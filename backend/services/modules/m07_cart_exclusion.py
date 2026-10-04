"""
Module 7: Absolute Cart Exclusion (Phase 1 Hard Gate)
Permanently drops candidates that are already present in the customer's cart,
matching by both item ID and normalized item name.
"""
from typing import Dict, Any, List, Set

def exclude_cart_items(
    candidates: List[Dict[str, Any]],
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not cart:
        return candidates

    cart_ids: Set[Any] = {item.get("id") for item in cart if item.get("id")}
    cart_names: Set[str] = {str(item.get("name", "")).strip().lower() for item in cart}

    survivors = []
    for cand in candidates:
        cand_id = cand.get("id")
        cand_name = str(cand.get("name", "")).strip().lower()

        if cand_id and cand_id in cart_ids:
            continue
        if cand_name in cart_names:
            continue

        survivors.append(cand)

    return survivors
