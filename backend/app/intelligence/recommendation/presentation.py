"""
app/intelligence/recommendation/presentation.py
Presentation Layer — v7 §24

Separates WHO makes the decision from WHO writes the words.

Recommendation Engine outputs: { item_id, score, evidence, sub_role, job_code }
This layer adds:             { image_url, price_display, badge_text }

The engine NEVER invents copy. Badge text comes from a badge_rules config keyed
by WHY the item was selected (reason_code), not hardcoded inside scoring functions.

This means:
  A UI copy change (marketing wants different wording) → ONLY this file changes.
  A ranking change (new signal added) → ONLY scoring.py changes.
  Two files change independently. No function does both jobs.

Badge reason codes (keyed in badge_rules table and BADGE_RULES below):
  top_score_in_slot  -> 'Best Match'
  bandit_exploration -> 'Try Something New'
  circadian_boost    -> 'Perfect Right Now'
  sensory_contrast   -> 'Great Pairing'
  co_purchase        -> 'Often Ordered Together'
  meal_completer     -> 'Complete Your Meal'
  budget_fit         -> 'Great Value'
  popularity         -> 'Customer Favourite'
  fallback_curated   -> 'Staff Pick'
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ── BADGE RULES (in-memory mirror of badge_rules table) ──────────────────────
# Structure: reason_code -> {badge_text, badge_icon, priority}
# Priority: higher number = shown preferentially when multiple reasons apply.

BADGE_RULES: dict[str, dict[str, Any]] = {
    "top_score_in_slot":  {"badge_text": "Best Match",            "badge_icon": "⭐", "priority": 10},
    "meal_completer":     {"badge_text": "Complete Your Meal",    "badge_icon": "🍽️", "priority": 10},
    "circadian_boost":    {"badge_text": "Perfect Right Now",     "badge_icon": "🕐", "priority": 8},
    "sensory_contrast":   {"badge_text": "Great Pairing",         "badge_icon": "🔥", "priority": 9},
    "co_purchase":        {"badge_text": "Often Ordered Together", "badge_icon": "👥", "priority": 7},
    "popularity":         {"badge_text": "Customer Favourite",    "badge_icon": "❤️", "priority": 7},
    "budget_fit":         {"badge_text": "Great Value",           "badge_icon": "💚", "priority": 6},
    "bandit_exploration": {"badge_text": "Try Something New",    "badge_icon": "✨", "priority": 5},
    "fallback_curated":   {"badge_text": "Staff Pick",           "badge_icon": "👨🍳", "priority": 4},
}


@dataclass
class RenderedItem:
    """
    The frontend contract for a recommendation item.
    Contains everything the UI needs — no ranking internals leak through.
    """
    id: int
    name: str
    price: float
    price_display: str          # e.g. '₹189'
    image: str
    short_description: str
    category: str
    food_type: str
    badge_text: str             # From badge_rules table
    badge_icon: str
    is_meal_available: bool
    # score and evidence are intentionally EXCLUDED — presentation layer
    # does not expose ranking internals to the frontend

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "price_display": self.price_display,
            "image": self.image,
            "short_description": self.short_description,
            "category": self.category,
            "food_type": self.food_type,
            "badge_text": self.badge_text,
            "badge_icon": self.badge_icon,
            "is_meal_available": self.is_meal_available,
        }


class PresentationLayer:
    """
    Reads from catalog MenuItem + badge_rules config.
    Transforms engine decision objects into frontend-renderable RenderedItems.
    No ranking logic here — this is purely a rendering concern.
    """

    @staticmethod
    def resolve_badge(reason_code: str) -> tuple[str, str]:
        """
        Returns (badge_text, badge_icon) for a given reason_code.
        Falls back to empty strings if no rule exists — never crashes.
        """
        rule = BADGE_RULES.get(reason_code, {})
        return rule.get("badge_text", ""), rule.get("badge_icon", "")

    @staticmethod
    def get_top_reason_code(
        score_breakdown: dict[str, float],
        source: str = "",
    ) -> str:
        """
        Determines the primary badge reason code for an item based on its score breakdown.
        The highest-contributing signal becomes the badge reason.
        This is a pure function — the same inputs always produce the same badge.
        """
        if not score_breakdown:
            return "popularity" if not source else source

        # Threshold-based reason assignment (ordered by priority)
        circadian = score_breakdown.get("circadian", 1.0)
        sensory = score_breakdown.get("sensory_contrast", 1.0)
        price_fit = score_breakdown.get("price_fit", 1.0)
        bandit = score_breakdown.get("bandit_theta", 0.33)

        if source == "co_purchase":
            return "co_purchase"
        if source == "exploration" or bandit > 0.65:
            return "bandit_exploration"
        if circadian > 1.15:
            return "circadian_boost"
        if sensory > 1.25:
            return "sensory_contrast"
        if price_fit > 0.85:
            return "budget_fit"
        if source == "popularity":
            return "popularity"
        return "top_score_in_slot"

    @classmethod
    def render(cls, catalog_item: Any, score_breakdown: dict[str, float] = None, source: str = "") -> RenderedItem:
        """
        Renders a single catalog MenuItem into a RenderedItem for the frontend.
        The score_breakdown informs badge selection but is NOT included in the output.
        """
        score_breakdown = score_breakdown or {}
        reason_code = cls.get_top_reason_code(score_breakdown, source)
        badge_text, badge_icon = cls.resolve_badge(reason_code)

        price_val = float(
            catalog_item.price.amount if hasattr(catalog_item.price, "amount") else catalog_item.price
        )

        food_type = str(
            catalog_item.food_type.value if hasattr(catalog_item.food_type, "value") else catalog_item.food_type or ""
        ).lower()

        category = str(
            catalog_item.category.value if hasattr(catalog_item.category, "value") else catalog_item.category or ""
        ).lower()

        return RenderedItem(
            id=catalog_item.id,
            name=catalog_item.name,
            price=price_val,
            price_display=f"\u20b9{price_val:.0f}",
            image=catalog_item.image or "",
            short_description=catalog_item.short_description or catalog_item.name,
            category=category,
            food_type=food_type,
            badge_text=badge_text,
            badge_icon=badge_icon,
            is_meal_available=bool(catalog_item.is_meal_available),
        )

    @classmethod
    def render_list(
        cls,
        items: list[Any],
        score_breakdowns: dict[int, dict[str, float]] | None = None,
        sources: dict[int, str] | None = None,
    ) -> list[RenderedItem]:
        """
        Renders a list of catalog MenuItems into RenderedItems.
        score_breakdowns and sources are keyed by item_id.
        """
        score_breakdowns = score_breakdowns or {}
        sources = sources or {}
        rendered = []
        for item in items:
            rendered.append(cls.render(
                catalog_item=item,
                score_breakdown=score_breakdowns.get(item.id, {}),
                source=sources.get(item.id, ""),
            ))
        return rendered
