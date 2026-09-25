"""
app/config/feature_flags.py
----------------------------
Typed feature-flag configuration for TheAtom.

Feature flags gate optional capabilities that may be expensive, in preview,
or require extra infrastructure (embeddings, voice, etc.).  They are loaded
once from settings at startup via ``get_feature_flags()``.

Design rules:
- Flags are immutable after startup (frozen dataclass).
- No framework imports — pure Python.
- All flags default to the safest / cheapest option (False).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class FeatureFlags:
    """Immutable set of runtime feature toggles."""

    use_semantic_entity_resolution: bool
    """When True, entity resolution falls back to embedding-based semantic
    similarity after fuzzy matching fails.  Requires an EmbeddingPort adapter."""

    use_embedding_recommendations: bool
    """When True, recommendation scoring includes an embedding-based semantic
    affinity signal in addition to rule-based signals."""

    use_contextual_memory: bool
    """When True, the MemoryStore is consulted to suppress or boost items
    based on past observations (e.g., previously rejected meal offers)."""

    use_cross_sell_signals: bool
    """When True, the recommendation engine queries the catalog for
    cross-sell associations and includes a cross-sell signal in scoring."""

    use_mmr_diversity: bool
    """When True, Maximal Marginal Relevance (MMR) is applied to the
    candidate list to increase diversity in the final recommendation set."""

    voice_enabled: bool
    """Master toggle for voice I/O pipeline (TTS + STT).  Both
    ``tts_enabled`` and ``stt_enabled`` in settings must also be True."""

    def any_voice_active(self) -> bool:
        """Return True if the voice pipeline is globally enabled."""
        return self.voice_enabled

    def full_intelligence(self) -> bool:
        """Return True when all intelligence features are active."""
        return all([
            self.use_semantic_entity_resolution,
            self.use_embedding_recommendations,
            self.use_contextual_memory,
            self.use_cross_sell_signals,
            self.use_mmr_diversity,
        ])


# ---------------------------------------------------------------------------
# Default flag sets — useful for testing and early development
# ---------------------------------------------------------------------------

DEVELOPMENT_FLAGS = FeatureFlags(
    use_semantic_entity_resolution=False,
    use_embedding_recommendations=False,
    use_contextual_memory=True,
    use_cross_sell_signals=True,
    use_mmr_diversity=False,
    voice_enabled=False,
)
"""Lightweight flag set for local development — avoids embedding costs."""

PRODUCTION_FLAGS = FeatureFlags(
    use_semantic_entity_resolution=True,
    use_embedding_recommendations=True,
    use_contextual_memory=True,
    use_cross_sell_signals=True,
    use_mmr_diversity=True,
    voice_enabled=False,
)
"""Full-capability flag set intended for production deployments."""


@lru_cache(maxsize=1)
def get_feature_flags() -> FeatureFlags:
    """Return the active ``FeatureFlags`` instance derived from settings.

    Flags are computed once at startup and cached for the process lifetime.

    Usage::

        from app.config.feature_flags import get_feature_flags
        flags = get_feature_flags()
        if flags.use_contextual_memory:
            ...
    """
    from app.config.settings import get_settings

    settings = get_settings()

    return FeatureFlags(
        use_semantic_entity_resolution=not settings.is_development,
        use_embedding_recommendations=not settings.is_development,
        use_contextual_memory=True,
        use_cross_sell_signals=True,
        use_mmr_diversity=not settings.is_development,
        voice_enabled=settings.tts_enabled and settings.stt_enabled,
    )
