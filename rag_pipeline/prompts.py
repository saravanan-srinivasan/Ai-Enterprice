"""
rag_pipeline/prompts.py
------------------------
Centralized prompt templates for each agent type.
Uses structured templates to ensure consistent, hallucination-resistant outputs.
"""

from string import Template
from typing import List

from rag_pipeline.retriever import RetrievedChunk


SYSTEM_GUARDRAILS = """
You are an enterprise AI knowledge assistant. You must:
1. Answer ONLY based on the provided context documents
2. If the context doesn't contain enough information, say "Based on available documents, I cannot fully answer this."
3. Never fabricate statistics, dates, names, or figures not present in the context
4. Always cite which document(s) your answer is based on
5. Be precise, professional, and concise
6. Flag if the question is outside the scope of ingested enterprise data
"""

QUERY_SYSTEM_PROMPT = f"""{SYSTEM_GUARDRAILS}

You are answering enterprise knowledge queries. Provide accurate, well-structured answers grounded in the provided context. Include confidence indicators when uncertain.
"""

ANALYSIS_SYSTEM_PROMPT = f"""{SYSTEM_GUARDRAILS}

You are an expert business analyst. Analyze the provided enterprise data and extract meaningful patterns, trends, anomalies, and insights. Structure your analysis with: Executive Summary, Key Findings, Supporting Evidence, and Recommendations.
"""

REPORT_SYSTEM_PROMPT = f"""{SYSTEM_GUARDRAILS}

You are an enterprise report writer. Generate professional, structured reports from the provided data. Use clear headings, bullet points where appropriate, and include an executive summary. Reports should be decision-ready.
"""

ACTION_SYSTEM_PROMPT = f"""{SYSTEM_GUARDRAILS}

You are an enterprise decision support system. Based on the provided context, evaluate the situation and provide structured decision recommendations with:
1. Situation Assessment
2. Decision Options (with pros/cons)
3. Recommended Action
4. Risk Factors
5. Success Metrics
"""

ANOMALY_DETECTION_PROMPT = f"""{SYSTEM_GUARDRAILS}

You are an enterprise anomaly detection specialist. Analyze the data for:
- Statistical outliers
- Process deviations
- Compliance violations
- Performance degradations
- Security incidents

For each anomaly found, provide: Severity (Critical/High/Medium/Low), Category, Description, Affected Records, and Recommended Action.
"""


def build_rag_prompt(
    query: str,
    retrieved_chunks: List[RetrievedChunk],
    session_memory: List[dict] = None,
    agent_type: str = "query",
) -> str:
    """
    Build the user-turn prompt with injected context.
    Structures context clearly with source attribution.
    """
    # Format retrieved context
    context_blocks = []
    for i, rc in enumerate(retrieved_chunks, start=1):
        block = (
            f"[Source {i}: {rc.chunk.filename}"
            + (f", Page {rc.chunk.page_number}" if rc.chunk.page_number else "")
            + f" | Relevance: {rc.combined_score:.2f}]\n"
            + rc.chunk.content
        )
        context_blocks.append(block)

    context_section = "\n\n---\n\n".join(context_blocks)

    # Conversation memory
    history_section = ""
    if session_memory:
        turns = []
        for turn in session_memory[-4:]:  # Last 4 turns
            role = turn.get("role", "").upper()
            content = turn.get("content", "")[:300]
            turns.append(f"{role}: {content}")
        history_section = (
            "\n\n### Conversation History (recent):\n" + "\n".join(turns)
        )

    # Agent-specific instructions
    agent_instructions = {
        "query": "Answer the question accurately and concisely using the context above.",
        "analysis": "Provide a comprehensive analysis of the data, highlighting patterns and insights.",
        "report": "Generate a structured professional report based on the context.",
        "action": "Provide decision recommendations with clear options and reasoning.",
        "anomaly": "Identify and describe any anomalies or irregularities in the data.",
    }.get(agent_type, "Answer using the context provided.")

    prompt = f"""### Enterprise Knowledge Context:

{context_section}
{history_section}

### Task:
{agent_instructions}

### Question / Request:
{query}

### Instructions:
- Ground your response in the provided context documents
- Cite sources using [Source N] notation
- If confidence is uncertain, explicitly state it
- Structure your response clearly for enterprise stakeholders
"""
    return prompt


def build_confidence_evaluation_prompt(
    query: str, answer: str, context_chunks: List[RetrievedChunk]
) -> str:
    """
    Ask the LLM to self-evaluate confidence in its answer.
    Returns a structured evaluation for the guardrail system.
    """
    context_preview = "\n".join(
        [f"- {rc.chunk.content[:200]}..." for rc in context_chunks[:3]]
    )
    return f"""Evaluate the following AI-generated answer for accuracy and groundedness.

Question: {query}

Answer: {answer}

Supporting Context (excerpt):
{context_preview}

Provide a JSON response with these exact fields:
{{
  "confidence_score": <float 0.0-1.0>,
  "is_grounded": <true|false>,
  "unsupported_claims": [<list of claims not in context>],
  "quality_assessment": "<brief assessment>"
}}

Respond ONLY with the JSON object, no other text.
"""


def get_system_prompt(agent_type: str) -> str:
    """Return the appropriate system prompt for the given agent type."""
    prompts = {
        "query": QUERY_SYSTEM_PROMPT,
        "analysis": ANALYSIS_SYSTEM_PROMPT,
        "report": REPORT_SYSTEM_PROMPT,
        "action": ACTION_SYSTEM_PROMPT,
        "anomaly": ANOMALY_DETECTION_PROMPT,
    }
    return prompts.get(agent_type, QUERY_SYSTEM_PROMPT)
