"""
Module 1: Strict Dietary Lock (Phase 1 Hard Gate)
Eradicates non-veg items from candidate pool if customer has active veg preference
or if all items in cart are vegetarian.
"""
from typing import List, Dict, Any

def apply_dietary_lock(
    candidates: List[Dict[str, Any]],
    preference: str | None,
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    # Determine effective dietary preference
    eff_pref = (preference or "").lower().strip()
    
    # If no explicit preference, inspect cart: if all cart items are veg, lock to veg
    if not eff_pref and cart:
        has_items = len(cart) > 0
        all_veg = all("veg" in str(item.get("foodType") or item.get("food_type", "")).lower() and "non" not in str(item.get("foodType") or item.get("food_type", "")).lower() for item in cart)
        if has_items and all_veg:
            eff_pref = "veg"

    if eff_pref == "veg":
        survivors = []
        for item in candidates:
            ft = str(item.get("foodType") or item.get("food_type", "")).lower()
            # Must contain veg and NOT contain non
            if "veg" in ft and "non" not in ft:
                survivors.append(item)
        return survivors
    
    elif "non" in eff_pref:
        survivors = []
        for item in candidates:
            ft = str(item.get("foodType") or item.get("food_type", "")).lower()
            if "non" in ft:
                survivors.append(item)
        return survivors

    return candidates
