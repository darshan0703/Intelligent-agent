"""
app/intelligence/entity_resolution/resolver.py

Multi-tier cascade entity resolver for TheAtom.

Resolution cascade (in order):
  1. Exact match (case-insensitive)
  2. Normalised exact match (strip punctuation, collapse whitespace)
  3. Alias lookup (YAML config)
  4. Fuzzy match (rapidfuzz, jaro-winkler + token_sort_ratio blend)
  5. Semantic match (embedding cosine similarity)
  6. Return None — never invent an item

Each tier logs why it succeeded or was skipped, providing full observability
of the resolution decision.

No framework imports — pure domain logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from app.intelligence.entity_resolution.alias_resolver import alias_match, load_aliases
from app.intelligence.entity_resolution.exact_resolver import exact_match, normalized_match
from app.intelligence.entity_resolution.fuzzy_resolver import fuzzy_match
from app.intelligence.entity_resolution.semantic_resolver import EmbeddingPort, SemanticResolver
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.domain.entities.menu_item import MenuItem

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Resolution method literals
# ---------------------------------------------------------------------------

ResolutionMethod = Literal[
    "exact",
    "normalized",
    "alias",
    "fuzzy",
    "semantic",
    "none",
]

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntityResolutionResult:
    """
    Outcome of a single entity resolution attempt.

    Attributes:
        matched_item: The resolved MenuItem, or ``None`` if unresolved.
        confidence:   Float in [0, 1]; 1.0 for exact/alias, blended for fuzzy/semantic.
        method:       Which tier resolved (or ``"none"``).
        alternatives: Other candidates that scored close to the threshold.
    """

    matched_item: MenuItem | None
    confidence: float
    method: ResolutionMethod
    alternatives: list[MenuItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cascade resolver
# ---------------------------------------------------------------------------


class EntityResolver:
    """
    Multi-tier cascade resolver.

    Inject a :class:`SemanticResolver` instance to enable the semantic tier.
    Without it, the cascade stops at fuzzy matching.

    Args:
        fuzzy_threshold:    Minimum blended score for fuzzy acceptance (0-1).
        semantic_threshold: Minimum cosine similarity for semantic acceptance (0-1).
        semantic_resolver:  Optional pre-warmed semantic resolver.
        alias_domain:       Domain key for alias YAML loading.
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.82,
        semantic_threshold: float = 0.75,
        semantic_resolver: SemanticResolver | None = None,
        alias_domain: str = "default",
    ) -> None:
        self._fuzzy_threshold = fuzzy_threshold
        self._semantic_threshold = semantic_threshold
        self._semantic_resolver = semantic_resolver
        self._alias_domain = alias_domain
        # Alias map is loaded once per domain (lru_cached in alias_resolver)
        self._alias_map: dict[str, str] = load_aliases(alias_domain)

    async def resolve(
        self,
        text: str,
        candidates: list[MenuItem],
        method_override: ResolutionMethod | None = None,
    ) -> EntityResolutionResult:
        """
        Resolve *text* to the best-matching MenuItem from *candidates*.

        Args:
            text:            Raw user input to match.
            candidates:      Pool of eligible MenuItem objects.
            method_override: Skip cascade and use a specific tier directly.
                             Useful for testing or forced resolution.

        Returns:
            :class:`EntityResolutionResult` — always returns an object;
            check ``matched_item is None`` to detect failure.
        """
        if not text or not candidates:
            return EntityResolutionResult(
                matched_item=None,
                confidence=0.0,
                method="none",
            )

        log = logger.bind(query=text, candidate_count=len(candidates))

        # ------------------------------------------------------------------
        # Tier 1: Exact match
        # ------------------------------------------------------------------
        if method_override in (None, "exact"):
            item = exact_match(text, candidates)
            if item is not None:
                log.info("entity_resolver.resolved", tier="exact", matched=item.name)
                return EntityResolutionResult(
                    matched_item=item,
                    confidence=1.0,
                    method="exact",
                )
            if method_override == "exact":
                return EntityResolutionResult(matched_item=None, confidence=0.0, method="none")

        # ------------------------------------------------------------------
        # Tier 2: Normalised exact match
        # ------------------------------------------------------------------
        if method_override in (None, "normalized"):
            item = normalized_match(text, candidates)
            if item is not None:
                log.info("entity_resolver.resolved", tier="normalized", matched=item.name)
                return EntityResolutionResult(
                    matched_item=item,
                    confidence=0.98,
                    method="normalized",
                )
            if method_override == "normalized":
                return EntityResolutionResult(matched_item=None, confidence=0.0, method="none")

        # ------------------------------------------------------------------
        # Tier 3: Alias lookup
        # ------------------------------------------------------------------
        if method_override in (None, "alias"):
            item = alias_match(text, candidates, self._alias_map)
            if item is not None:
                log.info("entity_resolver.resolved", tier="alias", matched=item.name)
                return EntityResolutionResult(
                    matched_item=item,
                    confidence=0.95,
                    method="alias",
                )
            if method_override == "alias":
                return EntityResolutionResult(matched_item=None, confidence=0.0, method="none")

        # ------------------------------------------------------------------
        # Tier 4: Fuzzy match
        # ------------------------------------------------------------------
        if method_override in (None, "fuzzy"):
            item, confidence = fuzzy_match(text, candidates, self._fuzzy_threshold)
            if item is not None:
                log.info(
                    "entity_resolver.resolved",
                    tier="fuzzy",
                    matched=item.name,
                    confidence=round(confidence, 4),
                )
                return EntityResolutionResult(
                    matched_item=item,
                    confidence=confidence,
                    method="fuzzy",
                )
            if method_override == "fuzzy":
                return EntityResolutionResult(matched_item=None, confidence=0.0, method="none")

        # ------------------------------------------------------------------
        # Tier 5: Semantic match
        # ------------------------------------------------------------------
        if method_override in (None, "semantic") and self._semantic_resolver is not None:
            item, confidence = await self._semantic_resolver.semantic_match(
                text, candidates, self._semantic_threshold
            )
            if item is not None:
                log.info(
                    "entity_resolver.resolved",
                    tier="semantic",
                    matched=item.name,
                    confidence=round(confidence, 4),
                )
                # Collect near-miss alternatives for UX ("Did you mean?")
                alternatives = await self._collect_alternatives(
                    text, candidates, item, threshold=self._semantic_threshold * 0.9
                )
                return EntityResolutionResult(
                    matched_item=item,
                    confidence=confidence,
                    method="semantic",
                    alternatives=alternatives,
                )

        # ------------------------------------------------------------------
        # Tier 6: Unresolved — never invent
        # ------------------------------------------------------------------
        log.info("entity_resolver.unresolved", query=text)
        return EntityResolutionResult(
            matched_item=None,
            confidence=0.0,
            method="none",
        )

    async def _collect_alternatives(
        self,
        text: str,
        candidates: list[MenuItem],
        best: MenuItem,
        threshold: float,
    ) -> list[MenuItem]:
        """Return up to 3 near-miss candidates for ''Did you mean?'' UX."""
        if self._semantic_resolver is None:
            return []
        others = [c for c in candidates if c.id != best.id]
        result: list[MenuItem] = []
        for item in others:
            _, sim = await self._semantic_resolver.semantic_match(text, [item], threshold=0.0)
            if sim >= threshold:
                result.append(item)
            if len(result) >= 3:
                break
        return result
