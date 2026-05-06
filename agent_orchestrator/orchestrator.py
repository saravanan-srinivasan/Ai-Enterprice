"""
agent_orchestrator/orchestrator.py
------------------------------------
Multi-agent orchestration layer.
Routes queries to specialized agents with tool-calling, memory, and CoT reasoning.
Agents: QueryAgent, AnalysisAgent, ReportAgent, ActionAgent
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from rag_pipeline.llm_provider import LLMClient, LLMMessage, LLMResponse, get_llm_client
from rag_pipeline.prompts import build_confidence_evaluation_prompt, build_rag_prompt, get_system_prompt
from rag_pipeline.retriever import HybridRetriever, RetrievedChunk
from utils.cache import cache_service
from utils.config import settings
from utils.logger import get_logger, metrics
from utils.models import AgentType, QueryResponse, QueryStatus, SourceDocument

logger = get_logger(__name__, service="orchestrator")


# ─── Agent Memory ─────────────────────────────────────────────────────────────

class AgentMemory:
    """Short-term conversation memory backed by Redis."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._local: List[Dict] = []

    async def load(self) -> List[Dict]:
        self._local = await cache_service.get_session_memory(self.session_id)
        return self._local

    async def add_turn(self, role: str, content: str) -> None:
        self._local.append({"role": role, "content": content, "timestamp": datetime.utcnow().isoformat()})
        await cache_service.update_session_memory(
            self.session_id, self._local, settings.memory_window_size
        )

    def get_llm_history(self) -> List[LLMMessage]:
        """Convert memory to LLM message format, excluding system messages."""
        return [
            LLMMessage(role=m["role"], content=m["content"])
            for m in self._local
            if m["role"] in ("user", "assistant")
        ]


# ─── Tool Definitions ─────────────────────────────────────────────────────────

@dataclass
class Tool:
    """A callable tool available to agents."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None


class ToolRegistry:
    """Registry of tools available to agents."""

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    async def call(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        handlers = {
            "retrieve_context": self._retrieve_context,
            "summarize_document": self._summarize_document,
            "detect_anomalies": self._detect_anomalies,
            "compute_statistics": self._compute_statistics,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(tool_name, False, None, f"Unknown tool: {tool_name}")
        try:
            result = await handler(**params)
            return ToolResult(tool_name, True, result)
        except Exception as exc:
            return ToolResult(tool_name, False, None, str(exc))

    async def _retrieve_context(self, query: str, top_k: int = 5) -> List[Dict]:
        chunks = self._retriever.retrieve(query, top_k=top_k)
        return [
            {
                "content": c.chunk.content[:500],
                "source": c.chunk.filename,
                "score": c.combined_score,
            }
            for c in chunks
        ]

    async def _summarize_document(self, doc_filename: str) -> Dict:
        chunks = self._retriever.retrieve(
            f"summarize {doc_filename}", top_k=10, filters={"filename": doc_filename}
        )
        return {
            "filename": doc_filename,
            "chunk_count": len(chunks),
            "content_preview": chunks[0].chunk.content[:300] if chunks else "Not found",
        }

    async def _detect_anomalies(self, domain: str) -> Dict:
        chunks = self._retriever.retrieve(
            f"errors failures anomalies issues {domain}", top_k=10
        )
        return {
            "domain": domain,
            "suspicious_entries": [
                {"content": c.chunk.content[:200], "score": c.combined_score}
                for c in chunks
                if c.combined_score > 0.3
            ],
        }

    async def _compute_statistics(self, metric: str) -> Dict:
        chunks = self._retriever.retrieve(f"statistics data numbers {metric}", top_k=5)
        return {
            "metric": metric,
            "data_points": len(chunks),
            "sources": [c.chunk.filename for c in chunks],
        }


# ─── Base Agent ───────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    """Output from any agent execution."""
    answer: str
    reasoning_steps: List[str]
    sources: List[SourceDocument]
    confidence_score: float
    tokens_used: int
    latency_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base for all agents in the system."""

    def __init__(
        self,
        llm: LLMClient,
        retriever: HybridRetriever,
        tools: ToolRegistry,
        agent_type: AgentType,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.tools = tools
        self.agent_type = agent_type
        self._logger = get_logger(
            __name__, agent=agent_type.value, service="agent"
        )

    @abstractmethod
    async def execute(
        self,
        query: str,
        memory: AgentMemory,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> AgentResult:
        ...

    async def _retrieve_and_build_context(
        self, query: str, top_k: int, filters: Optional[Dict]
    ) -> Tuple[List[RetrievedChunk], List[SourceDocument]]:
        """Shared retrieval step for all agents."""
        chunks = self.retriever.retrieve(query, top_k=top_k, filters=filters)
        sources = self.retriever.to_source_documents(chunks)
        return chunks, sources

    async def _evaluate_confidence(
        self,
        query: str,
        answer: str,
        chunks: List[RetrievedChunk],
    ) -> float:
        """
        Guardrail: self-evaluate answer confidence.
        Falls back to a score based on retrieval scores on LLM error.
        """
        if not chunks:
            return 0.1

        try:
            eval_prompt = build_confidence_evaluation_prompt(query, answer, chunks)
            response = await self.llm.complete_with_system(
                system_prompt="You are an objective AI output evaluator. Respond only with JSON.",
                user_message=eval_prompt,
                max_tokens=256,
                temperature=0.0,
            )
            data = json.loads(response.content.strip())
            score = float(data.get("confidence_score", 0.5))
            return max(0.0, min(1.0, score))
        except Exception as exc:
            # Fallback: average of top retrieval scores
            self._logger.warning("confidence_eval_failed", error=str(exc))
            avg_score = sum(c.combined_score for c in chunks[:3]) / min(len(chunks), 3)
            return round(avg_score, 3)

    def _extract_reasoning_steps(self, raw: str) -> Tuple[str, List[str]]:
        """
        Chain-of-thought: extract <think>...</think> blocks.
        Steps are stored internally but not exposed in final answer.
        """
        import re
        steps = re.findall(r"<think>(.*?)</think>", raw, re.DOTALL)
        clean_answer = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return clean_answer, [s.strip() for s in steps]


# ─── Specialized Agents ───────────────────────────────────────────────────────

class QueryAgent(BaseAgent):
    """
    Handles direct factual queries against the knowledge base.
    Optimized for accuracy and citation.
    """

    async def execute(
        self,
        query: str,
        memory: AgentMemory,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> AgentResult:
        t0 = time.monotonic()
        self._logger.info("query_agent_start", query_preview=query[:60])

        await memory.load()
        chunks, sources = await self._retrieve_and_build_context(query, top_k, filters)

        user_prompt = build_rag_prompt(
            query=query,
            retrieved_chunks=chunks,
            session_memory=memory.get_llm_history() and [m.__dict__ for m in memory.get_llm_history()],
            agent_type="query",
        )

        response = await self.llm.complete_with_system(
            system_prompt=get_system_prompt("query"),
            user_message=user_prompt,
            history=memory.get_llm_history(),
        )

        answer, steps = self._extract_reasoning_steps(response.content)
        confidence = await self._evaluate_confidence(query, answer, chunks)

        await memory.add_turn("user", query)
        await memory.add_turn("assistant", answer)

        latency_ms = int((time.monotonic() - t0) * 1000)
        metrics.record("agent_latency_ms", latency_ms, agent="query")

        return AgentResult(
            answer=answer,
            reasoning_steps=steps,
            sources=sources,
            confidence_score=confidence,
            tokens_used=response.total_tokens,
            latency_ms=latency_ms,
        )


class AnalysisAgent(BaseAgent):
    """
    Extracts patterns, trends, and insights from enterprise data.
    Performs multi-step tool-assisted analysis.
    """

    async def execute(
        self,
        query: str,
        memory: AgentMemory,
        top_k: int = 8,
        filters: Optional[Dict] = None,
    ) -> AgentResult:
        t0 = time.monotonic()
        self._logger.info("analysis_agent_start", query_preview=query[:60])

        # Step 1: Retrieve broad context
        chunks, sources = await self._retrieve_and_build_context(query, top_k, filters)

        # Step 2: Use anomaly detection tool for supplemental data
        tool_result = await self.tools.call(
            "detect_anomalies", {"domain": query[:50]}
        )

        user_prompt = build_rag_prompt(
            query=query,
            retrieved_chunks=chunks,
            agent_type="analysis",
        )

        if tool_result.success and tool_result.result:
            anomaly_context = json.dumps(tool_result.result, indent=2)
            user_prompt += f"\n\n### Anomaly Detection Tool Output:\n{anomaly_context}"

        response = await self.llm.complete_with_system(
            system_prompt=get_system_prompt("analysis"),
            user_message=user_prompt,
        )

        answer, steps = self._extract_reasoning_steps(response.content)
        confidence = await self._evaluate_confidence(query, answer, chunks)

        latency_ms = int((time.monotonic() - t0) * 1000)
        metrics.record("agent_latency_ms", latency_ms, agent="analysis")

        return AgentResult(
            answer=answer,
            reasoning_steps=steps,
            sources=sources,
            confidence_score=confidence,
            tokens_used=response.total_tokens,
            latency_ms=latency_ms,
            metadata={"tool_used": "detect_anomalies"},
        )


class ReportAgent(BaseAgent):
    """
    Generates structured enterprise reports from knowledge base data.
    Designed for executive consumption.
    """

    async def execute(
        self,
        query: str,
        memory: AgentMemory,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> AgentResult:
        t0 = time.monotonic()
        self._logger.info("report_agent_start", query_preview=query[:60])

        chunks, sources = await self._retrieve_and_build_context(query, top_k, filters)

        # Gather supplemental statistics
        stats_result = await self.tools.call(
            "compute_statistics", {"metric": query[:60]}
        )

        user_prompt = build_rag_prompt(
            query=query,
            retrieved_chunks=chunks,
            agent_type="report",
        )

        if stats_result.success:
            user_prompt += f"\n\n### Statistical Context:\n{json.dumps(stats_result.result, indent=2)}"

        user_prompt += "\n\n### Additional Instruction:\nGenerate a complete, professional enterprise report with: Executive Summary, Key Findings, Detailed Analysis, Data Tables (if applicable), Recommendations, and Next Steps."

        response = await self.llm.complete_with_system(
            system_prompt=get_system_prompt("report"),
            user_message=user_prompt,
            max_tokens=settings.llm_max_tokens,
        )

        answer, steps = self._extract_reasoning_steps(response.content)
        confidence = await self._evaluate_confidence(query, answer, chunks)

        latency_ms = int((time.monotonic() - t0) * 1000)

        return AgentResult(
            answer=answer,
            reasoning_steps=steps,
            sources=sources,
            confidence_score=confidence,
            tokens_used=response.total_tokens,
            latency_ms=latency_ms,
            metadata={"report_type": "enterprise_standard"},
        )


class ActionAgent(BaseAgent):
    """
    Decision support agent providing structured recommendations.
    Simulates decision pathways with risk analysis.
    """

    async def execute(
        self,
        query: str,
        memory: AgentMemory,
        top_k: int = 6,
        filters: Optional[Dict] = None,
    ) -> AgentResult:
        t0 = time.monotonic()
        self._logger.info("action_agent_start", query_preview=query[:60])

        chunks, sources = await self._retrieve_and_build_context(query, top_k, filters)

        user_prompt = build_rag_prompt(
            query=query,
            retrieved_chunks=chunks,
            agent_type="action",
        )

        user_prompt += """

### Decision Framework:
Structure your response as:
1. **Situation Assessment**: What is happening and why it matters
2. **Decision Options**: List 2-3 concrete options with pros/cons
3. **Recommended Action**: Your top recommendation with justification
4. **Risk Factors**: Key risks and mitigation strategies
5. **Success Metrics**: How to measure if the decision was correct
6. **Timeline**: Suggested implementation timeline
"""

        response = await self.llm.complete_with_system(
            system_prompt=get_system_prompt("action"),
            user_message=user_prompt,
        )

        answer, steps = self._extract_reasoning_steps(response.content)
        confidence = await self._evaluate_confidence(query, answer, chunks)

        latency_ms = int((time.monotonic() - t0) * 1000)

        return AgentResult(
            answer=answer,
            reasoning_steps=steps,
            sources=sources,
            confidence_score=confidence,
            tokens_used=response.total_tokens,
            latency_ms=latency_ms,
        )


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class AgentOrchestrator:
    """
    Central orchestrator that routes queries to the appropriate agent.
    Manages the full query lifecycle: cache check → agent execution → persist.
    """

    def __init__(self) -> None:
        self._llm = get_llm_client()
        self._retriever = HybridRetriever()
        self._tools = ToolRegistry(self._retriever)
        self._agents: Dict[AgentType, BaseAgent] = {
            AgentType.QUERY: QueryAgent(self._llm, self._retriever, self._tools, AgentType.QUERY),
            AgentType.ANALYSIS: AnalysisAgent(self._llm, self._retriever, self._tools, AgentType.ANALYSIS),
            AgentType.REPORT: ReportAgent(self._llm, self._retriever, self._tools, AgentType.REPORT),
            AgentType.ACTION: ActionAgent(self._llm, self._retriever, self._tools, AgentType.ACTION),
        }
        logger.info("orchestrator_ready", agents=list(self._agents.keys()))

    async def process_query(
        self,
        query_id: str,
        session_id: str,
        question: str,
        agent_type: AgentType = AgentType.QUERY,
        top_k: int = 5,
        include_sources: bool = True,
        filters: Optional[Dict] = None,
    ) -> QueryResponse:
        """
        Full query processing pipeline with caching, execution, and response building.
        """
        t_start = time.monotonic()
        memory = AgentMemory(session_id)

        # ── Cache check ──────────────────────────────────────────
        cached = await cache_service.get_query_result(
            question, agent_type.value, top_k
        )
        if cached:
            logger.info("query_cache_hit", query_id=query_id)
            cached["query_id"] = query_id
            cached["cached"] = True
            return QueryResponse(**cached)

        # ── Input validation + guardrails ─────────────────────────
        question = self._sanitize_input(question)

        # ── Agent execution ───────────────────────────────────────
        agent = self._agents.get(agent_type, self._agents[AgentType.QUERY])
        try:
            result = await asyncio.wait_for(
                agent.execute(question, memory, top_k, filters),
                timeout=settings.agent_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error("agent_timeout", query_id=query_id, agent=agent_type.value)
            result = AgentResult(
                answer="The request timed out. Please try a more specific query.",
                reasoning_steps=[],
                sources=[],
                confidence_score=0.0,
                tokens_used=0,
                latency_ms=int((time.monotonic() - t_start) * 1000),
            )

        # ── Output filtering ──────────────────────────────────────
        answer = self._filter_output(result.answer)

        response = QueryResponse(
            query_id=query_id,
            session_id=session_id,
            question=question,
            answer=answer,
            agent_type=agent_type,
            status=QueryStatus.COMPLETED,
            sources=result.sources if include_sources else [],
            confidence_score=result.confidence_score,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            cached=False,
            reasoning_steps=result.reasoning_steps if result.reasoning_steps else None,
            created_at=datetime.utcnow(),
        )

        # ── Cache result ──────────────────────────────────────────
        if result.confidence_score > 0.3:
            await cache_service.set_query_result(
                question,
                agent_type.value,
                top_k,
                response.model_dump(),
                ttl=settings.cache_ttl_seconds,
            )

        metrics.record("query_confidence", result.confidence_score)
        metrics.increment("queries_processed", agent=agent_type.value)
        logger.info(
            "query_complete",
            query_id=query_id,
            agent=agent_type.value,
            confidence=result.confidence_score,
            tokens=result.tokens_used,
            latency_ms=result.latency_ms,
        )

        return response

    def _sanitize_input(self, text: str) -> str:
        """Basic input sanitization — remove null bytes and excessive whitespace."""
        return " ".join(text.replace("\x00", "").split()).strip()[:2000]

    def _filter_output(self, text: str) -> str:
        """
        Output filtering guardrail.
        Strips potential prompt injection markers and normalizes formatting.
        """
        import re
        # Remove any attempt to override system behavior
        injection_patterns = [
            r"Ignore previous instructions",
            r"Disregard the above",
            r"New instruction:",
            r"<\|system\|>",
        ]
        for pattern in injection_patterns:
            text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)
        return text.strip()


# ─── Singleton ────────────────────────────────────────────────────────────────

_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
