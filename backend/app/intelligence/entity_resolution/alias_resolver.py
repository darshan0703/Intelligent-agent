"""
app/intelligence/entity_resolution/alias_resolver.py

Alias-based entity resolution.  Aliases are loaded from a YAML config file
(``app/prompts/v1/domains/aliases.yaml``) and resolve common shorthand or
colloquial names to canonical menu-item names.

No framework imports — pure domain logic.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.domain.entities.menu_item import MenuItem

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_ALIASES_DIR = Path(__file__).parents[3] / "prompts" / "v1" / "domains"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLLAPSE_SPACE = re.compile(r"\s+")
_STRIP_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = _STRIP_PUNCT.sub(" ", text)
    return _COLLAPSE_SPACE.sub(" ", text).strip()


# ---------------------------------------------------------------------------
# Alias loading
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=32)
def load_aliases(domain: str = "default") -> dict[str, str]:
    """
    Load alias map for a given domain from YAML.

    The YAML file is expected at::

        app/prompts/v1/domains/<domain>_aliases.yaml

    Each entry maps an alias (key) to the canonical item name (value):

    .. code-block:: yaml

        aliases:
          bk burger: Burger King Burger
          whopper jr: Whopper Jr.
          large fries: Large French Fries

    If no domain-specific file is found, the ``default_aliases.yaml`` is
    attempted.  If neither exists, an empty dict is returned and a warning is
    logged — the resolver degrades gracefully.

    Args:
        domain: Domain identifier (e.g. ``"burger_king"``).

    Returns:
        Mapping of normalised alias -> canonical name.
    """
    try:
        import yaml  # PyYAML — optional dependency; only needed at runtime
    except ImportError:  # pragma: no cover
        logger.warning(
            "alias_resolver.yaml_not_installed",
            hint="Install PyYAML to enable alias loading",
        )
        return {}

    candidates = [
        _ALIASES_DIR / f"{domain}_aliases.yaml",
        _ALIASES_DIR / "default_aliases.yaml",
    ]

    for path in candidates:
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            raw: dict = data.get("aliases", {})
            normalised = {_normalise(k): v for k, v in raw.items() if k and v}
            logger.info(
                "alias_resolver.aliases_loaded",
                domain=domain,
                path=str(path),
                count=len(normalised),
            )
            return normalised

    logger.warning(
        "alias_resolver.no_file_found",
        domain=domain,
        searched=[str(p) for p in candidates],
    )
    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def alias_match(
    text: str,
    candidates: list[MenuItem],
    alias_map: dict[str, str],
) -> MenuItem | None:
    """
    Resolve *text* to a MenuItem via the alias map.

    Algorithm:
    1. Normalise the input text.
    2. Look up the normalised text in *alias_map* -> canonical name.
    3. Find a candidate whose normalised name equals the canonical name.

    Args:
        text:       Raw user-supplied text.
        candidates: Pool of MenuItem objects.
        alias_map:  Mapping of normalised alias -> canonical item name.

    Returns:
        Matched MenuItem, or ``None``.
    """
    if not alias_map:
        return None

    needle = _normalise(text)
    canonical = alias_map.get(needle)
    if canonical is None:
        logger.debug("alias_resolver.no_alias_entry", needle=needle)
        return None

    canonical_norm = _normalise(canonical)
    for item in candidates:
        if _normalise(item.name) == canonical_norm:
            logger.debug(
                "alias_resolver.hit",
                needle=needle,
                alias_canonical=canonical,
                matched=item.name,
                item_id=item.id,
            )
            return item

    logger.warning(
        "alias_resolver.canonical_not_in_candidates",
        needle=needle,
        canonical=canonical,
        hint="Alias file may reference a non-existent item name",
    )
    return None
