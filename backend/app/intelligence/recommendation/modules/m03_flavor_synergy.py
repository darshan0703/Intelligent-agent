"""
Module 3: Flavor Anti-Clash & Regional Cuisine Synergy (Phase 3 Culinary Logic)
Prevents clashing or overwhelming same-flavor profiles (Mango + Mango = 0.25x).
Boosts regional flavor pairings (Makhani / Paneer + Masala = 1.5x).
"""
from typing import Dict, Any, List

def score_flavor_synergy(
    candidate: Dict[str, Any],
    anchor_item: Dict[str, Any] | None,
    cart: List[Dict[str, Any]]
) -> float:
    cand_name = str(candidate.get("name", "")).lower()
    
    # 1. Flavor Anti-Clash
    cart_names = [str(item.get("name", "")).lower() for item in cart]
    if anchor_item:
        cart_names.append(str(anchor_item.get("name", "")).lower())

    flavor_tags = ["mango", "chocolate", "strawberry", "vanilla", "berry"]
    for tag in flavor_tags:
        if tag in cand_name and any(tag in c for c in cart_names):
            return 0.25

    # 2. Regional Cuisine Synergy
    if anchor_item:
        anchor_name = str(anchor_item.get("name", "")).lower()
        regional_anchors = ["makhani", "paneer", "tandoor", "desi"]
        if any(r in anchor_name for r in regional_anchors) and "masala" in cand_name:
            return 1.50

    return 1.0
