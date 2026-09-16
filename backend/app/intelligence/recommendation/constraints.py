"""
app/intelligence/recommendation/constraints.py
Deterministic hard constraints filter.
Filters out items that violate stock, dietary preferences, or explicit rejections.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.session.entities import SessionState


class ConstraintFilter:
    def filter_candidates(
        self,
        candidates: list[MenuItem],
        session: SessionState,
        rejected_item_ids: set[int] | None = None,
    ) -> list[MenuItem]:
        rejected = rejected_item_ids or set()
        valid: list[MenuItem] = []

        for item in candidates:
            if not item.is_available:
                continue
            if item.inventory and item.inventory.stock <= 0:
                continue
            if item.id in rejected:
                continue

            if session.food_preference:
                pref = session.food_preference.lower()
                food_type = str(item.food_type).lower() if item.food_type else ""
                if pref == "veg" and "non" in food_type:
                    continue
                if pref in ("non_veg", "non veg") and food_type == "veg":
                    continue

            valid.append(item)
        return valid
