"""
app/config/llm_config.py
LLM model configuration registry.
Centralises model IDs, temperature presets, and token limits so that
adapters and intelligence agents reference this module — not hard-coded strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config.settings import get_settings


@dataclass(frozen=True)
class ModelProfile:
    """Immutable descriptor for a single LLM model variant."""

    model_id: str
    temperature: float
    max_tokens: int
    supports_tools: bool = True
    supports_structured_output: bool = True
    description: str = ""

    def to_kwargs(self) -> dict[str, Any]:
        """Return kwargs suitable for passing to a LangChain chat model."""
        return {
            "model": self.model_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


def _build_profiles() -> dict[str, ModelProfile]:
    """Build model profile registry from current settings."""
    s = get_settings()
    return {
        "default": ModelProfile(
            model_id=s.groq_default_model,
            temperature=s.groq_temperature,
            max_tokens=s.groq_max_tokens,
            description="Primary reasoning model — balanced quality/speed",
        ),
        "fast": ModelProfile(
            model_id=s.groq_fast_model,
            temperature=s.groq_temperature,
            max_tokens=512,
            description="Low-latency model for simple classifications",
        ),
        "creative": ModelProfile(
            model_id=s.groq_default_model,
            temperature=0.7,
            max_tokens=s.groq_max_tokens,
            description="Higher temperature for natural, varied responses",
        ),
        "precise": ModelProfile(
            model_id=s.groq_default_model,
            temperature=0.0,
            max_tokens=s.groq_max_tokens,
            description="Zero temperature for deterministic structured output",
        ),
        "tool_use": ModelProfile(
            model_id=s.groq_default_model,
            temperature=0.1,
            max_tokens=s.groq_max_tokens,
            supports_tools=True,
            description="Tool-calling agent loop",
        ),
    }


class LLMConfig:
    """Registry of named model profiles, built once from settings.

    Usage::

        config = LLMConfig()
        profile = config.get("precise")
        kwargs = profile.to_kwargs()
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ModelProfile] = _build_profiles()

    def get(self, name: str = "default") -> ModelProfile:
        """Return a named profile, falling back to 'default'."""
        return self._profiles.get(name, self._profiles["default"])

    def all_profiles(self) -> dict[str, ModelProfile]:
        """Return the full registry (read-only copy)."""
        return dict(self._profiles)

    def register(self, name: str, profile: ModelProfile) -> None:
        """Register or override a named profile at runtime."""
        object.__setattr__(self, "_profiles", {**self._profiles, name: profile})


# Module-level singleton — import and use directly:
#   from app.config.llm_config import llm_config
llm_config = LLMConfig()
