"""
Module 10: Sensory Contrast (Phase 3 Culinary Logic)
Neuro-gastronomic biological counter-balance:
Spicy Main -> Cooling Dairy / Shakes (1.35x)
Rich / Cheesy Main -> Effervescent Carbonation (1.30x)
Crispy Main -> Refreshing Beverage (1.25x)
"""
from typing import Dict, Any

SPICY_KEYWORDS = {"spicy", "peri peri", "zesty", "fiery", "hot"}
COOLING_DAIRY_KEYWORDS = {"shake", "sundae", "softie", "float", "cold coffee"}

RICH_KEYWORDS = {"cheese", "paneer", "cheesy", "loaded", "double", "mayo"}
CARBONATION_KEYWORDS = {"coke", "fanta", "sprite", "fizz", "soda", "thums up"}

def score_sensory_contrast(
    candidate: Dict[str, Any],
    anchor_item: Dict[str, Any] | None
) -> float:
    if not anchor_item:
        return 1.0

    anchor_name = str(anchor_item.get("name", "")).lower()
    cand_name = str(candidate.get("name", "")).lower()

    # 1. Spicy -> Cooling Dairy
    if any(s in anchor_name for s in SPICY_KEYWORDS):
        if any(c in cand_name for c in COOLING_DAIRY_KEYWORDS):
            return 1.35

    # 2. Rich / Cheesy -> Carbonation Cut-Through
    if any(r in anchor_name for r in RICH_KEYWORDS):
        if any(c in cand_name for c in CARBONATION_KEYWORDS):
            return 1.30

    return 1.0
