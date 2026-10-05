"""
Integration Test: Cross-Category Recommendations + Module 7 Cart Exclusion
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, backend_dir)

from services.menu_service import get_product, get_category
from services.productservice import get_product_recommendations
from services.modules.m01_dietary_lock import get_item_food_type
from services.modules.m07_cart_exclusion import exclude_cart_items


def test_cross_category_recommendations():
    product = get_product("Paneer Whopper")
    assert product is not None, "Product 'Paneer Whopper' should exist"

    recs = get_product_recommendations(product, cart=[])
    assert len(recs) == 3, f"Expected 3 recommendations, got {len(recs)}"

    cats = [r.get("category") for r in recs]
    assert "side" in cats, f"Expected side in recommendations, got {cats}"
    assert "drink" in cats, f"Expected drink in recommendations, got {cats}"
    assert "dessert" in cats, f"Expected dessert in recommendations, got {cats}"
    print("PASS: test_cross_category_recommendations (Side + Drink + Dessert)")


def test_cross_category_with_cart_exclusion():
    product = get_product("Paneer Whopper")
    assert product is not None

    # Get baseline recommendations
    initial_recs = get_product_recommendations(product, cart=[])
    first_side = next(r for r in initial_recs if r.get("category") == "side")

    # Now put that first side into the cart
    cart = [{"id": first_side.get("id"), "name": first_side.get("name")}]
    updated_recs = get_product_recommendations(product, cart=cart)

    rec_names = [r.get("name") for r in updated_recs]
    rec_ids = [r.get("id") for r in updated_recs]

    assert first_side.get("id") not in rec_ids, f"Cart item {first_side['name']} should be excluded by ID"
    assert first_side.get("name") not in rec_names, f"Cart item {first_side['name']} should be excluded by name"
    assert len(updated_recs) == 3, f"Expected 3 recommendations with substitute, got {len(updated_recs)}"
    print(f"PASS: test_cross_category_with_cart_exclusion ({first_side['name']} excluded -> substituted)")


def test_cross_category_dietary_veg_lock():
    # Paneer Whopper is Veg
    product = get_product("Paneer Whopper")
    assert product is not None
    assert get_item_food_type(product) == "veg"

    recs = get_product_recommendations(product, cart=[])
    # All recommendations MUST be veg (zero non-veg allowed)
    for r in recs:
        ft = get_item_food_type(r)
        assert ft == "veg", f"Non-veg item {r['name']} ({ft}) leaked into veg product recommendations!"
    print("PASS: test_cross_category_dietary_veg_lock (100% veg recommended for veg product)")


def test_cross_category_dietary_non_veg_prioritization():
    # Chicken Whopper is Non-Veg
    product = get_product("Chicken Whopper")
    assert product is not None
    assert get_item_food_type(product) == "non_veg"

    recs = get_product_recommendations(product, cart=[])
    # Should recommend non-veg side if available (e.g. wings/nuggets)
    side_rec = next((r for r in recs if r.get("category") == "side"), None)
    if side_rec:
        # Non-veg sides exist in DB (e.g., Chicken Wings / Nuggets), verify it prioritized non-veg
        assert get_item_food_type(side_rec) == "non_veg", f"Expected non-veg side prioritized for non-veg product, got {side_rec}"
    print("PASS: test_cross_category_dietary_non_veg_prioritization")


if __name__ == "__main__":
    test_cross_category_recommendations()
    test_cross_category_with_cart_exclusion()
    test_cross_category_dietary_veg_lock()
    test_cross_category_dietary_non_veg_prioritization()
    print("\nALL INTEGRATION TESTS PASSED!")
