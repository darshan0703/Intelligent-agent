"""
Module 6: Condiment Host Gating (Updated)

Rules:
1. MEAL-ONLY ITEMS (price == 0): These are meal components (e.g. Peri Peri Chicken Boneless 2Pc).
   Always dropped from ALL recommendations. They can only appear via the meal flow.

2. CONDIMENTS / DIPS (dip, sauce, mayo, ketchup): These are checkout-only suggestions.
   Always dropped from the 4-card recommendation pages (product, category, etc.).
   They are surfaced separately via the /cart/checkout-suggestions endpoint.

3. FINGER FOOD detection: Used by the checkout suggestions endpoint to know
   whether to offer dips at checkout.
"""
from typing import Dict, Any, List

FINGER_FOOD_KEYWORDS = {"fries", "nugget", "wing", "strip", "hashbrown", "puff"}
DIP_KEYWORDS         = {"dip", "sauce", "mayo", "ketchup"}


def is_meal_only_item(item: Dict[str, Any]) -> bool:
    """
    Returns True if the item is a meal-only component (price == 0).
    These items are database-level meal components and must never surface
    as standalone recommendations.
    """
    raw_price = item.get("price")
    if raw_price is None:
        raw_price = item.get("original_price")
    try:
        return float(raw_price) == 0.0
    except (TypeError, ValueError):
        return False


def is_condiment(item: Dict[str, Any]) -> bool:
    """Returns True if item is a dip / sauce / condiment alone, not a combo meal containing dips."""
    name = str(item.get("name", "")).lower()
    # Exclude combos or desserts that mention dips or sauces
    if any(k in name for k in ["nugget", "wing", "strip", "fries", "burger", "softie", "sundae", "cone", "waffle", "cake", "mousse"]):
        return False
    return any(d in name for d in DIP_KEYWORDS)


def has_finger_food_in_cart(cart: List[Dict[str, Any]]) -> bool:
    """Returns True if cart contains any finger-food host item (Fries, Nuggets, etc.)."""
    for item in cart:
        name = str(item.get("name", "")).lower()
        if any(f in name for f in FINGER_FOOD_KEYWORDS):
            return True
        # If it's a meal combo, check the side component
        side = item.get("side")
        if isinstance(side, dict):
            side_name = str(side.get("name", "")).lower()
            if any(f in side_name for f in FINGER_FOOD_KEYWORDS):
                return True
    return False


def has_dip_in_cart(cart: List[Dict[str, Any]]) -> bool:
    """Returns True if cart already contains a dip/sauce."""
    for item in cart:
        if is_condiment(item):
            return True
        side = item.get("side")
        if isinstance(side, dict) and is_condiment(side):
            return True
    return False


def filter_for_recommendation_page(
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Hard gate for all 4-card recommendation pages (product page, category page, etc.).
    Drops:
      - Meal-only items (price == 0)
      - All condiments / dips (those belong only on checkout)
    """
    return [
        item for item in candidates
        if not is_meal_only_item(item) and not is_condiment(item)
    ]


def get_checkout_dip_suggestions(
    all_side_items: List[Dict[str, Any]],
    cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Returns dip/sauce suggestions specifically for the checkout page.
    Conditions:
      - Cart must have at least one finger-food host (Fries, Nuggets, etc.)
      - Cart must NOT already have a dip/sauce
    Priority wise:
      1. Sauces first (e.g. Chilli Sauce With Oregano)
      2. Dips second (e.g. Fiery Hell Dip)
      3. Sorted by price ascending
    """
    if not has_finger_food_in_cart(cart):
        return []

    if has_dip_in_cart(cart):
        return []

    condiments = [item for item in all_side_items if is_condiment(item)]

    def priority_key(item: Dict[str, Any]):
        name = str(item.get("name", "")).lower()
        # Priority 0 for sauces, Priority 1 for dips, Priority 2 for others
        pri = 0 if "sauce" in name else (1 if "dip" in name else 2)
        price = float(item.get("price") or 0)
        return (pri, price)

    return sorted(condiments, key=priority_key)
