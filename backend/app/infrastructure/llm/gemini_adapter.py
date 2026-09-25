"""
app/infrastructure/llm/gemini_adapter.py
Google Gemini LLM adapter implementing LanguageModelPort.
Supports gemini-3.6-flash and gemini-2.5-flash-lite with schema parsing and retry logic.
"""
from __future__ import annotations
import json
import re
import time
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config.settings import get_settings
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter(LanguageModelPort):
    def __init__(
        self,
        model_name: str | None = None,
        temperature: float | None = None,
        api_key: str | None = None,
    ):
        settings = get_settings()
        self.model_name = model_name or settings.gemini_default_model
        self.fallback_model = settings.gemini_fallback_model
        self.temperature = temperature if temperature is not None else settings.gemini_temperature
        self.api_key = api_key or settings.effective_gemini_api_key
        self.timeout = float(settings.gemini_timeout_seconds)

    async def _call_api(self, prompt: str, model: str | None = None, is_json: bool = False) -> str:
        target_model = model or self.model_name
        url = f"{BASE_URL}/{target_model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        generation_config: dict[str, Any] = {
            "temperature": self.temperature,
        }
        if is_json:
            generation_config["responseMimeType"] = "application/json"

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                # If primary model has an issue, attempt fallback model
                if target_model != self.fallback_model:
                    logger.warning("gemini_fallback_attempt", primary=target_model, fallback=self.fallback_model, status=resp.status_code)
                    return await self._call_api(prompt, model=self.fallback_model, is_json=is_json)
                resp.raise_for_status()

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates: {data}")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError(f"Gemini returned empty parts: {data}")
            return parts[0].get("text", "")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        start_time = time.monotonic()
        try:
            result = await self._call_api(prompt, is_json=False)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("gemini_generate_success", model=self.model_name, duration_ms=duration_ms)
            return result.strip()
        except Exception as exc:
            logger.error("gemini_generate_failed", model=self.model_name, error=str(exc))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def structured_complete(self, prompt: str, output_schema: type[T], **kwargs: Any) -> T:
        start_time = time.monotonic()
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        system_instruction = (
            f"You are a strict data extraction system.\n"
            f"You must return ONLY a JSON object strictly conforming to this JSON Schema:\n{schema_json}\n\n"
            f"User input:\n{prompt}"
        )
        try:
            raw_text = await self._call_api(system_instruction, is_json=True)
            clean_json = raw_text.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
                clean_json = re.sub(r"\n?```$", "", clean_json)
            result = output_schema.model_validate_json(clean_json)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("gemini_structured_success", model=self.model_name, schema=output_schema.__name__, duration_ms=duration_ms)
            return result
        except Exception as exc:
            logger.error("gemini_structured_failed", model=self.model_name, schema=output_schema.__name__, error=str(exc))
            raise

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"role": "assistant", "content": "Tools routed via Gemini"}
