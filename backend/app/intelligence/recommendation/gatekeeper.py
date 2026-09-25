"""
app/intelligence/recommendation/gatekeeper.py
Calibrated Gatekeeper & Edge Case Manager (v4 Specification).

Enforces:
1. Calibrated Confidence Floor (§6):
   if top_candidate.score < GATEKEEPER_FLOOR:
       show nothing  # silence beats a bad recommendation
2. Edge Cases (§7):
   - Zero eligible candidates: triggers fallback to unpersonalized category top-seller
   - Cold session: personalization signals default to None (not zero)
   - Dismissed / removed items: hard-suppression for session lifetime
"""
from __future__ import annotations
from typing import Any, Optional
from app.domain.catalog.entities import MenuItem


class Gatekeeper:
    """Multi-signal evaluation gate enforcing silence policy & v4 edge cases."""

    DEFAULT_CONFIDENCE_FLOOR = 0.15
    MAX_SESSION_DISMISSALS = 5

    @classmethod
    def should_silence(
        cls,
        candidate_count: int,
        top_score: float,
        session_dismissals: int,
        confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
    ) -> tuple[bool, str]:
        """
        Evaluates whether recommendations should be silenced.
        Returns: (should_silence: bool, reason: str)
        """
        # Excessive dismissal / fatigue
        if session_dismissals >= cls.MAX_SESSION_DISMISSALS:
            return True, f"session_fatigued ({session_dismissals} dismissals)"

        # Calibrated score floor check
        if candidate_count > 0 and top_score < confidence_floor:
            return True, f"low_confidence_score ({top_score:.3f} < {confidence_floor})"

        return False, "approved"

    @classmethod
    def handle_zero_candidates_fallback(
        cls,
        available_catalog_items: list[MenuItem],
        requested_count: int = 3,
        limit: Optional[int] = None,
    ) -> list[MenuItem]:
        """
        v4 §7 Edge Case: Zero eligible candidates after filters.
        Falls back to category top-seller (unpersonalized) rather than an empty broken screen.
        """
        count = limit if limit is not None else requested_count
        if not available_catalog_items:
            return []
        # Return popular items by display_order / stock availability, enforcing category uniqueness (one per role)
        sorted_by_popularity = sorted(
            [i for i in available_catalog_items if i.is_in_stock],
            key=lambda x: getattr(x, "display_order", 0) or 0,
        )
        selected = []
        seen_cats = set()
        for item in sorted_by_popularity:
            cat = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
            if cat not in seen_cats:
                seen_cats.add(cat)
                selected.append(item)
                if len(selected) >= count:
                    break
        return selected
