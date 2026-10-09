"""
Focused Unit & Business Rule Tests for Module 6: Condiment Host Gating (Metadata-Driven V3)
Tests all 15 explicit business rules.
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.modules.m06_condiment_gating import (
    is_condiment,
    is_meal_only_item,
    is_side_item,
    has_side_in_cart,
    has_condiment_in_cart,
    filter_for_recommendation_page,
    get_checkout_dip_suggestions,
)


# =========================================================================
# TEST FIXTURES BASED ON CANONICAL DATABASE METADATA
# =========================================================================

FIERY_HELL_DIP = {
    "id": 83,
    "name": "Fiery Hell Dip",
    "category": "side",
    "section": "Dips",
    "price": 25.0,
    "display_order": 1,
    "is_meal_only": False,
}

CHILLI_SAUCE = {
    "id": 84,
    "name": "Chilli Sauce With Oregano",
    "category": "side",
    "section": "Dips",
    "price": 25.0,
    "display_order": 2,
    "is_meal_only": False,
}

CHOCO_DIP_SOFTIE = {
    "id": 55,
    "name": "Choco Dip Softie",
    "category": "dessert",
    "section": "Soft Serve",
    "price": 50.0,
    "display_order": 2,
    "is_meal_only": False,
}

FRIES_MEDIUM = {
    "id": 65,
    "name": "Fries (Medium)",
    "category": "side",
    "section": "Fries",
    "meal_role": "side",
    "price": 130.0,
    "display_order": 1,
    "is_meal_only": False,
}

CRUNCHY_NUGGETS = {
    "id": 70,
    "name": "Crunchy Chicken Nuggets (4 Pc)",
    "category": "side",
    "section": "Nuggets",
    "meal_role": "side",
    "price": 89.0,
    "display_order": 1,
    "is_meal_only": False,
}

BURGER_WHOPPER = {
    "id": 8,
    "name": "Chicken Whopper",
    "category": "burger",
    "section": "Whoppers",
    "meal_role": "main",
    "price": 209.0,
    "display_order": 2,
    "is_meal_only": False,
}

DRINK_COKE = {
    "id": 40,
    "name": "Large Coca cola",
    "category": "drink",
    "section": "Cold Drinks",
    "meal_role": "drink",
    "price": 131.0,
    "display_order": 2,
    "is_meal_only": False,
}

MEAL_COMBO = {
    "type": "meal",
    "name": "Regular Meal",
    "side": {
        "id": 65,
        "name": "Fries (Medium)",
        "category": "side",
        "section": "Fries",
    },
    "drink": DRINK_COKE,
}

MEAL_ONLY_COMPONENT = {
    "id": 85,
    "name": "Peri Peri Chicken Boneless 2 Pc",
    "category": "side",
    "section": "Nuggets",
    "meal_role": "side",
    "price": 0.0,
    "display_order": 11,
    "is_meal_only": True,
}


# =========================================================================
# THE 15 REQUIRED BUSINESS TESTS
# =========================================================================

def test_1_fiery_hell_dip_is_condiment():
    assert is_condiment(FIERY_HELL_DIP) is True, "Fiery Hell Dip (section='Dips') must be recognized as condiment"


def test_2_chilli_sauce_is_condiment():
    assert is_condiment(CHILLI_SAUCE) is True, "Chilli Sauce (section='Dips') must be recognized as condiment"


def test_3_choco_dip_softie_is_not_condiment():
    # MANDATORY TEST: Old string-based heuristic falsely flagged this because 'dip' is in the name.
    assert is_condiment(CHOCO_DIP_SOFTIE) is False, "Choco Dip Softie (category='dessert') must NOT be a condiment"


def test_4_fries_has_side_in_cart():
    cart = [FRIES_MEDIUM]
    assert has_side_in_cart(cart) is True, "Fries in cart must satisfy has_side_in_cart"


def test_5_nuggets_has_side_in_cart():
    cart = [CRUNCHY_NUGGETS]
    assert has_side_in_cart(cart) is True, "Nuggets in cart must satisfy has_side_in_cart"


def test_6_burger_has_no_side_in_cart():
    cart = [BURGER_WHOPPER, DRINK_COKE, CHOCO_DIP_SOFTIE]
    assert has_side_in_cart(cart) is False, "Burger/drink/dessert cart must NOT satisfy has_side_in_cart"


def test_7_meal_with_nested_side_has_side_in_cart():
    cart = [MEAL_COMBO]
    assert has_side_in_cart(cart) is True, "Combo meal with nested Fries in 'side' must satisfy has_side_in_cart"

    # Also test nested side where category is omitted but meal_role='side' is provided
    meal_with_role_only = {
        "type": "meal",
        "name": "Combo",
        "side": {
            "name": "Upgrade Fries",
            "meal_role": "side",
        }
    }
    assert has_side_in_cart([meal_with_role_only]) is True, "Nested side with meal_role='side' must be recognized"

    # Standalone item with only meal_role='side' but non-side category must NOT be a standalone side host
    non_side_standalone = {"name": "Test Burger", "category": "burger", "meal_role": "side"}
    assert has_side_in_cart([non_side_standalone]) is False, "Standalone item must strictly require category == 'side'/'sides'"


def test_8_cart_with_condiment_has_condiment_in_cart():
    cart = [FRIES_MEDIUM, FIERY_HELL_DIP]
    assert has_condiment_in_cart(cart) is True, "Cart with Fiery Hell Dip must return has_condiment_in_cart == True"


def test_9_checkout_with_no_side_returns_empty():
    cart = [BURGER_WHOPPER]
    all_sides = [FIERY_HELL_DIP, CHILLI_SAUCE, FRIES_MEDIUM]
    assert get_checkout_dip_suggestions(all_sides, cart) == [], "Checkout without a side host must return []"


def test_10_checkout_with_side_and_no_condiment_returns_dips():
    cart = [FRIES_MEDIUM]
    all_sides = [FRIES_MEDIUM, FIERY_HELL_DIP, CHILLI_SAUCE]
    dips = get_checkout_dip_suggestions(all_sides, cart)
    dip_ids = [d["id"] for d in dips]
    assert 83 in dip_ids and 84 in dip_ids, "Should return available Dips-section condiments"
    assert 65 not in dip_ids, "Fries must not be returned as a dip suggestion"


def test_11_checkout_with_side_and_existing_condiment_returns_empty():
    cart = [FRIES_MEDIUM, CHILLI_SAUCE]
    all_sides = [FIERY_HELL_DIP, CHILLI_SAUCE]
    assert get_checkout_dip_suggestions(all_sides, cart) == [], "Cart already containing dip must return []"


def test_12_meal_only_item_metadata_detection():
    assert is_meal_only_item(MEAL_ONLY_COMPONENT) is True, "Item with is_meal_only=True must be detected"

    # Verify string boolean values ('true', 't', '1' vs 'false', 'f', '0')
    assert is_meal_only_item({"name": "Test", "is_meal_only": "true"}) is True
    assert is_meal_only_item({"name": "Test", "is_meal_only": "True"}) is True
    assert is_meal_only_item({"name": "Test", "is_meal_only": "t"}) is True
    assert is_meal_only_item({"name": "Test", "is_meal_only": "1"}) is True

    assert is_meal_only_item({"name": "Test", "is_meal_only": "false", "price": 0.0}) is False
    assert is_meal_only_item({"name": "Test", "is_meal_only": "False", "price": 0.0}) is False
    assert is_meal_only_item({"name": "Test", "is_meal_only": "f", "price": 0.0}) is False
    assert is_meal_only_item({"name": "Test", "is_meal_only": "0", "price": 0.0}) is False

    # Also verify that a zero-priced promo with is_meal_only=False is NOT meal-only
    promo_item = {"name": "Birthday Dessert", "price": 0.0, "is_meal_only": False}
    assert is_meal_only_item(promo_item) is False, "Explicit is_meal_only=False must not be treated as meal-only"

    # Fallback when is_meal_only key is absent
    legacy_zero = {"name": "Old Component", "price": 0.0}
    assert is_meal_only_item(legacy_zero) is True, "Missing metadata with price=0 must fallback to True"


def test_13_meal_only_item_excluded_from_recommendations():
    candidates = [BURGER_WHOPPER, MEAL_ONLY_COMPONENT]
    filtered = filter_for_recommendation_page(candidates)
    assert MEAL_ONLY_COMPONENT not in filtered, "Meal-only component must be dropped from recommendations"
    assert BURGER_WHOPPER in filtered, "Burger must remain in recommendations"


def test_14_choco_dip_softie_remains_in_recommendations():
    candidates = [CHOCO_DIP_SOFTIE, FIERY_HELL_DIP]
    filtered = filter_for_recommendation_page(candidates)
    assert CHOCO_DIP_SOFTIE in filtered, "Choco Dip Softie must NOT be filtered out of recommendations"
    assert FIERY_HELL_DIP not in filtered, "Fiery Hell Dip MUST be filtered out of standard recommendations"


def test_15_condiment_ordering_follows_display_order_not_name():
    # Construct two condiments where name keyword 'sauce' has higher display_order than 'dip'
    # Old logic: 'sauce' in name -> priority 0 (first).
    # New metadata logic: display_order 1 comes first regardless of whether it's named 'dip' or 'sauce'.
    dip_first = {
        "id": 101,
        "name": "Fiery Dip",
        "category": "side",
        "section": "Dips",
        "price": 30.0,
        "display_order": 1,
    }
    sauce_second = {
        "id": 102,
        "name": "Garlic Sauce",
        "category": "side",
        "section": "Dips",
        "price": 30.0,
        "display_order": 2,
    }
    cart = [FRIES_MEDIUM]
    # Pass in sauce first in list to test that sorting properly places display_order 1 first
    result = get_checkout_dip_suggestions([sauce_second, dip_first], cart)
    assert [r["id"] for r in result] == [101, 102], "Condiments must be ordered by display_order, not by name containing 'sauce'"


if __name__ == "__main__":
    test_1_fiery_hell_dip_is_condiment()
    test_2_chilli_sauce_is_condiment()
    test_3_choco_dip_softie_is_not_condiment()
    test_4_fries_has_side_in_cart()
    test_5_nuggets_has_side_in_cart()
    test_6_burger_has_no_side_in_cart()
    test_7_meal_with_nested_side_has_side_in_cart()
    test_8_cart_with_condiment_has_condiment_in_cart()
    test_9_checkout_with_no_side_returns_empty()
    test_10_checkout_with_side_and_no_condiment_returns_dips()
    test_11_checkout_with_side_and_existing_condiment_returns_empty()
    test_12_meal_only_item_metadata_detection()
    test_13_meal_only_item_excluded_from_recommendations()
    test_14_choco_dip_softie_remains_in_recommendations()
    test_15_condiment_ordering_follows_display_order_not_name()
    print("ALL 15 BUSINESS RULE TESTS PASSED SUCCESSFULLY!")
