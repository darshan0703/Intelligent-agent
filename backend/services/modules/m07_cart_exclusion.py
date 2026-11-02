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
        if not isinstance(item, dict):
            continue

        item_id = item.get("id")
        if item_id is not None:
            cart_ids.add(item_id)
            cart_ids.add(str(item_id))

        raw_name = item.get("name")
        if raw_name:
            norm_name = _normalize_name(raw_name)
            if norm_name:
                cart_names.add(norm_name)
                for suffix in STANDARD_MEAL_SUFFIXES:
                    if norm_name.endswith(suffix):
                        base_name = norm_name[:-len(suffix)].strip()
                        if base_name:
                            cart_names.add(base_name)

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
                    norm_comp = _normalize_name(comp_name)
                    if norm_comp:
                        cart_names.add(norm_comp)

    return cart_ids, cart_names


def is_candidate_excluded(cand: Dict[str, Any], cart_ids: Set[Any], cart_names: Set[str]) -> bool:
    """O(1) check if a candidate matches any excluded ID or name."""
    if not cand or not isinstance(cand, dict):
        return False
    cand_id = cand.get("id")
    if cand_id is not None and (cand_id in cart_ids or str(cand_id) in cart_ids):
        return True
    cand_name = _normalize_name(cand.get("name"))
    return bool(cand_name and cand_name in cart_names)


def exclude_cart_items(
    candidates: List[Dict[str, Any]],
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not cart or not candidates:
        return candidates

    standalone_ids: Set[Any] = set()
    standalone_names: Set[str] = set()

    meal_burger_ids: Set[Any] = set()
    meal_burger_names: Set[str] = set()

    meal_side_ids: Set[Any] = set()
    meal_side_names: Set[str] = set()

    meal_drink_ids: Set[Any] = set()
    meal_drink_names: Set[str] = set()

    for item in cart:
        if not isinstance(item, dict):
            continue

        item_id = item.get("id")
        if item_id is not None:
            standalone_ids.add(item_id)
            standalone_ids.add(str(item_id))

        raw_name = item.get("name")
        if raw_name:
            norm_name = _normalize_name(raw_name)
            if norm_name:
                standalone_names.add(norm_name)

                for suffix in STANDARD_MEAL_SUFFIXES:
                    if norm_name.endswith(suffix):
                        base_name = norm_name[:-len(suffix)].strip()
                        if base_name:
                            standalone_names.add(base_name)
                            if item.get("type") == "meal":
                                meal_burger_names.add(base_name)

        if item.get("type") == "meal":
            for b_key in ("main_item", "burger"):
                comp = item.get(b_key)
                if isinstance(comp, dict):
                    comp_id = comp.get("id")
                    if comp_id is not None:
                        meal_burger_ids.add(comp_id)
                        meal_burger_ids.add(str(comp_id))
                    comp_name = comp.get("name")
                    if comp_name:
                        norm_cname = _normalize_name(comp_name)
                        if norm_cname:
                            meal_burger_names.add(norm_cname)

            side_comp = item.get("side")
            if isinstance(side_comp, dict):
                s_id = side_comp.get("id")
                if s_id is not None:
                    meal_side_ids.add(s_id)
                    meal_side_ids.add(str(s_id))
                s_name = side_comp.get("name")
                if s_name:
                    norm_sname = _normalize_name(s_name)
                    if norm_sname:
                        meal_side_names.add(norm_sname)

            drink_comp = item.get("drink")
            if isinstance(drink_comp, dict):
                d_id = drink_comp.get("id")
                if d_id is not None:
                    meal_drink_ids.add(d_id)
                    meal_drink_ids.add(str(d_id))
                d_name = drink_comp.get("name")
                if d_name:
                    norm_dname = _normalize_name(d_name)
                    if norm_dname:
                        meal_drink_names.add(norm_dname)

    survivors = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        cand_id = cand.get("id")
        cand_name = _normalize_name(cand.get("name"))

        cand_cat = str(cand.get("category") or "").strip().lower()
        cand_role = str(cand.get("meal_role") or "").strip().lower()

        relevant_ids = set(standalone_ids)
        relevant_names = set(standalone_names)

        if cand_cat in ("burger", "burgers") or cand_role == "main":
            relevant_ids.update(meal_burger_ids)
            relevant_names.update(meal_burger_names)
        elif cand_cat in ("side", "sides") or cand_role == "side":
            relevant_ids.update(meal_side_ids)
            relevant_names.update(meal_side_names)
        elif cand_cat in ("drink", "drinks") or cand_role == "drink":
            relevant_ids.update(meal_drink_ids)
            relevant_names.update(meal_drink_names)
        else:
            relevant_ids.update(meal_burger_ids)
            relevant_names.update(meal_burger_names)
            relevant_names.update(meal_side_names)
            relevant_names.update(meal_drink_names)

        if cand_id is not None and (cand_id in relevant_ids or str(cand_id) in relevant_ids):
            continue
        if cand_name in relevant_names:
            continue
        survivors.append(cand)

    return survivors
