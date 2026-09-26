"""
Module 4: Dining Pillars & Dual-Role Saturation (Phase 1 Hard Gate)
Tracks meal pillars: Main, Side, Drink, Dessert.
A Shake, Frappe, or Float simultaneously satisfies both Drink and Dessert pillars.
"""
from typing import Dict, Any, List, Set

DUAL_ROLE_KEYWORDS = {"shake", "thick shake", "frappe", "float", "smoothie"}

def get_fulfilled_pillars(cart: List[Dict[str, Any]]) -> Set[str]:
    fulfilled: Set[str] = set()
    for item in cart:
        name = str(item.get("name", "")).lower()
        cat = str(item.get("category", "")).lower()

        if "burger" in cat or "wrap" in cat:
            fulfilled.add("main")
        elif "side" in cat or "fries" in cat or "nugget" in cat:
            fulfilled.add("side")
        elif "drink" in cat or "beverage" in cat:
            fulfilled.add("drink")
        elif "dessert" in cat or "sundae" in cat:
            fulfilled.add("dessert")

        # Dual-role check
        if any(d in name for d in DUAL_ROLE_KEYWORDS):
            fulfilled.add("drink")
            fulfilled.add("dessert")

    return fulfilled

def filter_saturated_candidates(
    candidates: List[Dict[str, Any]],
    fulfilled_pillars: Set[str]
) -> List[Dict[str, Any]]:
    # In checkout drawer, if dessert and drink are both fulfilled, don't show sweet drinks or desserts
    if "drink" in fulfilled_pillars and "dessert" in fulfilled_pillars:
        survivors = []
        for item in candidates:
            cat = str(item.get("category", "")).lower()
            name = str(item.get("name", "")).lower()
            is_dessert_or_sweet_drink = "dessert" in cat or any(d in name for d in DUAL_ROLE_KEYWORDS)
            if not is_dessert_or_sweet_drink:
                survivors.append(item)
        return survivors if survivors else candidates

    return candidates
