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
            standalone_names.add(norm_name)

            # Strip standard meal suffixes to catch base burger/item
            for suffix in [" regular meal", " medium meal", " large meal", " meal"]:
                if norm_name.endswith(suffix):
                    base_name = norm_name[:-len(suffix)].strip()
                    standalone_names.add(base_name)
                    if item.get("type") == "meal":
                        meal_burger_names.add(base_name)

        # Unpack composite meal components if present
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
                        meal_burger_names.add(_normalize_name(comp_name))

            side_comp = item.get("side")
            if isinstance(side_comp, dict):
                s_id = side_comp.get("id")
                if s_id is not None:
                    meal_side_ids.add(s_id)
                    meal_side_ids.add(str(s_id))
                s_name = side_comp.get("name")
                if s_name:
                    meal_side_names.add(_normalize_name(s_name))

            drink_comp = item.get("drink")
            if isinstance(drink_comp, dict):
                d_id = drink_comp.get("id")
                if d_id is not None:
                    meal_drink_ids.add(d_id)
                    meal_drink_ids.add(str(d_id))
                d_name = drink_comp.get("name")
                if d_name:
                    meal_drink_names.add(_normalize_name(d_name))

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
            # Fallback for candidates without category/role metadata:
            # Standalone items and meal main items (burgers) are primary products.
            # Meal side and drink IDs are excluded to prevent accidental ID collisions.
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
