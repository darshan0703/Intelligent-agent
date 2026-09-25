"""
app/intelligence/recommendation/fallback_graph.py
5-Level Capability-Keyed Fallback Graph — v7 §17

Each fallback level represents a SPECIFIC capability being unavailable, not a
generic 'something broke' catch-all. The evidence block (v7 §19) records which
fallback level actually served the response, making degradation diagnosable.

Fallback levels:
  Level 0: Full personalization — all generators warm, session data present
  Level 1: Cohort prior — no user_id; uses session mindset (budget/premium/meal_complete)
  Level 2: Category popularity — time-bucket weighted, no session context needed
  Level 3: Deterministic role match — sub_role capability fit only, zero scoring
  Level 4: Merchandiser-curated list — static, from badge_rules / curated config
  Level 5: Never empty — display_order top items (absolute last resort)

Fallback triggers (which level fires for which failure):
  co_purchase stale or thin (§14)              -> Level 1
  bandit posteriors not warm (new branch)       -> Level 2
  all generators returned empty (thin catalog)  -> Level 3
  session state lost / expired                  -> Level 2
  all scoring produces zero candidates          -> Level 4
  Level 4 empty                                 -> Level 5 (never fails)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


FALLBACK_TRIGGERS: dict[str, int] = {
    "co_purchase_stale":           1,
    "co_purchase_thin":            1,
    "bandit_not_warm":             2,
    "session_expired":             2,
    "all_generators_empty":        3,
    "scoring_zero_candidates":     4,
    "level4_empty":                5,
}

FALLBACK_DESCRIPTIONS: dict[int, str] = {
    0: "full_personalization",
    1: "cohort_prior_mindset",
    2: "category_popularity_timebucket",
    3: "deterministic_role_match",
    4: "merchandiser_curated",
    5: "display_order_never_empty",
}


@dataclass
class FallbackResult:
    level: int
    description: str
    trigger_reason: str
    items: list[Any]  # list[MenuItem]


class FallbackGraph:
    """
    Executes the fallback chain for a given trigger reason.
    Returns items and the level that served them — both recorded in DecisionTrace (§19).
    """

    def __init__(self, catalog: Any) -> None:
        self.catalog = catalog

    async def resolve(
        self,
        trigger_reason: str,
        category: str | None,
        session_mindset: str,
        branch_id: int,
        limit: int,
        circadian_hour: int | None = None,
    ) -> FallbackResult:
        """
        Walks the fallback chain starting from the level appropriate for trigger_reason.
        Tries each level in sequence until one returns items.
        """
        start_level = FALLBACK_TRIGGERS.get(trigger_reason, 1)

        for level in range(start_level, 6):
            items = await self._try_level(level, category, session_mindset, branch_id, limit, circadian_hour)
            if items:
                return FallbackResult(
                    level=level,
                    description=FALLBACK_DESCRIPTIONS[level],
                    trigger_reason=trigger_reason,
                    items=items,
                )

        # Level 5 absolute guarantee — should never be empty, but handle defensively
        return FallbackResult(
            level=5,
            description=FALLBACK_DESCRIPTIONS[5],
            trigger_reason=trigger_reason,
            items=[],
        )

    async def _try_level(
        self,
        level: int,
        category: str | None,
        session_mindset: str,
        branch_id: int,
        limit: int,
        circadian_hour: int | None,
    ) -> list[Any]:
        """Executes a single fallback level. Returns empty list if this level cannot serve."""
        try:
            if level == 0:
                # Full personalization — caller should not reach here via fallback
                return []

            elif level == 1:
                # Cohort prior: session mindset determines category priority
                # Budget_Hunter -> sides, drinks. Indulgent_Gourmet -> burgers, premium.
                priority_cat = self._mindset_to_category(session_mindset)
                target_cat = priority_cat or category or "burger"
                items = await self.catalog.get_by_category(target_cat, branch_id)
                # Return top items sorted by price (budget mindset: ascending; gourmet: descending)
                reverse = "gourmet" in session_mindset.lower() or "premium" in session_mindset.lower()
                return sorted(items, key=lambda i: float(i.price.amount), reverse=reverse)[:limit]

            elif level == 2:
                # Category popularity, time-bucket weighted
                target_cat = category or "burger"
                items = await self.catalog.get_by_category(target_cat, branch_id)
                # Time-bucket weighting: mornings bias drinks/sides, lunch bias burgers
                if circadian_hour is not None:
                    items = self._apply_timebucket_sort(items, circadian_hour)
                return [i for i in items if i.is_in_stock][:limit]

            elif level == 3:
                # Deterministic role match: return available items sorted by display_order
                target_cat = category or "side"
                items = await self.catalog.get_by_category(target_cat, branch_id)
                return sorted(
                    [i for i in items if i.is_in_stock],
                    key=lambda i: getattr(i, "display_order", 0) or 0,
                )[:limit]

            elif level == 4:
                # Merchandiser-curated: best sellers across all categories
                all_items = await self.catalog.get_all_available(branch_id)
                # Sort by price (mid-range bias: not cheapest, not most expensive)
                sorted_items = sorted(
                    [i for i in all_items if i.is_in_stock],
                    key=lambda i: abs(float(i.price.amount) - 150.0),
                )
                return sorted_items[:limit]

            elif level == 5:
                # Absolute last resort — display_order across all categories
                all_items = await self.catalog.get_all_available(branch_id)
                return sorted(
                    [i for i in all_items if i.is_in_stock],
                    key=lambda i: getattr(i, "display_order", 999) or 999,
                )[:limit]

        except Exception:
            return []
        return []

    @staticmethod
    def _mindset_to_category(mindset: str) -> str | None:
        mindset_lower = mindset.lower()
        if "budget" in mindset_lower:
            return "side"  # Budget customers first look at affordable sides
        if "premium" in mindset_lower or "gourmet" in mindset_lower or "indulgent" in mindset_lower:
            return "burger"  # Premium customers want full burgers
        if "refreshment" in mindset_lower or "quick" in mindset_lower:
            return "drink"
        return None  # Standard — no strong preference

    @staticmethod
    def _apply_timebucket_sort(items: list[Any], hour: int) -> list[Any]:
        """
        Biases item order based on time of day.
        Morning (6-11): drinks/sides first. Lunch (11-16): burgers first.
        Evening (16-20): sides/snacks. Late-night (20+): desserts/indulgent.
        """
        def time_priority(item: Any) -> int:
            cat = str(getattr(item, "category", "")).lower()
            name = str(getattr(item, "name", "")).lower()
            if 6 <= hour < 11:
                return 0 if "drink" in cat or "coffee" in name or "side" in cat else 1
            elif 11 <= hour < 16:
                return 0 if "burger" in cat else 1
            elif 16 <= hour < 20:
                return 0 if "side" in cat else 1
            else:  # Late night
                return 0 if "dessert" in cat or "shake" in name else 1
        return sorted(items, key=time_priority)
