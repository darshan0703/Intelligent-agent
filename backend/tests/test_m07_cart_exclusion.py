"""
Unit tests for Module 7: Absolute Cart Exclusion
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
module_dir = os.path.abspath(os.path.join(current_dir, "..", "files", "backend"))
sys.path.insert(0, backend_dir)
sys.path.insert(0, module_dir)

try:
    from services.modules.m07_cart_exclusion import exclude_cart_items
except ImportError:
    from backend.services.modules.m07_cart_exclusion import exclude_cart_items

def test_cart_exclusion_by_id():
    cart = [{"id": 101, "name": "Veg Whopper"}]
    candidates = [
        {"id": 101, "name": "Veg Whopper"},
        {"id": 102, "name": "Peri Peri Fries"},
    ]
    survivors = exclude_cart_items(candidates, cart)
    assert len(survivors) == 1, f"Expected 1 survivor, got {len(survivors)}"
    assert survivors[0]["id"] == 102
    print("PASS: test_cart_exclusion_by_id")

def test_cart_exclusion_by_name():
    cart = [{"name": "Classic Fries"}]
    candidates = [
        {"id": 201, "name": "Classic Fries "},  # trailing space normalized
        {"id": 202, "name": "Cold Coffee"},
    ]
    survivors = exclude_cart_items(candidates, cart)
    assert len(survivors) == 1
    assert survivors[0]["id"] == 202
    print("PASS: test_cart_exclusion_by_name")

def test_meal_burger_exclusion_scenarios():
    # Scenario A: Standalone Veg Whopper
    cart_standalone = [{"type": "item", "id": 7, "name": "Veg Whopper", "category": "burger", "meal_role": "main"}]
    burger_candidates = [
        {"id": 7, "name": "Veg Whopper", "category": "burger", "meal_role": "main"},
        {"id": 12, "name": "Crispy Veg Burger", "category": "burger", "meal_role": "main"},
    ]
    survivors_a = exclude_cart_items(burger_candidates, cart_standalone)
    assert len(survivors_a) == 1
    assert survivors_a[0]["id"] == 12

    # Scenario B: Veg Whopper Meal
    cart_meal = [{
        "type": "meal",
        "name": "Veg Whopper Medium Meal",
        "main_item": {"id": 7, "name": "Veg Whopper", "category": "burger", "meal_role": "main"},
        "side": {"id": 65, "name": "Fries (Medium)", "category": "side", "meal_role": "side"},
        "drink": {"id": 80, "name": "Coke (Medium)", "category": "drink", "meal_role": "drink"},
    }]
    survivors_b = exclude_cart_items(burger_candidates, cart_meal)
    assert len(survivors_b) == 1
    assert survivors_b[0]["id"] == 12

    # Scenario C: Both standalone burger and meal
    cart_both = [
        {"type": "item", "id": 12, "name": "Crispy Veg Burger", "category": "burger", "meal_role": "main"},
        cart_meal[0],
    ]
    candidates_c = [
        {"id": 7, "name": "Veg Whopper", "category": "burger", "meal_role": "main"},
        {"id": 12, "name": "Crispy Veg Burger", "category": "burger", "meal_role": "main"},
        {"id": 15, "name": "Fiery Chicken Burger", "category": "burger", "meal_role": "main"},
    ]
    survivors_c = exclude_cart_items(candidates_c, cart_both)
    assert len(survivors_c) == 1
    assert survivors_c[0]["id"] == 15

    # Scenario D: Side and drink IDs from a meal must not accidentally exclude burger candidates
    burger_candidates_d = [
        {"id": 65, "name": "Special Promo Burger 65", "category": "burger", "meal_role": "main"},
        {"id": 80, "name": "Special Promo Burger 80", "category": "burger", "meal_role": "main"},
        {"id": 7, "name": "Veg Whopper", "category": "burger", "meal_role": "main"},
    ]
    survivors_d = exclude_cart_items(burger_candidates_d, cart_meal)
    # Burger 7 is excluded because main_item is 7. Burgers 65 and 80 must SURVIVE!
    assert len(survivors_d) == 2
    survivor_ids = {s["id"] for s in survivors_d}
    assert survivor_ids == {65, 80}

    # Scenario F: Empty cart preserves all candidates
    survivors_f = exclude_cart_items(burger_candidates, [])
    assert len(survivors_f) == len(burger_candidates)

    print("PASS: test_meal_burger_exclusion_scenarios")


def test_unknown_category_candidate_side_drink_id_collision():
    """
    Req: For candidates without category or meal_role metadata,
    a collision with a meal's side ID or drink ID must NOT cause the candidate to be excluded.
    However, a collision with a meal's main_item (burger) ID or a standalone item ID MUST exclude it.
    """
    cart = [
        {
            "type": "meal",
            "name": "Veg Whopper Medium Meal",
            "main_item": {"id": 7, "name": "Veg Whopper"},
            "side": {"id": 65, "name": "Fries (Medium)"},
            "drink": {"id": 80, "name": "Coke (Medium)"},
        },
        {"type": "item", "id": 10, "name": "Dessert 10"},
    ]

    candidates_without_metadata = [
        {"id": 65, "name": "Mystery Burger 65"},
        {"id": 80, "name": "Mystery Burger 80"},
        {"id": 7, "name": "Unknown Burger 7"},
        {"id": 10, "name": "Unknown Item 10"},
        {"id": 99, "name": "Safe Burger 99"},
    ]

    survivors = exclude_cart_items(candidates_without_metadata, cart)
    survivor_ids = {c["id"] for c in survivors}

    assert 65 in survivor_ids, "Candidate 65 should not be excluded by meal side ID collision"
    assert 80 in survivor_ids, "Candidate 80 should not be excluded by meal drink ID collision"
    assert 99 in survivor_ids, "Candidate 99 has no collision and should survive"
    assert 7 not in survivor_ids, "Candidate 7 matches meal main_item ID and should be excluded"
    assert 10 not in survivor_ids, "Candidate 10 matches standalone item ID and should be excluded"
    assert len(survivors) == 3

    print("PASS: test_unknown_category_candidate_side_drink_id_collision")


if __name__ == "__main__":
    test_cart_exclusion_by_id()
    test_cart_exclusion_by_name()
    test_meal_burger_exclusion_scenarios()
    test_unknown_category_candidate_side_drink_id_collision()
    print("\nALL CART EXCLUSION TESTS PASSED!")
