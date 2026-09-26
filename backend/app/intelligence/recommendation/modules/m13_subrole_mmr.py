"""
Module 13: Sub-Role MMR Diversity & Anti-Gamification (Phase 4 Diversity)
Part A: Anti-Gamification guarantees offer_price == original_price (zero fake discounts).
Part B: Sub-Role MMR ensures diversity so top slots don't collapse into multiple near-identical items (e.g. 2 thick shakes).
"""
from typing import Dict, Any, List

def get_subrole(item: Dict[str, Any]) -> str:
    name = str(item.get("name", "")).lower()
    if any(k in name for k in ["shake", "frappe"]):
        return "shake"
    if any(k in name for k in ["coffee", "latte", "cappuccino"]):
        return "coffee"
    if any(k in name for k in ["coke", "sprite", "fanta", "fizz", "soda"]):
        return "soda"
    if any(k in name for k in ["fries"]):
        return "fries"
    if any(k in name for k in ["nugget", "wing"]):
        return "finger_chicken"
    if any(k in name for k in ["sundae", "softie", "mousse"]):
        return "ice_cream"
    return "general"

def rerank_subrole_diversity(
    candidates: List[Dict[str, Any]],
    top_k: int = 8
) -> List[Dict[str, Any]]:
    # Anti-gamification enforcement
    for item in candidates:
        if "original_price" in item:
            item["price"] = item["original_price"]

    if not candidates:
        return []

    selected: List[Dict[str, Any]] = []
    seen_subroles = set()
    deferred: List[Dict[str, Any]] = []

    # First pass: pick highest scoring distinct subroles
    for item in candidates:
        sr = get_subrole(item)
        if sr not in seen_subroles and len(selected) < top_k:
            seen_subroles.add(sr)
            selected.append(item)
        else:
            deferred.append(item)

    # Second pass: fill remaining slots with remaining scored items
    for item in deferred:
        if len(selected) < top_k:
            selected.append(item)

    return selected
