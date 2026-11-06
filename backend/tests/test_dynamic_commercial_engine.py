"""
tests/test_dynamic_commercial_engine.py
Unit and integration tests for Dynamic Commercial Engine (dynamic_commercial_engine.py)
"""

import pytest
from services.modules.dynamic_commercial_engine import (
    compute_budget_mindset,
    compute_commercial_margin_score,
    rank_candidates_commercial,
    get_product_page_rankings,
    get_meal_customizer_rankings,
    build_dynamic_checkout_shelf,
)


def test_compute_budget_mindset_empty_cart():
    assert compute_budget_mindset([]) == "neutral"
    assert compute_budget_mindset(None) == "neutral"


def test_compute_budget_mindset_low_budget():
    cart = [
        {"name": "Crispy Veg Burger", "price": 79.0, "unitPrice": 79.0, "quantity": 1}
    ]
    assert compute_budget_mindset(cart) == "low_budget"


def test_compute_budget_mindset_upsell():
    cart = [
        {"name": "Whopper Jr", "price": 129.0, "unitPrice": 129.0, "quantity": 1}
    ]
    assert compute_budget_mindset(cart) == "upsell"


def test_compute_budget_mindset_premium():
    cart = [
        {"name": "Whopper Double Cheese", "price": 189.0, "unitPrice": 189.0, "quantity": 1}
    ]
    assert compute_budget_mindset(cart) == "premium"


def test_commercial_margin_score_bounds():
    cand = {"name": "Chocolate Shake", "price": 160.0, "category": "dessert"}
    score = compute_commercial_margin_score(cand, cart=[], mindset="premium")
    assert 0.0 <= score <= 0.5


def test_rank_candidates_commercial():
    candidates = [
        {"id": 1, "name": "Classic Fries", "price": 99.0, "category": "side", "priority": 1.0},
        {"id": 2, "name": "King Peri Peri Fries", "price": 139.0, "category": "side", "priority": 1.0},
    ]
    cart = [{"name": "Peri Peri Chicken Burger", "price": 179.0, "flavor_profile": "spicy"}]

    ranked = rank_candidates_commercial(candidates, cart, placement="checkout")
    assert len(ranked) == 2
    # King Peri Peri Fries should rank higher due to Peri Peri flavor harmony with spicy cart burger
    assert ranked[0]["id"] == 2


def test_build_dynamic_checkout_shelf_3slots():
    cart = [{"name": "Peri Peri Fries", "category": "side"}]
    all_sides = [
        {"id": 10, "name": "Peri Peri Dip", "category": "sauce", "price": 30.0},
        {"id": 11, "name": "Cheesy Dip", "category": "dip", "price": 35.0},
    ]
    all_drinks = [
        {"id": 20, "name": "Coke Zero", "category": "drink", "price": 60.0},
    ]
    all_desserts = [
        {"id": 30, "name": "Chocolate Lava Cake", "category": "dessert", "price": 109.0},
    ]

    shelf = build_dynamic_checkout_shelf(cart, all_sides, all_drinks, all_desserts)

    # Slot 1 should surface single highest ranked dip for finger food cart
    assert len(shelf) <= 3
    slots = [item["slot"] for item in shelf]
    assert 1 in slots
    assert 2 in slots
    assert 3 in slots

    slot1 = next(item for item in shelf if item["slot"] == 1)
    assert "Dip" in slot1["name"] or "Sauce" in slot1["name"]


def test_build_dynamic_checkout_shelf_suppress_dip_when_already_in_cart():
    # When dip is already in cart, Slot 1 does not force a duplicate dip
    cart = [
        {"name": "Peri Peri Fries", "category": "side"},
        {"name": "Peri Peri Dip", "category": "sauce"},
    ]
    all_sides = [
        {"id": 10, "name": "Peri Peri Dip", "category": "sauce", "price": 30.0},
        {"id": 11, "name": "Cheesy Dip", "category": "dip", "price": 35.0},
    ]
    all_drinks = [
        {"id": 20, "name": "Coke Zero", "category": "drink", "price": 60.0},
    ]
    all_desserts = [
        {"id": 30, "name": "Chocolate Lava Cake", "category": "dessert", "price": 109.0},
    ]

    shelf = build_dynamic_checkout_shelf(cart, all_sides, all_drinks, all_desserts)
    # Check that Peri Peri Dip is not duplicated
    names = [i["name"] for i in shelf]
    assert "Peri Peri Dip" not in names


def test_checkout_shelf_enforces_m1_dietary_lock():
    # Vegetarian cart: non-veg sides and non-veg desserts MUST be excluded
    cart = [
        {"name": "Crispy Veg Burger", "category": "burger", "food_type": "veg"}
    ]
    all_sides = [
        {"id": 1, "name": "Chicken Nuggets", "category": "side", "food_type": "non_veg", "price": 149.0},
        {"id": 2, "name": "Classic Fries", "category": "side", "food_type": "veg", "price": 99.0},
    ]
    all_drinks = [
        {"id": 3, "name": "Coke Zero", "category": "drink", "food_type": "veg", "price": 60.0},
    ]
    all_desserts = [
        {"id": 4, "name": "Egg Pudding", "category": "dessert", "food_type": "non_veg", "price": 89.0},
        {"id": 5, "name": "Chocolate Lava Cake", "category": "dessert", "food_type": "veg", "price": 109.0},
    ]

    shelf = build_dynamic_checkout_shelf(cart, all_sides, all_drinks, all_desserts)
    recommended_names = [item["name"] for item in shelf]

    assert "Chicken Nuggets" not in recommended_names
    assert "Egg Pudding" not in recommended_names
    assert "Classic Fries" in recommended_names or "Chocolate Lava Cake" in recommended_names


def test_extra_price_meal_customizer_scoring():
    # Free default upgrade (+0.0) should get a high value commercial score boost
    cand_free = {"name": "Classic Fries", "price": 99.0, "extra_price": 0.0}
    cand_costly = {"name": "Gourmet Loaded Fries", "price": 160.0, "extra_price": 60.0}

    score_free = compute_commercial_margin_score(cand_free, cart=[])
    score_costly = compute_commercial_margin_score(cand_costly, cart=[])

    assert score_free >= score_costly


def test_meal_service_integration_with_central_engine():
    from services.meal_service import organize_meal_options

    options = [
        {"id": 1, "name": "King Peri Peri Fries", "extra_price": 30.0, "food_type": "veg", "flavor_profile": "spicy"},
        {"id": 2, "name": "Classic Fries", "extra_price": 0.0, "food_type": "veg", "is_default": True},
    ]
    main = {"name": "Peri Peri Burger", "flavor_profile": "spicy"}
    organized = organize_meal_options(options, food_preference="veg", cart=[], main_product=main)

    assert len(organized) == 2
    # King Peri Peri Fries should rank higher due to Peri Peri flavor harmony with Peri Peri main burger
    assert organized[0]["id"] == 1


def test_explicit_veg_preference_checkout_with_empty_cart():
    # Explicitly vegetarian customer with EMPTY cart must NOT receive non-veg recommendations
    cart = []
    all_sides = [
        {"id": 1, "name": "Chicken Nuggets", "category": "side", "food_type": "non_veg", "price": 149.0},
        {"id": 2, "name": "Classic Fries", "category": "side", "food_type": "veg", "price": 99.0},
    ]
    all_drinks = [
        {"id": 3, "name": "Coke Zero", "category": "drink", "food_type": "veg", "price": 60.0},
    ]
    all_desserts = [
        {"id": 4, "name": "Chicken Pie", "category": "dessert", "food_type": "non_veg", "price": 120.0},
        {"id": 5, "name": "Chocolate Lava Cake", "category": "dessert", "food_type": "veg", "price": 109.0},
    ]

    shelf = build_dynamic_checkout_shelf(cart, all_sides, all_drinks, all_desserts, food_preference="veg")
    recommended_names = [item["name"] for item in shelf]

    assert "Chicken Nuggets" not in recommended_names
    assert "Chicken Pie" not in recommended_names
    assert "Classic Fries" in recommended_names or "Chocolate Lava Cake" in recommended_names


def test_mixed_cart_checkout_dietary_behavior():
    # Mixed cart (contains non-veg item): preference defaults to unrestricted 'both' unless explicit preference passed
    cart = [
        {"name": "Chicken Whopper", "category": "burger", "food_type": "non_veg"}
    ]
    all_sides = [
        {"id": 1, "name": "Chicken Wings", "category": "side", "food_type": "non_veg", "price": 169.0},
        {"id": 2, "name": "Classic Fries", "category": "side", "food_type": "veg", "price": 99.0},
    ]
    all_drinks = [
        {"id": 3, "name": "Coke Zero", "category": "drink", "food_type": "veg", "price": 60.0},
    ]
    all_desserts = [
        {"id": 4, "name": "Chocolate Lava Cake", "category": "dessert", "food_type": "veg", "price": 109.0},
    ]

    shelf = build_dynamic_checkout_shelf(cart, all_sides, all_drinks, all_desserts, food_preference="both")
    assert len(shelf) >= 1
