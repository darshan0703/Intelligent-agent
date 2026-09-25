"""
app/infrastructure/llm/hybrid_llm_adapter.py
Hybrid & Fallback LLM Adapter implementing LanguageModelPort.
Coordinates primary (Groq) and fallback (Google Gemini) LLM providers with automatic zero-downtime failover.
"""
from __future__ import annotations
import time
from typing import Any, TypeVar
from pydantic import BaseModel
from app.config.settings import get_settings
from app.infrastructure.llm.gemini_adapter import GeminiAdapter
from app.infrastructure.llm.groq_adapter import GroqAdapter
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class HybridLLMAdapter(LanguageModelPort):
    """
    Hybrid LLM engine providing ultra-resilient inference:
    - Primary: Groq (ultra-low latency Llama-3.3-70B)
    - Fallback: Google Gemini (high intelligence gemini-3.6-flash / gemini-2.5-flash-lite)
    Automatically intercepts rate limits (429), timeouts, and API disruptions,
    failing over to Gemini with 0 user-facing downtime.
    """

    def __init__(
        self,
        primary: LanguageModelPort | None = None,
        fallback: LanguageModelPort | None = None,
    ):
        settings = get_settings()
        self._groq_configured = bool(settings.groq_api_key and settings.groq_api_key.strip())
        self._gemini_configured = bool(settings.gemini_api_key and settings.gemini_api_key.strip())

        self.primary = primary or (GroqAdapter() if self._groq_configured else None)
        self.fallback = fallback or (GeminiAdapter() if self._gemini_configured else None)

        # In case primary is unconfigured but fallback is configured, swap them
        if not self.primary and self.fallback:
            self.primary = self.fallback
            self.fallback = None

        self.failover_count: int = 0
        self.primary_count: int = 0

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates text via primary LLM, failing over to secondary LLM upon any failure.
        """
        start_time = time.monotonic()

        if self.primary:
            try:
                result = await self.primary.generate_text(prompt, **kwargs)
                self.primary_count += 1
                return result
            except Exception as exc:
                self.failover_count += 1
                logger.warning(
                    "llm_primary_generate_failed_failing_over",
                    primary_type=type(self.primary).__name__,
                    error=str(exc),
                    failover_count=self.failover_count,
                )
                if not self.fallback:
                    raise

        if self.fallback:
            logger.info("llm_fallback_invoked", fallback_type=type(self.fallback).__name__)
            result = await self.fallback.generate_text(prompt, **kwargs)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "llm_fallback_generate_success",
                fallback_type=type(self.fallback).__name__,
                duration_ms=duration_ms,
            )
            return result

        raise RuntimeError("No LLM providers configured or available in HybridLLMAdapter.")

    async def structured_complete(self, prompt: str, output_schema: type[T], **kwargs: Any) -> T:
        """
        Extracts structured schema via primary LLM, failing over to secondary upon any failure.
        """
        start_time = time.monotonic()

        if self.primary:
            try:
                result = await self.primary.structured_complete(prompt, output_schema, **kwargs)
                self.primary_count += 1
                return result
            except Exception as exc:
                self.failover_count += 1
                logger.warning(
                    "llm_primary_structured_failed_failing_over",
                    primary_type=type(self.primary).__name__,
                    schema=output_schema.__name__,
                    error=str(exc),
                    failover_count=self.failover_count,
                )
                if not self.fallback:
                    raise

        if self.fallback:
            logger.info(
                "llm_fallback_structured_invoked",
                fallback_type=type(self.fallback).__name__,
                schema=output_schema.__name__,
            )
            result = await self.fallback.structured_complete(prompt, output_schema, **kwargs)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "llm_fallback_structured_success",
                fallback_type=type(self.fallback).__name__,
                schema=output_schema.__name__,
                duration_ms=duration_ms,
            )
            return result

        raise RuntimeError("No LLM providers configured or available in HybridLLMAdapter.")

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Executes tool completion via primary or fallback.
        """
        if self.primary:
            try:
                return await self.primary.complete_with_tools(messages, tools, **kwargs)
            except Exception as exc:
                logger.warning("llm_primary_tools_failed_failing_over", error=str(exc))
                if not self.fallback:
                    raise

        if self.fallback:
            return await self.fallback.complete_with_tools(messages, tools, **kwargs)

        raise RuntimeError("No LLM providers configured or available in HybridLLMAdapter.")
