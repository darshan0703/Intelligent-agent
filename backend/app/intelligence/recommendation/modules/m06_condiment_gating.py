"""
Module 6: Condiment Host Gating (Phase 1 Hard Gate & Phase 3 Boost)
Dips / sauces require a finger-food host (Fries, Nuggets, Wings) in cart or anchor.
If host is absent -> dip candidates are dropped (0.0x).
If host is present -> dip candidates receive 1.5x boost.
"""
from typing import Dict, Any, List

FINGER_FOOD_KEYWORDS = {"fries", "nugget", "wing", "strip", "hashbrown", "puff"}
DIP_KEYWORDS = {"dip", "sauce", "mayo", "ketchup"}

def has_finger_food_host(cart: List[Dict[str, Any]], anchor_item: Dict[str, Any] | None) -> bool:
    pool = list(cart)
    if anchor_item:
        pool.append(anchor_item)

    for item in pool:
        name = str(item.get("name", "")).lower()
        if any(f in name for f in FINGER_FOOD_KEYWORDS):
            return True
    return False

def filter_or_boost_condiments(
    candidates: List[Dict[str, Any]],
    has_host: bool
) -> List[Dict[str, Any]]:
    results = []
    for item in candidates:
        name = str(item.get("name", "")).lower()
        is_dip = any(d in name for d in DIP_KEYWORDS)

        if is_dip:
            if not has_host:
                continue  # Drop condiment if no host present
            else:
                # Host present: apply 1.5x boost
                item_copy = dict(item)
                item_copy["score"] = item_copy.get("score", 1.0) * 1.5
                results.append(item_copy)
        else:
            results.append(item)

    return results
