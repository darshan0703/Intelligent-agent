"""
app/infrastructure/llm/groq_adapter.py
Groq LLM adapter implementing LanguageModelPort.
LangChain dependencies are strictly contained inside this adapter.
"""
from __future__ import annotations
import time
from typing import Any, TypeVar
from pydantic import BaseModel
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config.settings import get_settings
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class GroqAdapter(LanguageModelPort):
    def __init__(self, model_name: str | None = None, temperature: float | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.groq_default_model
        self.temperature = temperature if temperature is not None else settings.groq_temperature
        self.api_key = settings.groq_api_key

        self._llm = ChatGroq(
            model=self.model_name,
            temperature=self.temperature,
            groq_api_key=self.api_key,
            max_tokens=settings.groq_max_tokens,
            timeout=settings.groq_timeout_seconds,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def structured_complete(self, prompt: str, output_schema: type[T], **kwargs: Any) -> T:
        start_time = time.monotonic()
        structured_llm = self._llm.with_structured_output(output_schema)
        try:
            result = await structured_llm.ainvoke(prompt)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("llm_structured_success", model=self.model_name, schema=output_schema.__name__, duration_ms=duration_ms)
            return result
        except Exception as exc:
            logger.error("llm_structured_failed", model=self.model_name, schema=output_schema.__name__, error=str(exc))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        start_time = time.monotonic()
        try:
            response = await self._llm.ainvoke(prompt)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("llm_generate_success", model=self.model_name, duration_ms=duration_ms)
            return str(response.content)
        except Exception as exc:
            logger.error("llm_generate_failed", model=self.model_name, error=str(exc))
            raise

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"role": "assistant", "content": "Tools routed"}
