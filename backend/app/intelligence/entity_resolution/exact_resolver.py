"""
app/intelligence/entity_resolution/exact_resolver.py

Exact and normalised-exact matching for entity resolution.
No framework dependencies — pure Python domain logic.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.domain.entities.menu_item import MenuItem

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLLAPSE_SPACE = re.compile(r"\s+")
_STRIP_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, NFC-normalise."""
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = _STRIP_PUNCT.sub(" ", text)
    text = _COLLAPSE_SPACE.sub(" ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def exact_match(text: str, candidates: list[MenuItem]) -> MenuItem | None:
    """
    Case-insensitive exact match against menu item names.

    Args:
        text: Raw user-supplied text.
        candidates: Pool of MenuItem objects to search within.

    Returns:
        The first candidate whose name matches exactly (case-insensitive),
        or ``None`` if no match found.
    """
    needle = text.strip().lower()
    for item in candidates:
        if item.name.lower() == needle:
            logger.debug(
                "entity_resolution.exact_match.hit",
                needle=needle,
                matched=item.name,
                item_id=item.id,
            )
            return item
    logger.debug("entity_resolution.exact_match.miss", needle=needle)
    return None


def normalized_match(text: str, candidates: list[MenuItem]) -> MenuItem | None:
    """
    Normalised exact match: strip punctuation, lowercase, collapse whitespace.

    This catches inputs such as ``"big  mac!"`` matching ``"Big Mac"``.

    Args:
        text: Raw user-supplied text.
        candidates: Pool of MenuItem objects.

    Returns:
        The first candidate whose normalised name equals the normalised input,
        or ``None`` if no match found.
    """
    needle = _normalise(text)
    if not needle:
        return None

    for item in candidates:
        if _normalise(item.name) == needle:
            logger.debug(
                "entity_resolution.normalized_match.hit",
                needle=needle,
                matched=item.name,
                item_id=item.id,
            )
            return item
    logger.debug("entity_resolution.normalized_match.miss", needle=needle)
    return None
