"""
app/ports/llm_port.py
Abstract protocol for Language Model providers.
Domain and application layers depend ONLY on this protocol.
"""
from __future__ import annotations
from typing import Protocol, TypeVar, Any, runtime_checkable
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

@runtime_checkable
class LanguageModelPort(Protocol):
    async def structured_complete(self, prompt: str, output_schema: type[T], **kwargs: Any) -> T:
        """Extract structured data from LLM with strict schema enforcement."""
        ...

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """Generate natural language response."""
        ...

    async def complete_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Tool-calling completion for autonomous cashier agent."""
        ...
