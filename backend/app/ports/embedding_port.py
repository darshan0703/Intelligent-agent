"""
app/ports/embedding_port.py
Abstract protocol for Vector Embedding providers.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class EmbeddingPort(Protocol):
    async def embed_text(self, text: str) -> list[float]:
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    def dimensions(self) -> int:
        ...
