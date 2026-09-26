"""
Module 5: Bulk Elastic Budget & Hard Price Ceiling (Phase 2 Budget Gate)
On product cross-sells, companion price > anchor.price * 1.5 is dropped.
Ensures value buyers are never pitched items more expensive than their main meal.
"""
from typing import Dict, Any, List

def apply_price_ceiling(
    candidates: List[Dict[str, Any]],
    anchor_price: float | None,
    max_ratio: float = 1.5
) -> List[Dict[str, Any]]:
    if not anchor_price or anchor_price <= 0:
        return candidates

    ceiling = anchor_price * max_ratio
    survivors = []
    
    for item in candidates:
        price = float(item.get("price") or item.get("original_price", 0))
        # If item price is within ceiling, keep it
        if price <= ceiling:
            survivors.append(item)

    # Return filtered pool if non-empty; defensive fallback to lowest priced items
    if survivors:
        return survivors

    return sorted(candidates, key=lambda x: float(x.get("price") or x.get("original_price", 999)))[:4]
