"""
app/intelligence/entity_resolution/fuzzy_resolver.py

Rapidfuzz-based fuzzy entity resolution.

Uses a two-signal approach:
  1. ``jaro_winkler_similarity`` — primary signal; rewards prefix matches and
     handles OCR / transcription noise well.
  2. ``token_sort_ratio`` — secondary signal for multi-word names where word
     order may differ (e.g. "fries large" vs "large fries").

Both are blended into a weighted confidence score.  Only matches that exceed
*threshold* are returned.

No framework imports — pure domain logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.domain.entities.menu_item import MenuItem

logger = get_logger(__name__)

# Blend weights
_JARO_WEIGHT: float = 0.6
_TOKEN_SORT_WEIGHT: float = 0.4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _blend_score(jaro: float, token_sort_ratio: float) -> float:
    """
    Weighted blend of jaro-winkler (0-1) and token_sort_ratio (0-100).

    token_sort_ratio is normalised to 0-1 before blending.
    """
    return _JARO_WEIGHT * jaro + _TOKEN_SORT_WEIGHT * (token_sort_ratio / 100.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fuzzy_match(
    text: str,
    candidates: list[MenuItem],
    threshold: float = 0.82,
) -> tuple[MenuItem | None, float]:
    """
    Find the best fuzzy match for *text* within *candidates*.

    Args:
        text:       Raw user-supplied text (already past exact / alias tiers).
        candidates: Pool of MenuItem objects.
        threshold:  Minimum blended confidence score (0-1) to accept.

    Returns:
        A tuple ``(best_item, confidence)`` where *best_item* is ``None``
        when no candidate meets *threshold*.
    """
    try:
        from rapidfuzz import fuzz
        from rapidfuzz.distance import JaroWinkler
    except ImportError as exc:  # pragma: no cover
        logger.error(
            "fuzzy_resolver.rapidfuzz_not_installed",
            error=str(exc),
            hint="pip install rapidfuzz",
        )
        return None, 0.0

    if not candidates:
        return None, 0.0

    needle = text.strip().lower()
    best_item: MenuItem | None = None
    best_score: float = 0.0

    for item in candidates:
        haystack = item.name.lower()
        jaro = JaroWinkler.normalized_similarity(needle, haystack)
        token_sort = fuzz.token_sort_ratio(needle, haystack)
        blended = _blend_score(jaro, token_sort)

        if blended > best_score:
            best_score = blended
            best_item = item

    if best_score >= threshold and best_item is not None:
        logger.debug(
            "fuzzy_resolver.hit",
            needle=needle,
            matched=best_item.name,
            item_id=best_item.id,
            confidence=round(best_score, 4),
            threshold=threshold,
        )
        return best_item, best_score

    logger.debug(
        "fuzzy_resolver.miss",
        needle=needle,
        best_score=round(best_score, 4),
        threshold=threshold,
    )
    return None, best_score
