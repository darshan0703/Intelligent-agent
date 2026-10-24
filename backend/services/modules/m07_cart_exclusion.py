"""
Module 7: Absolute Cart Exclusion (Phase 1 Hard Gate)
Permanently drops candidates that are already present in the customer's cart,
matching by both item ID and normalized item name.
"""
from typing import Dict, Any, List, Set, Tuple

STANDARD_MEAL_SUFFIXES = (" regular meal", " medium meal", " large meal", " meal")
COMPOSITE_KEYS = ("main_item", "burger", "side", "drink")


def _normalize_name(name: Any) -> str:
    return str(name or "").strip().lower().replace("-", " ").replace("_", " ")


def get_cart_exclusion_sets(cart: List[Dict[str, Any]]) -> Tuple[Set[Any], Set[str]]:
    """
    Extracts normalized ID and name sets from the active cart for O(1) exclusion lookups.
    """
    cart_ids: Set[Any] = set()
    cart_names: Set[str] = set()

    if not cart:
        return cart_ids, cart_names

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
            for suffix in STANDARD_MEAL_SUFFIXES:
                if norm_name.endswith(suffix):
                    cart_names.add(norm_name[:-len(suffix)].strip())

        # Unpack composite meal components if present
        for comp_key in COMPOSITE_KEYS:
            comp = item.get(comp_key)
            if isinstance(comp, dict):
                comp_id = comp.get("id")
                if comp_id is not None:
                    cart_ids.add(comp_id)
                    cart_ids.add(str(comp_id))
                comp_name = comp.get("name")
                if comp_name:
                    cart_names.add(_normalize_name(comp_name))

    return cart_ids, cart_names


def is_candidate_excluded(cand: Dict[str, Any], cart_ids: Set[Any], cart_names: Set[str]) -> bool:
    """O(1) check if a candidate matches any excluded ID or name."""
    if not cand:
        return False
    cand_id = cand.get("id")
    if cand_id is not None and (cand_id in cart_ids or str(cand_id) in cart_ids):
        return True
    return _normalize_name(cand.get("name")) in cart_names


def exclude_cart_items(
    candidates: List[Dict[str, Any]],
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not cart or not candidates:
        return candidates

    cart_ids, cart_names = get_cart_exclusion_sets(cart)
    return [
        cand for cand in candidates
        if not is_candidate_excluded(cand, cart_ids, cart_names)
    ]

