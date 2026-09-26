"""
Module 8: Gatekeeper Kill-Switch (Phase 1 Hard Gate)
If all 4 dining pillars (Main, Side, Drink, Dessert) are fulfilled in the cart,
the basket is complete. Suppresses invasive trays to prevent checkout friction.
"""
from typing import Dict, Any, List, Set

def should_kill_recommendations(fulfilled_pillars: Set[str]) -> bool:
    required = {"main", "side", "drink", "dessert"}
    return required.issubset(fulfilled_pillars)

def apply_gatekeeper_killswitch(
    candidates: List[Dict[str, Any]],
    fulfilled_pillars: Set[str]
) -> List[Dict[str, Any]]:
    if should_kill_recommendations(fulfilled_pillars):
        # Basket is 100% complete — return empty list to protect smooth checkout
        return []
    return candidates
