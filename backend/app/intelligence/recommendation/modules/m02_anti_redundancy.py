"""
Module 2: Anti-Redundancy & Universal Overrides (Phase 3 Culinary Logic)
Prevents texture and ingredient fatigue (e.g. potato burger + potato hashbrown).
Universal sides (Fries, Nuggets) bypass penalty to protect core commercial combos.
"""
from typing import Dict, Any

UNIVERSAL_SIDES = {"fries", "peri peri fries", "saucy fries", "nuggets", "chicken nuggets"}

def get_base_ingredient(name: str) -> str:
    name_lower = name.lower()
    if any(k in name_lower for k in ["potato", "aloo", "veggie", "hashbrown"]):
        return "potato"
    if any(k in name_lower for k in ["paneer"]):
        return "paneer"
    if any(k in name_lower for k in ["chicken"]):
        return "chicken"
    if any(k in name_lower for k in ["mutton", "beef"]):
        return "meat"
    return "other"

def score_anti_redundancy(
    candidate: Dict[str, Any],
    anchor_item: Dict[str, Any] | None
) -> float:
    if not anchor_item:
        return 1.0

    cand_name = str(candidate.get("name", "")).lower()
    
    # Universal sides always bypass
    if any(u in cand_name for u in UNIVERSAL_SIDES):
        return 1.0

    anchor_base = get_base_ingredient(str(anchor_item.get("name", "")))
    cand_base = get_base_ingredient(cand_name)

    # Identical base ingredient redundancy penalty
    if anchor_base != "other" and anchor_base == cand_base:
        return 0.35

    return 1.0
