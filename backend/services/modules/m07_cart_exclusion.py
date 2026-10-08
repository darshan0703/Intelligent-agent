"""
Module 7: Absolute Cart Exclusion (Phase 1 Hard Gate)
Permanently drops candidates that are already present in the customer's cart,
matching by both item ID and normalized item name.
"""
from typing import Dict, Any, List, Set

def _normalize_name(name: Any) -> str:
    return str(name or "").strip().lower().replace("-", " ").replace("_", " ")

def exclude_cart_items(
    candidates: List[Dict[str, Any]],
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not cart:
        return candidates

    cart_ids: Set[Any] = set()
    cart_names: Set[str] = set()

    for item in cart:
        item_id = item.get("id")
        if item_id is not None:
            cart_ids.add(item_id)
            cart_ids.add(str(item_id))

        raw_name = item.get("name")
        if raw_name:
            norm_name = _normalize_name(raw_name)
            cart_names.add(norm_name)

            # Strip standard meal suffixes to catch base burger/item
            for suffix in [" regular meal", " medium meal", " large meal", " meal"]:
                if norm_name.endswith(suffix):
                    cart_names.add(norm_name[:-len(suffix)].strip())

        # Unpack composite meal components if present
        for comp_key in ("main_item", "burger", "side", "drink"):
            comp = item.get(comp_key)
            if isinstance(comp, dict):
                comp_id = comp.get("id")
                if comp_id is not None:
                    cart_ids.add(comp_id)
                    cart_ids.add(str(comp_id))
                comp_name = comp.get("name")
                if comp_name:
                    cart_names.add(_normalize_name(comp_name))

    survivors = []
    for cand in candidates:
        cand_id = cand.get("id")
        cand_name = _normalize_name(cand.get("name"))

        if cand_id is not None and (cand_id in cart_ids or str(cand_id) in cart_ids):
            continue
        if cand_name in cart_names:
            continue

        survivors.append(cand)

    return survivors
