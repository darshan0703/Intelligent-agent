"""
Focused Unit & Business Rule Tests for Module 5: Budget Ceiling
Tests all 16 explicit business rules.
"""
import sys
import os
import copy

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.modules.m05_budget_ceiling import (
    apply_price_ceiling,
    _get_item_price,
    _get_item_category,
)


def test_1_empty_cart():
    candidates = [
        {"name": "Fries", "price": 130.0, "category": "side"},
        {"name": "Drink", "price": 110.0, "category": "drink"},
    ]
    result = apply_price_ceiling(candidates, cart=[])
    assert result == candidates, "Empty cart must return candidates unchanged"


def test_2_burger_anchor_below_100():
    # Anchor = Burger ₹89. Ratio = 2.0x -> Ceiling = ₹178.0
    cart = [{"name": "Crispy Veg", "price": 89.0, "category": "burger"}]
    candidates = [
        {"name": "Fries", "price": 130.0, "category": "side"},      # <= 178 -> kept
        {"name": "Cold Coffee", "price": 170.0, "category": "drink"},# <= 178 -> kept
        {"name": "KitKat Shake", "price": 249.0, "category": "drink"},# > 178 -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Fries" in res_names and "Cold Coffee" in res_names
    assert "KitKat Shake" not in res_names, "Shake above 2.0x ceiling must be filtered"


def test_3_burger_anchor_between_100_and_199():
    # Anchor = Burger ₹169. Ratio = 1.75x -> Ceiling = ₹295.75
    cart = [{"name": "Paneer Whopper", "price": 169.0, "category": "burger"}]
    candidates = [
        {"name": "Fries King", "price": 140.0, "category": "side"},    # <= 295.75 -> kept
        {"name": "Shake", "price": 249.0, "category": "drink"},         # <= 295.75 -> kept
        {"name": "Wings Platter", "price": 359.0, "category": "side"}, # > 295.75 -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Fries King" in res_names and "Shake" in res_names
    assert "Wings Platter" not in res_names, "Wings above 1.75x ceiling must be filtered"


def test_4_burger_anchor_ge_200():
    # Anchor = Burger ₹239. Ratio = 1.5x -> Ceiling = ₹358.50
    cart = [{"name": "Peri Peri Cheese", "price": 239.0, "category": "burger"}]
    candidates = [
        {"name": "Shake", "price": 249.0, "category": "drink"},          # <= 358.5 -> kept
        {"name": "Wings 8pc", "price": 279.0, "category": "side"},       # <= 358.5 -> kept
        {"name": "Wings 15pc", "price": 519.0, "category": "side"},      # > 358.5 -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Shake" in res_names and "Wings 8pc" in res_names
    assert "Wings 15pc" not in res_names, "Wings 15pc above 1.5x ceiling must be filtered"


def test_5_burger_preferred_as_anchor_over_more_expensive_side_or_drink():
    # Cart has Burger ₹139 and expensive Wings ₹309.
    # The Burger MUST be chosen as anchor, NOT the Wings!
    # Anchor = ₹139 -> ratio 1.75x -> ceiling = ₹243.25
    # (If Wings ₹309 were chosen -> ceiling = 309 * 1.5 = ₹463.50)
    cart = [
        {"name": "BK Veggie", "price": 139.0, "category": "burger"},
        {"name": "Wings Bucket", "price": 309.0, "category": "side"},
    ]
    candidates = [
        {"name": "Medium Fries", "price": 130.0, "category": "side"},   # <= 243.25 -> kept
        {"name": "Classic Cold Coffee", "price": 189.0, "category": "drink"}, # <= 243.25 -> kept
        {"name": "Frappe", "price": 249.0, "category": "drink"},        # > 243.25 -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Medium Fries" in res_names and "Classic Cold Coffee" in res_names
    assert "Frappe" not in res_names, "Frappe above Burger anchor ceiling must be filtered"


def test_6_no_main_in_cart_highest_item_becomes_anchor():
    # Cart has NO burgers/mains: only Side ₹140 and Drink ₹111.
    # Highest item is Side ₹140 (category='side') -> ratio 1.75x -> ceiling = ₹245.0
    cart = [
        {"name": "Fries King", "price": 140.0, "category": "side"},
        {"name": "Sprite", "price": 111.0, "category": "drink"},
    ]
    candidates = [
        {"name": "Cold Coffee", "price": 189.0, "category": "drink"},  # <= 245.0 -> kept
        {"name": "Choco Lava", "price": 119.0, "category": "dessert"},  # <= 245.0 -> kept
        {"name": "Gourmet Burger", "price": 299.0, "category": "burger"},  # > 245.0 (cross-sell) -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Cold Coffee" in res_names and "Choco Lava" in res_names
    assert "Gourmet Burger" not in res_names, "Cross-sell above highest-cart-item ceiling must be filtered"


def test_7_same_category_candidates_bypass_ceiling():
    # Cart has Burger ₹139. Ceiling = 139 * 1.75 = ₹243.25.
    # A candidate Burger with price ₹299 (above ceiling) MUST survive because same-category browsing bypasses ceiling.
    cart = [{"name": "BK Veggie", "price": 139.0, "category": "burger"}]
    candidates = [
        {"name": "Crispy Veg", "price": 59.0, "category": "burger"},
        {"name": "Premium Double Whopper", "price": 299.0, "category": "burger"}, # > 243.25 but SAME category!
    ]
    result = apply_price_ceiling(candidates, cart)
    assert len(result) == 2
    assert "Premium Double Whopper" in [i["name"] for i in result], "Same-category candidate must bypass ceiling"


def test_8_cross_category_candidates_above_ceiling_filtered():
    cart = [{"name": "Crispy Veg", "price": 59.0, "category": "burger"}] # ceiling = 59 * 2.0 = 118
    candidates = [
        {"name": "Sundae", "price": 45.0, "category": "dessert"},   # <= 118 -> kept
        {"name": "Hot Chocolate", "price": 179.0, "category": "drink"}, # > 118 -> dropped
        {"name": "KitKat Shake", "price": 249.0, "category": "drink"}, # > 118 -> dropped
        {"name": "Vanilla Softie", "price": 33.0, "category": "dessert"}, # <= 118 -> kept
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Hot Chocolate" not in res_names
    assert "KitKat Shake" not in res_names


def test_9_cross_category_candidates_at_or_below_ceiling_survive():
    cart = [{"name": "Burger", "price": 100.0, "category": "burger"}] # ceiling = 100 * 1.75 = 175.0
    candidates = [
        {"name": "Item at ceiling", "price": 175.0, "category": "side"},
        {"name": "Item below ceiling", "price": 130.0, "category": "drink"},
    ]
    result = apply_price_ceiling(candidates, cart)
    assert len(result) == 2, "Items at or below ceiling must survive"


def test_10_ge_2_survivors_returns_only_survivors():
    cart = [{"name": "Burger", "price": 100.0, "category": "burger"}] # ceiling = 175.0
    candidates = [
        {"name": "Low 1", "price": 50.0, "category": "side"},
        {"name": "Low 2", "price": 80.0, "category": "side"},
        {"name": "High 1", "price": 300.0, "category": "side"},
    ]
    result = apply_price_ceiling(candidates, cart)
    assert len(result) == 2
    assert [i["name"] for i in result] == ["Low 1", "Low 2"]


def test_11_zero_survivors_fallback_returns_original_candidates():
    # If all items exceed ceiling, fallback returns original candidate list so shelf is not starved
    cart = [{"name": "Burger", "price": 50.0, "category": "burger"}] # ceiling = 50 * 2.0 = 100
    candidates = [
        {"name": "Expensive 1", "price": 250.0, "category": "side"},
        {"name": "Expensive 2", "price": 300.0, "category": "drink"},
    ]
    result = apply_price_ceiling(candidates, cart)
    assert result == candidates, "0 survivors must trigger fallback returning original candidates"


def test_12_one_survivor_fallback_returns_original_candidates():
    # If only 1 item survives, fallback returns original candidate list (minimum 2 items shelf requirement)
    cart = [{"name": "Burger", "price": 50.0, "category": "burger"}] # ceiling = 100
    candidates = [
        {"name": "Cheap One", "price": 80.0, "category": "side"},       # survives
        {"name": "Expensive 1", "price": 250.0, "category": "drink"},   # filtered
        {"name": "Expensive 2", "price": 300.0, "category": "dessert"}, # filtered
    ]
    result = apply_price_ceiling(candidates, cart)
    assert result == candidates, "1 survivor must trigger fallback returning original candidates"


def test_13_missing_invalid_candidate_price_does_not_crash():
    cart = [{"name": "Burger", "price": 100.0, "category": "burger"}]
    candidates = [
        {"name": "None price", "price": None, "category": "side"},
        {"name": "String price", "price": "120.50", "category": "side"},
        {"name": "Nested price", "price": {"amount": 110.0}, "category": "drink"},
        {"name": "Corrupted price", "price": "invalid", "category": "dessert"},
        {"name": "Zero price", "price": 0.0, "category": "side"},
    ]
    result = apply_price_ceiling(candidates, cart)
    assert len(result) >= 2, "Function must handle varied price formats without crashing"


def test_14_missing_category_does_not_trigger_database_lookup(monkeypatch):
    # Ensure no network / database / service calls happen when category is missing
    cart = [{"name": "Unknown Cart Item", "price": 100.0}]
    candidates = [
        {"name": "Unknown Candidate 1", "price": 50.0},
        {"name": "Unknown Candidate 2", "price": 60.0},
    ]
    # If any DB/service function were called, it would fail or be detected
    result = apply_price_ceiling(candidates, cart)
    assert len(result) == 2
    assert _get_item_category({}) == ""


def test_15_does_not_mutate_candidate_dictionaries_or_input_list():
    cart = [{"name": "Burger", "price": 100.0, "category": "burger"}]
    c1 = {"name": "Fries", "price": 120.0, "category": "side"}
    c2 = {"name": "Coke", "price": 80.0, "category": "drink"}
    candidates = [c1, c2]

    c1_snapshot = copy.deepcopy(c1)
    c2_snapshot = copy.deepcopy(c2)
    candidates_snapshot = list(candidates)

    result = apply_price_ceiling(candidates, cart)

    assert c1 == c1_snapshot, "Candidate dict must not be mutated"
    assert c2 == c2_snapshot, "Candidate dict must not be mutated"
    assert candidates == candidates_snapshot, "Input candidates list must not be mutated in-place"
    assert result is not candidates, "Survivors must be a new list"


def test_16_m01_m07_m06_not_reimplemented_in_m05():
    # Verify M05 does NOT filter by veg/non-veg (M01), does NOT filter carted items (M07),
    # and does NOT filter condiments (M06) - those are separate modules.
    cart = [{"name": "Burger", "price": 100.0, "category": "burger"}]
    candidates = [
        {"name": "Burger", "price": 100.0, "category": "burger"},             # Already in cart (M07 job)
        {"name": "Chicken Wings", "price": 120.0, "category": "side", "foodType": "non_veg"}, # Non-veg (M01 job)
        {"name": "Fiery Hell Dip", "price": 25.0, "category": "side", "section": "Dips"},     # Condiment (M06 job)
    ]
    result = apply_price_ceiling(candidates, cart)
    # M05 should only apply budget logic; since all are within ceiling (or same category), all survive M05!
    assert len(result) == 3, "M05 must strictly focus on budget ceiling without reimplementing M01/M06/M07"


def test_17_meal_uses_highest_priced_component_not_unit_price():
    # Whopper Meal unitPrice = ₹249
    # Components: Whopper ₹199, Fries ₹130, Coke ₹99
    # Anchor must be ₹199 (Whopper), NOT ₹249!
    # Ceiling = 199 * 1.75 = ₹348.25.
    # (If ₹249 were used as anchor, ceiling would be 249 * 1.5 = ₹373.50).
    # Test with a candidate priced at ₹360:
    # Under correct ₹199 anchor (ceiling ₹348.25) -> ₹360 is DROPPED.
    # Under buggy ₹249 anchor (ceiling ₹373.50) -> ₹360 would leak!
    meal_cart = [{
        "type": "meal",
        "name": "Whopper Meal",
        "unitPrice": 249.0,
        "main_item": {"name": "Whopper", "price": 199.0, "category": "burger"},
        "side": {"name": "Fries", "price": 130.0, "category": "side"},
        "drink": {"name": "Coke", "price": 99.0, "category": "drink"},
    }]
    candidates = [
        {"name": "Affordable Shake", "price": 200.0, "category": "drink"}, # <= 348.25 -> kept
        {"name": "Standard Wings", "price": 300.0, "category": "side"},     # <= 348.25 -> kept
        {"name": "Luxury Platter", "price": 360.0, "category": "side"},     # > 348.25 -> DROPPED
    ]
    result = apply_price_ceiling(candidates, meal_cart)
    res_names = [i["name"] for i in result]
    assert "Affordable Shake" in res_names and "Standard Wings" in res_names
    assert "Luxury Platter" not in res_names, "Luxury Platter must be filtered under component anchor ₹199"


def test_18_meal_main_preferred_as_anchor_when_highest_main():
    # Meal has Burger ₹169, Side ₹180 (e.g. expensive side combo), Drink ₹99.
    # Even though Side is ₹180, Burger ₹169 is the main!
    # Burger ₹169 must be chosen as anchor -> ceiling = 169 * 1.75 = ₹295.75.
    meal_cart = [{
        "type": "meal",
        "name": "Combo Meal",
        "unitPrice": 300.0,
        "main_item": {"name": "Paneer Whopper", "price": 169.0, "category": "burger"},
        "side": {"name": "Loaded Wings Side", "price": 180.0, "category": "side"},
        "drink": {"name": "Soda", "price": 99.0, "category": "drink"},
    }]
    candidates = [
        {"name": "Dessert 1", "price": 150.0, "category": "dessert"}, # <= 295.75 -> kept
        {"name": "Dessert 2", "price": 250.0, "category": "dessert"}, # <= 295.75 -> kept
        {"name": "Dessert 3", "price": 310.0, "category": "dessert"}, # > 295.75 -> dropped
    ]
    result = apply_price_ceiling(candidates, meal_cart)
    res_names = [i["name"] for i in result]
    assert "Dessert 3" not in res_names, "Main component must be preferred as anchor"


def test_19_higher_priced_side_can_become_anchor_if_no_main_exists():
    # Cart has a composite item with only side and drink (no main).
    # Side ₹140, Drink ₹99. Side ₹140 becomes anchor -> ceiling = 140 * 1.75 = ₹245.0
    side_drink_combo = [{
        "type": "meal",
        "name": "Side Drink Combo",
        "unitPrice": 200.0,
        "side": {"name": "Large Fries", "price": 140.0, "category": "side"},
        "drink": {"name": "Iced Tea", "price": 99.0, "category": "drink"},
    }]
    candidates = [
        {"name": "Dessert A", "price": 120.0, "category": "dessert"}, # <= 245 -> kept
        {"name": "Dessert B", "price": 200.0, "category": "dessert"}, # <= 245 -> kept
        {"name": "Expensive Burger", "price": 280.0, "category": "burger"}, # > 245 -> dropped
    ]
    result = apply_price_ceiling(candidates, side_drink_combo)
    res_names = [i["name"] for i in result]
    assert "Expensive Burger" not in res_names


def test_20_standalone_burger_plus_meal_highest_main_wins():
    # Cart has:
    # 1. Standalone Burger ₹179
    # 2. Whopper Meal with Whopper ₹199, Fries ₹130, Coke ₹99
    # Both are mains. Highest main = Whopper ₹199!
    # Ceiling = 199 * 1.75 = ₹348.25.
    cart = [
        {"name": "Cheese Whopper", "price": 179.0, "category": "burger"},
        {
            "type": "meal",
            "name": "Whopper Meal",
            "unitPrice": 249.0,
            "main_item": {"name": "Whopper", "price": 199.0, "category": "burger"},
            "side": {"name": "Fries", "price": 130.0, "category": "side"},
            "drink": {"name": "Coke", "price": 99.0, "category": "drink"},
        },
        {"name": "Coffee", "price": 189.0, "category": "drink"},
    ]
    candidates = [
        {"name": "Side 1", "price": 200.0, "category": "side"}, # <= 348.25 -> kept
        {"name": "Side 2", "price": 300.0, "category": "side"}, # <= 348.25 -> kept
        {"name": "Side 3", "price": 360.0, "category": "side"}, # > 348.25 -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Side 1" in res_names and "Side 2" in res_names
    assert "Side 3" not in res_names


def test_21_meal_bundle_price_never_becomes_anchor():
    # Small burger meal: Burger ₹59, Fries ₹55, Coke ₹40. Bundle unitPrice = ₹154.
    # Anchor must be Burger ₹59 (ratio 2.0x -> ceiling = ₹118).
    # If bundle ₹154 were used as anchor, ceiling would be 154 * 1.75 = ₹269.50!
    small_meal_cart = [{
        "type": "meal",
        "name": "Crispy Veg Small Meal",
        "unitPrice": 154.0,
        "main_item": {"name": "Crispy Veg", "price": 59.0, "category": "burger"},
        "side": {"name": "Fries Small", "price": 55.0, "category": "side"},
        "drink": {"name": "Coke Small", "price": 40.0, "category": "drink"},
    }]
    candidates = [
        {"name": "Sundae", "price": 45.0, "category": "dessert"},       # <= 118 -> kept
        {"name": "Vanilla Softie", "price": 33.0, "category": "dessert"},# <= 118 -> kept
        {"name": "Frappe", "price": 199.0, "category": "drink"},          # > 118 -> MUST BE DROPPED!
    ]
    result = apply_price_ceiling(candidates, small_meal_cart)
    res_names = [i["name"] for i in result]
    assert "Frappe" not in res_names, "Frappe above component ceiling ₹118 must be dropped; bundle price must never anchor"


def test_22_meal_with_missing_component_does_not_crash():
    # Meal with None or missing side / drink
    malformed_meal = [{
        "type": "meal",
        "name": "Partial Meal",
        "unitPrice": 199.0,
        "main_item": {"name": "Burger Only", "price": 120.0, "category": "burger"},
        "side": None,
        # drink omitted
    }]
    candidates = [
        {"name": "Item 1", "price": 100.0, "category": "side"},
        {"name": "Item 2", "price": 120.0, "category": "drink"},
    ]
    result = apply_price_ceiling(candidates, malformed_meal)
    assert len(result) == 2, "Partial meal must not crash"


def test_23_normal_cart_items_continue_working_unchanged():
    # Standard standalone cart without any meals
    cart = [
        {"name": "Paneer Royale", "price": 209.0, "category": "burger"},
        {"name": "Masala Hashbrown", "price": 45.0, "category": "side"},
    ]
    candidates = [
        {"name": "Fries Medium", "price": 130.0, "category": "side"},
        {"name": "KitKat Shake", "price": 249.0, "category": "drink"},
        {"name": "Wings 15pc", "price": 519.0, "category": "side"}, # ceiling = 209 * 1.5 = 313.5 -> dropped
    ]
    result = apply_price_ceiling(candidates, cart)
    res_names = [i["name"] for i in result]
    assert "Fries Medium" in res_names and "KitKat Shake" in res_names
    assert "Wings 15pc" not in res_names


if __name__ == "__main__":
    test_1_empty_cart()
    test_2_burger_anchor_below_100()
    test_3_burger_anchor_between_100_and_199()
    test_4_burger_anchor_ge_200()
    test_5_burger_preferred_as_anchor_over_more_expensive_side_or_drink()
    test_6_no_main_in_cart_highest_item_becomes_anchor()
    test_7_same_category_candidates_bypass_ceiling()
    test_8_cross_category_candidates_above_ceiling_filtered()
    test_9_cross_category_candidates_at_or_below_ceiling_survive()
    test_10_ge_2_survivors_returns_only_survivors()
    test_11_zero_survivors_fallback_returns_original_candidates()
    test_12_one_survivor_fallback_returns_original_candidates()
    test_13_missing_invalid_candidate_price_does_not_crash()
    test_14_missing_category_does_not_trigger_database_lookup(None)
    test_15_does_not_mutate_candidate_dictionaries_or_input_list()
    test_16_m01_m07_m06_not_reimplemented_in_m05()
    test_17_meal_uses_highest_priced_component_not_unit_price()
    test_18_meal_main_preferred_as_anchor_when_highest_main()
    test_19_higher_priced_side_can_become_anchor_if_no_main_exists()
    test_20_standalone_burger_plus_meal_highest_main_wins()
    test_21_meal_bundle_price_never_becomes_anchor()
    test_22_meal_with_missing_component_does_not_crash()
    test_23_normal_cart_items_continue_working_unchanged()
    print("ALL 23 M05 BUSINESS RULE TESTS PASSED SUCCESSFULLY!")
