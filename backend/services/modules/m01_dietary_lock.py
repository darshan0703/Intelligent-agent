"""
Module 1: Strict Dietary Lock (Phase 1 Hard Gate)

Eradicates non-veg items from candidate pool if customer has active
veg preference, or if all items in cart are vegetarian.
"""


def normalize_food_type(value):
    """
    Normalize all food-type representations to one canonical value.

    Examples:
        "Veg"      -> "veg"
        "Non Veg"  -> "non_veg"
        "non veg"  -> "non_veg"
        "non_veg"  -> "non_veg"
        "Non-Veg"  -> "non_veg"
    """

    return (
        str(value or "")
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .strip()
    )


def get_item_food_type(item):
    """
    Read food type from either supported database field name.
    """

    return normalize_food_type(
        item.get("foodType")
        or item.get("food_type")
        or ""
    )


def apply_dietary_lock(candidates, preference, cart):
    """
    Apply the strict dietary gate before recommendation scoring.
    """

    eff_pref = normalize_food_type(preference)

    # ---------------------------------------------------------
    # CART-BASED DIETARY LOCK
    # ---------------------------------------------------------

    if not eff_pref and cart:
        all_veg = all(
            get_item_food_type(item) == "veg"
            for item in cart
        )

        if all_veg:
            eff_pref = "veg"

    # ---------------------------------------------------------
    # VEG LOCK
    # ---------------------------------------------------------

    if eff_pref == "veg":
        return [
            item
            for item in candidates
            if get_item_food_type(item) == "veg"
        ]

    # ---------------------------------------------------------
    # NON-VEG LOCK
    # ---------------------------------------------------------

    if eff_pref == "non_veg":
        return [
            item
            for item in candidates
            if get_item_food_type(item) == "non_veg"
        ]

    # ---------------------------------------------------------
    # NO ACTIVE LOCK
    # ---------------------------------------------------------

    return candidates