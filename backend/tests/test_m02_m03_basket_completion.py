"""
backend/tests/test_m02_m03_basket_completion.py
Comprehensive Unit Test Suite for Module A (Role-Aware Basket Completion & Sensory Pairing Engine)
"""

import pytest
from services.modules.m02_m03_basket_completion import (
    parse_product_role,
    compute_sensory_score,
    generate_candidate_signals,
    rank_candidates_with_sensory,
    build_checkout_3slot_recommendations,
)


def test_parse_product_role_explicit_metadata():
    item = {
        "id": 1,
        "name": "Whopper",
        "category": "burger",
        "meal_role": "main",
        "subrole": "whopper_burger",
        "satisfies_roles": ["main"],
        "temperature": "hot",
        "texture": "crunchy",
        "flavor_profile": "savory",
    }
    role = parse_product_role(item)
    assert role["meal_role"] == "main"
    assert role["subrole"] == "whopper_burger"
    assert "main" in role["satisfies_roles"]
    assert role["temperature"] == "hot"


def test_parse_product_role_missing_metadata_no_invented_roles():
    item = {"id": 99, "name": "Mystery Product"}
    role = parse_product_role(item)
    assert role["meal_role"] == "unassigned"
    assert role["subrole"] == "unassigned"
    assert role["satisfies_roles"] == []
    assert role["temperature"] is None


def test_shake_satisfies_roles():
    item = {"id": 50, "name": "KitKat Shake", "category": "drink"}
    role = parse_product_role(item)
    assert "drink" in role["satisfies_roles"]
    assert role["meal_role"] == "drink"


def test_compute_sensory_score_hot_cold_and_crunchy_smooth():
    cart = [
        {"id": 1, "name": "Whopper", "category": "burger", "temperature": "hot", "flavor_profile": "savory"},
        {"id": 65, "name": "Fries", "category": "side", "texture": "crunchy", "flavor_profile": "spicy"},
    ]
    cold_drink = {"id": 40, "name": "Coke", "category": "drink", "temperature": "cold"}
    smooth_dip = {"id": 70, "name": "Fiery Dip", "category": "side", "texture": "smooth"}

    score_drink = compute_sensory_score(cart, cold_drink)
    score_dip = compute_sensory_score(cart, smooth_dip)

    assert score_drink > 0.0
    assert score_dip > 0.0


def test_compute_sensory_score_missing_metadata_returns_neutral():
    cart = [{"id": 1, "name": "Whopper"}]
    unknown_item = {"id": 999, "name": "Unknown Product"}

    score = compute_sensory_score(cart, unknown_item)
    assert score == 0.0


def test_generate_candidate_signals_structured_dict():
    cart = [{"id": 1, "name": "Whopper", "category": "burger", "temperature": "hot"}]
    candidate = {"id": 40, "name": "Cold Coffee", "category": "drink", "price": 120, "temperature": "cold"}

    signals = generate_candidate_signals(candidate, cart, placement="normal")
    assert isinstance(signals, dict)
    assert signals["candidate_id"] == 40
    assert signals["role_fit"] == "drink"
    assert "SENSORY_AFFINITY_BOOST" in signals["reason_codes"]
    assert signals["confidence"] > 0.50


def test_rank_candidates_with_sensory_soft_ranking():
    cart = [{"id": 1, "name": "Spicy Peri Peri Fries", "category": "side", "flavor_profile": "spicy"}]
    candidates = [
        {"id": 10, "name": "Plain Water", "category": "drink", "priority": 5.0},
        {"id": 50, "name": "KitKat Shake", "category": "drink", "priority": 5.0, "temperature": "cold", "flavor_profile": "sweet"},
    ]

    ranked = rank_candidates_with_sensory(candidates, cart)
    assert len(ranked) == 2
    # KitKat Shake receives sensory affinity boost for spicy -> sweet/cold
    assert ranked[0]["id"] == 50


def test_checkout_3slot_recommendations_slots_and_deduplication():
    cart = [{"id": 65, "name": "Fries (Medium)", "category": "side"}]  # finger food triggers M6 dip
    all_sides = [
        {"id": 70, "name": "Fiery Dip", "category": "side", "price": 25, "texture": "smooth"},
        {"id": 66, "name": "Onion Rings", "category": "side", "price": 99},
    ]
    all_drinks = [
        {"id": 40, "name": "Coca Cola", "category": "drink", "price": 60, "temperature": "cold"},
    ]
    all_desserts = [
        {"id": 80, "name": "BK Fusion Sundae", "category": "dessert", "price": 110},
    ]

    recs = build_checkout_3slot_recommendations(
        cart=cart,
        all_sides=all_sides,
        all_drinks=all_drinks,
        all_desserts=all_desserts,
    )

    assert len(recs) == 3
    # Slot 1 should be the M6 gated dip
    assert recs[0]["id"] == 70
    assert recs[0]["slot"] == 1
    # Slot 2 should be Best Match
    assert recs[1]["slot"] == 2
    # Slot 3 should be Sweet Finish
    assert recs[2]["id"] == 80
    assert recs[2]["slot"] == 3

    # Verify no duplicate IDs
    rec_ids = [r["id"] for r in recs]
    assert len(rec_ids) == len(set(rec_ids))


def test_shake_in_cart_does_not_suppress_sundae():
    cart = [
        {"id": 1, "name": "Whopper", "category": "burger"},
        {"id": 50, "name": "Chocolate Shake", "category": "drink"},
    ]
    all_sides = [{"id": 65, "name": "Fries", "category": "side", "price": 90}]
    all_drinks = [{"id": 40, "name": "Coke", "category": "drink", "price": 60}]
    all_desserts = [{"id": 80, "name": "BK Fusion Sundae", "category": "dessert", "price": 110}]

    recs = build_checkout_3slot_recommendations(
        cart=cart,
        all_sides=all_sides,
        all_drinks=all_drinks,
        all_desserts=all_desserts,
    )

    # Sundae should still appear in Slot 3
    dessert_recs = [r for r in recs if r.get("id") == 80]
    assert len(dessert_recs) == 1


def test_checkout_dynamic_card_count_fewer_candidates():
    cart = [{"id": 1, "name": "Whopper", "category": "burger"}]
    all_sides = []
    all_drinks = [{"id": 40, "name": "Coke", "category": "drink", "price": 60}]
    all_desserts = []

    recs = build_checkout_3slot_recommendations(
        cart=cart,
        all_sides=all_sides,
        all_drinks=all_drinks,
        all_desserts=all_desserts,
    )

    # Only 1 candidate available (Coke) -> returns 1 card gracefully
    assert len(recs) == 1
    assert recs[0]["id"] == 40


def test_flavor_harmony_peri_peri_matching():
    cart = [{"id": 1, "name": "Peri Peri Veg Burger", "category": "burger", "flavor_profile": "spicy peri peri"}]
    plain_fries = {"id": 65, "name": "Classic Fries", "category": "side", "priority": 5.0}
    peri_fries = {"id": 66, "name": "King Peri Peri Fries", "category": "side", "priority": 5.0}

    score_plain = compute_sensory_score(cart, plain_fries)
    score_peri = compute_sensory_score(cart, peri_fries)

    # Peri Peri Fries receives flavor_harmony boost
    assert score_peri > score_plain


def test_meal_customizer_options_ranking():
    from services.meal_service import organize_meal_options
    main_burger = {"id": 1, "name": "Peri Peri Chicken Burger", "category": "burger", "flavor_profile": "spicy peri peri"}
    options = [
        {"id": 65, "name": "Classic Fries", "category": "side", "extra_price": 0, "is_default": True},
        {"id": 66, "name": "King Peri Peri Fries", "category": "side", "extra_price": 20, "is_default": False},
    ]

    organized = organize_meal_options(options, food_preference="non_veg", main_product=main_burger)
    # Peri Peri Fries should move up because of high Module A sensory & flavor affinity!
    assert organized[0]["id"] == 66

