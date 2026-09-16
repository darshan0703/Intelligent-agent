"""
app/intelligence/entity_resolution/semantic_resolver.py

Embedding-based semantic entity resolution.

The resolver embeds the query using the injected EmbeddingPort and compares
it against pre-cached embeddings for each candidate menu item.  Embeddings
are cached in a plain dict (item.name -> embedding vector) to avoid
re-embedding on every call — the cache is instance-scoped, not global.

Cosine similarity is computed in pure Python / numpy; no ML framework is
imported in the domain layer.

No framework imports — pure domain logic.
"""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING, Protocol

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.domain.entities.menu_item import MenuItem

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Embedding port (structural subtyping — no langchain, no concrete import)
# ---------------------------------------------------------------------------


class EmbeddingPort(Protocol):
    """Minimal interface expected of an embedding provider."""

    async def embed(self, text: str) -> list[float]:
        """Return a unit-normalised embedding vector for *text*."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a batch of texts."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Numerically-stable cosine similarity for two 1-D vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# SemanticResolver — instance carries the embedding cache
# ---------------------------------------------------------------------------


class SemanticResolver:
    """
    Embedding-based entity resolver with in-memory embedding cache.

    The cache maps ``item.name -> embedding vector`` and persists for the
    lifetime of the instance.  Create one instance per application lifecycle
    (e.g. as a singleton in the DI container).

    Args:
        embedding_port: Concrete implementation of :class:`EmbeddingPort`.
    """

    def __init__(self, embedding_port: EmbeddingPort) -> None:
        self._port = embedding_port
        # item.name (str) -> embedding (list[float])
        self._cache: dict[str, list[float]] = {}

    async def _get_embedding(self, text: str) -> list[float]:
        """Return embedding from cache or compute and cache it."""
        if text not in self._cache:
            self._cache[text] = await self._port.embed(text)
        return self._cache[text]

    async def warm_cache(self, candidates: list[MenuItem]) -> None:
        """
        Pre-embed all candidate names in a single batch call.

        Call this when the menu is (re)loaded to avoid latency on the first
        query.
        """
        uncached = [item.name for item in candidates if item.name not in self._cache]
        if not uncached:
            return
        vectors = await self._port.embed_batch(uncached)
        for name, vec in zip(uncached, vectors):
            self._cache[name] = vec
        logger.info(
            "semantic_resolver.cache_warmed",
            count=len(uncached),
            total_cached=len(self._cache),
        )

    async def semantic_match(
        self,
        text: str,
        candidates: list[MenuItem],
        threshold: float = 0.75,
    ) -> tuple[MenuItem | None, float]:
        """
        Find the best semantic match for *text* within *candidates*.

        Args:
            text:       Raw user-supplied text (already past earlier tiers).
            candidates: Pool of MenuItem objects.
            threshold:  Minimum cosine similarity to accept (0-1).

        Returns:
            ``(best_item, similarity)`` — *best_item* is ``None`` when no
            candidate meets *threshold*.
        """
        if not candidates:
            return None, 0.0

        query_vec = await self._port.embed(text)

        # Ensure all candidate embeddings are cached (batch where possible)
        uncached = [item.name for item in candidates if item.name not in self._cache]
        if uncached:
            vectors = await self._port.embed_batch(uncached)
            for name, vec in zip(uncached, vectors):
                self._cache[name] = vec

        best_item: MenuItem | None = None
        best_sim: float = 0.0

        for item in candidates:
            item_vec = self._cache[item.name]
            sim = _cosine_similarity(query_vec, item_vec)
            if sim > best_sim:
                best_sim = sim
                best_item = item

        if best_sim >= threshold and best_item is not None:
            logger.debug(
                "semantic_resolver.hit",
                query=text,
                matched=best_item.name,
                item_id=best_item.id,
                similarity=round(best_sim, 4),
                threshold=threshold,
            )
            return best_item, best_sim

        logger.debug(
            "semantic_resolver.miss",
            query=text,
            best_sim=round(best_sim, 4),
            threshold=threshold,
        )
        return None, best_sim


# ---------------------------------------------------------------------------
# Module-level convenience wrapper (for callers that do not own an instance)
# ---------------------------------------------------------------------------


async def semantic_match(
    text: str,
    candidates: list[MenuItem],
    embedding_port: EmbeddingPort,
    threshold: float = 0.75,
) -> tuple[MenuItem | None, float]:
    """
    Stateless convenience wrapper around :class:`SemanticResolver`.

    Note: This creates a *temporary* resolver with no persistent cache.
    Prefer injecting a long-lived :class:`SemanticResolver` instance in
    production to benefit from embedding caching.
    """
    resolver = SemanticResolver(embedding_port)
    return await resolver.semantic_match(text, candidates, threshold)
