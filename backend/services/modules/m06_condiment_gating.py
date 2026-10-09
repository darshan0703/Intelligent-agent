"""
Module 6: Condiment Host Gating (Metadata-Driven V3)

Rules:
1. MEAL-ONLY ITEMS (is_meal_only == True):
   These items are database-level meal components and must never surface
   as standalone recommendations. Fallback: price == 0 if metadata missing.

2. CONDIMENTS / DIPS (section == "Dips"):
   Condiments belong strictly to the checkout page suggestions.
   Always dropped from the 4-card recommendation pages (product, category, etc.).
   Surfaced separately via the /cart/checkout-suggestions endpoint.

3. SIDE HOSTS (category == "side", not a condiment):
   Condiment recommendations are contextually triggered when the customer has
   a side item in their cart (either standalone or within a combo meal).
"""
from typing import Dict, Any, List


def is_meal_only_item(item: Dict[str, Any]) -> bool:
    """
    Returns True if the item is a meal-only component.
    Primary source of truth: item['is_meal_only'] boolean metadata from database.
    Robust against boolean, string-boolean ('true'/'false'/'t'/'f'/'1'/'0'), and integer values.
    Fallback: price == 0 if is_meal_only metadata is absent (None).
    Do not treat arbitrary zero-priced products as meal-only when explicit metadata says False.
    """
    if not isinstance(item, dict):
        return False

    val = item.get("is_meal_only")
    if val is not None:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("true", "t", "1", "yes"):
                return True
            if s in ("false", "f", "0", "no"):
                return False

    raw_price = item.get("price")
    if raw_price is None:
        raw_price = item.get("original_price")
    try:
        return float(raw_price) == 0.0
    except (TypeError, ValueError):
        return False


def is_condiment(item: Dict[str, Any]) -> bool:
    """
    Returns True if item is a dip / sauce / condiment based on canonical database metadata.
    In the database, condiments reside in the 'Dips' section under sides.
    Zero product name heuristics or keyword substring searching.
    """
    if not isinstance(item, dict):
        return False
    section = str(item.get("section") or "").strip().lower()
    return section == "dips"


def is_side_item(item: Dict[str, Any], is_nested_meal: bool = False) -> bool:
    """
    Returns True if item is a host side dish (e.g. Fries, Nuggets, Veggie Strips).
    A condiment itself (section == 'dips') does NOT count as a host side.
    Canonical source: category in ('side', 'sides').
    Fallback: meal_role == 'side' used only when necessary for nested meal semantics.
    """
    if not isinstance(item, dict):
        return False
    if is_condiment(item):
        return False

    cat = str(item.get("category") or "").strip().lower()
    if cat in ("side", "sides"):
        return True

    if is_nested_meal:
        role = str(item.get("meal_role") or "").strip().lower()
        if role == "side":
            return True

    return False


def has_side_in_cart(cart: List[Dict[str, Any]]) -> bool:
    """
    Returns True if cart contains any side dish host item (Fries, Nuggets, etc.).
    Inspects:
      1. Standalone cart items (category == 'side' / 'sides')
      2. Composite meal items with a nested 'side' dictionary
    Condiments themselves (section == 'dips') do NOT count as side hosts.
    """
    if not cart or not isinstance(cart, list):
        return False

    for item in cart:
        if not isinstance(item, dict):
            continue
        if is_side_item(item, is_nested_meal=False):
            return True
        side = item.get("side")
        if isinstance(side, dict) and is_side_item(side, is_nested_meal=True):
            return True

    return False


def has_condiment_in_cart(cart: List[Dict[str, Any]]) -> bool:
    """
    Returns True if cart already contains a dip / condiment.
    Inspects:
      1. Standalone cart items
      2. Composite meal items with a nested 'side' dictionary
    """
    if not cart or not isinstance(cart, list):
        return False

    for item in cart:
        if not isinstance(item, dict):
            continue
        if is_condiment(item):
            return True
        side = item.get("side")
        if isinstance(side, dict) and is_condiment(side):
            return True

    return False


# Backward compatibility aliases for existing callers
has_finger_food_in_cart = has_side_in_cart
has_dip_in_cart = has_condiment_in_cart


def filter_for_recommendation_page(
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Hard gate for all 4-card recommendation pages (product page, category page, etc.).
    Drops:
      - Meal-only items (is_meal_only == True or fallback price == 0)
      - All condiments / dips (those belong only on checkout suggestions)
    """
    if not candidates:
        return []
    return [
        item for item in candidates
        if not is_meal_only_item(item) and not is_condiment(item)
    ]


def get_checkout_dip_suggestions(
    all_side_items: List[Dict[str, Any]],
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Returns dip/condiment suggestions specifically for the checkout page.
    Conditions:
      - Cart must have at least one qualifying side host (Fries, Nuggets, etc.)
      - Cart must NOT already have a condiment/dip
    Merchandising Order:
      - display_order ascending (database merchandising priority)
      - price ascending (deterministic secondary tie-breaker)
    """
    if not has_side_in_cart(cart):
        return []

    if has_condiment_in_cart(cart):
        return []

    condiments = [item for item in all_side_items if is_condiment(item)]

    return sorted(
        condiments,
        key=lambda item: (
            item.get("display_order", 999),
            float(item.get("price") or 0)
        )
    )
