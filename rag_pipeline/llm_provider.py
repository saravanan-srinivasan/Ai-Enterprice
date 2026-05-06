"""
rag_pipeline/llm_provider.py
-----------------------------
Groq LLM provider integration.
Implements retry with exponential backoff.
Tracks token usage for cost monitoring.

Uses Groq API with llama-3.3-70b-versatile model for production deployment.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from utils.config import settings
from utils.logger import get_logger, metrics

logger = get_logger(__name__, service="llm_provider")


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""

    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    finish_reason: str = "stop"


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


# ─── Abstract Provider ────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Base class for all LLM provider implementations."""

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        max_tokens: int = None,
        temperature: float = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the API key is configured."""
        ...


# ─── Groq Provider ────────────────────────────────────────────────────────────

class GroqProvider(LLMProvider):
    """Groq API integration using llama-3.3-70b-versatile model."""

    def __init__(self) -> None:
        from groq import Groq
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.llm_model

    def is_available(self) -> bool:
        return bool(settings.groq_api_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def complete(
        self,
        messages: List[LLMMessage],
        max_tokens: int = None,
        temperature: float = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Complete a message sequence using Groq API.
        Note: Groq API is currently synchronous, so we wrap it in a thread pool.
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        max_tokens = max_tokens or settings.llm_max_tokens
        temperature = temperature if temperature is not None else settings.llm_temperature

        # Convert LLMMessage to Groq format
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Prepare kwargs
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if stop_sequences:
            kwargs["stop"] = stop_sequences

        t0 = time.monotonic()
        try:
            # Run Groq API call in thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: self._client.chat.completions.create(**kwargs)
                )

            latency_ms = int((time.monotonic() - t0) * 1000)

            choice = response.choices[0]
            content = choice.message.content or ""

            # Groq returns usage information
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

            metrics.record("llm_latency_ms", latency_ms, provider="groq")
            metrics.increment("llm_tokens", value=total_tokens)

            logger.info(
                "groq_completion_success",
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )

            return LLMResponse(
                content=content,
                model=self._model,
                provider="groq",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                finish_reason=choice.finish_reason or "stop",
            )

        except Exception as exc:
            logger.error("groq_api_error", error=str(exc), model=self._model)
            metrics.increment("llm_failure", provider="groq")
            raise


# ─── LLM Client ───────────────────────────────────────────────────────────────

class LLMClient:
    """
    LLM facade for Groq API.
    Provides convenient methods for common LLM patterns.
    """

    def __init__(self) -> None:
        self._provider = GroqProvider()
        if not self._provider.is_available():
            raise RuntimeError(
                "Groq API key not configured. Set GROQ_API_KEY environment variable."
            )
        logger.info("groq_provider_ready", model=settings.llm_model)

    async def complete(
        self,
        messages: List[LLMMessage],
        max_tokens: int = None,
        temperature: float = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Complete a message sequence.
        """
        try:
            response = await self._provider.complete(
                messages, max_tokens, temperature, stop_sequences
            )
            metrics.increment("llm_success", provider="groq")
            return response
        except Exception as exc:
            logger.error("llm_complete_failed", error=str(exc))
            metrics.increment("llm_failure", provider="groq")
            raise

    async def complete_with_system(
        self,
        system_prompt: str,
        user_message: str,
        history: Optional[List[LLMMessage]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Convenience method for standard system+user pattern."""
        messages = [LLMMessage(role="system", content=system_prompt)]
        if history:
            messages.extend(history)
        messages.append(LLMMessage(role="user", content=user_message))
        return await self.complete(messages, **kwargs)


# ─── Singleton ────────────────────────────────────────────────────────────────

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
