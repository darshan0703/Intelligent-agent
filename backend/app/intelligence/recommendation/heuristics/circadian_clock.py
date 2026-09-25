"""
app/intelligence/recommendation/heuristics/circadian_clock.py
Biological Contexting & Circadian Craving Multiplier
- Morning (6:00 - 11:30 AM): Boosts caffeine (Espresso, Latte, Coffee) and light breakfast snacks.
- Lunch & Dinner Rush (12:00 - 15:30, 19:00 - 22:00): Boosts high-protein hearty meals and complete combos.
- Afternoon (15:30 - 19:00): Boosts refreshing drinks, shakes, and finger sides.
- Late Night (22:00 - 5:00 AM): Prefrontal cortex fatigue -> Boosts high-sugar & high-fat comfort foods (Sundae, Choco Lava, KitKat Shakes, Double Patties).
"""
from __future__ import annotations
from datetime import datetime
from app.domain.catalog.entities import MenuItem


class CircadianCravingAnalyzer:
    @staticmethod
    def get_current_circadian_phase(hour: int | None = None) -> str:
        h = hour if hour is not None else datetime.now().hour
        if 6 <= h < 11:
            return "morning"
        elif 11 <= h < 15:
            return "lunch"
        elif 15 <= h < 19:
            return "afternoon_snack"
        elif 19 <= h < 22:
            return "dinner"
        else:
            return "late_night"

    @classmethod
    def evaluate_circadian_multiplier(
        cls,
        candidate_item: MenuItem,
        hour: int | None = None,
    ) -> tuple[float, str]:
        phase = cls.get_current_circadian_phase(hour)
        name = candidate_item.name.lower()
        cat = str(candidate_item.category.value if hasattr(candidate_item.category, "value") else candidate_item.category).lower()

        multiplier = 1.0
        reason = f"Standard {phase} baseline"

        if phase == "morning":
            # Boost caffeine and hot beverages
            if any(x in name for x in ["coffee", "latte", "cappuccino", "tea", "espresso"]):
                multiplier = 1.45
                reason = "Morning Circadian: High caffeine affinity"
            elif cat == "burger" and any(x in name for x in ["double", "whopper"]):
                multiplier = 0.80
                reason = "Morning Circadian: Downweight heavy double burgers before lunch"

        elif phase in ("lunch", "dinner"):
            # Boost hearty meals and burgers
            if cat == "burger" or candidate_item.is_meal_available:
                multiplier = 1.30
                reason = f"{phase.capitalize()} Rush: High protein meal affinity"

        elif phase == "afternoon_snack":
            # Boost light finger foods, shakes, and fries
            if cat in ("side", "drink") or any(x in name for x in ["fries", "shake", "nuggets", "strips"]):
                multiplier = 1.35
                reason = "Afternoon Snack: High finger-food & shake affinity"

        elif phase == "late_night":
            # Impulse comfort cravings (high fat / high sugar)
            if cat == "dessert" or any(x in name for x in ["choco", "lava", "sundae", "shake", "double", "cheese", "peri peri"]):
                multiplier = 1.50
                reason = "Late-Night Circadian: Peak impulse comfort & sweet craving"

        return multiplier, reason
