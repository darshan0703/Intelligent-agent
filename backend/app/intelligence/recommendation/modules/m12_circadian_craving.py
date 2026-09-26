"""
Module 12: Circadian Craving Analyzer (Phase 3 Heuristics)
Biases candidate scoring based on meal hours:
Morning (6-11): Coffee & Breakfast Sides (1.25x)
Lunch (11-16): Mains & Burger Meals (1.20x)
Evening (16-20): Finger Foods & Snack Sides (1.20x)
Late Night (20-4): Desserts & Indulgent Shakes (1.25x)
"""
from datetime import datetime
from typing import Dict, Any

def score_circadian_craving(
    candidate: Dict[str, Any],
    hour: int | None = None
) -> float:
    current_hour = hour if hour is not None else datetime.now().hour
    cat = str(candidate.get("category", "")).lower()
    name = str(candidate.get("name", "")).lower()

    # Morning
    if 6 <= current_hour < 11:
        if "coffee" in name or "hashbrown" in name:
            return 1.25

    # Lunch
    elif 11 <= current_hour < 16:
        if "burger" in cat or "whopper" in name:
            return 1.20

    # Evening
    elif 16 <= current_hour < 20:
        if "side" in cat or "fries" in name or "nugget" in name:
            return 1.20

    # Late Night
    else:
        if "dessert" in cat or "shake" in name or "sundae" in name:
            return 1.25

    return 1.0
