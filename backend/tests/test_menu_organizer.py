"""
Unit & Integration Tests for backend/services/menu_organizer.py

Verifies:
1. Safe Price Parsing: numeric, numeric strings, missing, None, malformed, dict, negative.
   Ensures malformed prices do not crash menu organization, are not mutated,
   and are not falsely rewarded as value anchors or budget boosts.
2. Dietary Filtering using Canonical M01:
   - veg, non_veg, unrestricted browsing (None and 'both')
   - Drinks with serving type ('hot'/'cold') vs foodType ('veg'/'non_veg')
   - Missing and unknown dietary metadata handling
   - Both supported database fields: foodType and food_type
3. Stable Cart Item Identification:
   - Matching across separate dictionary objects
   - ID normalization (int 12 vs string "12")
   - Duplicate names with different IDs preserved (not merged)
   - Products without IDs deduplicated and handled gracefully
   - Cart items moved to the very end of sections
4. Budget-Aware Strategic Ordering (Top 4 Viewport):
   - Respects all 4 mindsets: low_budget, upsell, premium, neutral
   - In low_budget, prefers affordable hero candidate (does not force premium item into Slot 1)
   - In upsell/premium/neutral, preserves high-margin hero in Slot 1
   - Slot 3 Value Anchor strictly <= 119
   - No products duplicated or dropped
5. Stock and Expiry Eligibility:
   - Excludes zero, negative, and malformed stock
   - Excludes expired products and malformed expiry dates
   - Permits valid unexpired products and missing/None expiry (untracked/non-perishable)
6. Merchandising Rules & Edge Cases:
   - Empty catalog / empty sections resilience
   - Condiment / Dip section gating with and without finger foods in cart
"""
import sys
import os
from datetime import date, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.menu_organizer import (
    organize_menu_sections,
    compute_budget_mindset,
    _arrange_strategic_top4,
    _parse_price,
    _get_product_key,
    is_item_in_cart,
)


# =========================================================
# 1. SAFE PRICE PARSING TESTS (SECTION 6)
# =========================================================

def test_parse_price_robustness():
    # 1. Numeric values
    assert _parse_price({"price": 150}) == 150.0
    assert _parse_price({"price": 199.50}) == 199.50

    # 2. Numeric strings
    assert _parse_price({"price": "140"}) == 140.0
    assert _parse_price({"price": "249.99"}) == 249.99

    # 3. None and missing -> safely returns None
    assert _parse_price({"price": None}) is None
    assert _parse_price({}) is None

    # 4. Malformed strings ('N/A', 'invalid', '') -> safely returns None
    assert _parse_price({"price": "N/A"}) is None
    assert _parse_price({"price": "invalid"}) is None
    assert _parse_price({"price": ""}) is None

    # 5. Nested dictionary price format
    assert _parse_price({"price": {"amount": 175.0}}) == 175.0
    assert _parse_price({"price": {"price": 185.0}}) == 185.0

    # 6. Negative price clamped to None
    assert _parse_price({"price": -20.0}) is None

    # 7. Non-dict input
    assert _parse_price(None) is None
    assert _parse_price("150") is None

    # 8. Field name fallbacks: unitPrice and original_price
    assert _parse_price({"unitPrice": 120.0}) == 120.0
    assert _parse_price({"original_price": "80.0"}) == 80.0
    print("PASS: test_parse_price_robustness")


def test_malformed_price_does_not_crash_menu_organization():
    raw_sections = [
        {
            "id": "sec-whopper",
            "title": "Whopper",
            "products": [
                {"id": "w1", "name": "Veg Whopper", "price": "N/A", "foodType": "veg", "stock": 10},
                {"id": "w2", "name": "Chicken Whopper", "price": 199.0, "foodType": "non_veg", "stock": 10},
                {"id": "w3", "name": "Mutton Whopper", "price": None, "foodType": "non_veg", "stock": 10},
                {"id": "w4", "name": "Crispy Veg", "price": "79.0", "foodType": "veg", "stock": 10},
            ]
        }
    ]

    result = organize_menu_sections("burger", raw_sections, preference=None, cart=[])
    assert len(result) == 1, "Expected 1 organized section"
    prods = result[0]["products"]
    assert len(prods) == 4, f"Expected 4 products, got {len(prods)}"

    # Verify that the original product dict's price field was NOT mutated
    w1 = next(p for p in prods if p["id"] == "w1")
    assert w1["price"] == "N/A", "Original price key must remain unchanged in output"

    w3 = next(p for p in prods if p["id"] == "w3")
    assert w3["price"] is None, "Original None price must remain unchanged in output"
    print("PASS: test_malformed_price_does_not_crash_menu_organization")


def test_malformed_price_not_rewarded_by_affordability_or_value_anchor():
    products = [
        {"id": "p1", "name": "Whopper Premium", "price": 180.0, "stock": 10},
        {"id": "p2", "name": "Burger Mid", "price": 130.0, "stock": 10},
        {"id": "p3", "name": "Burger Broken Price", "price": "N/A", "stock": 10},
        {"id": "p4", "name": "Burger Value", "price": 89.0, "stock": 10},
    ]
    raw_sections = [{"id": "sec-1", "title": "Burgers", "products": products}]
    result = organize_menu_sections("burger", raw_sections, preference=None, cart=[])
    prods = result[0]["products"]

    # Slot 3 (index 2) must be the genuine value item (<= 119), NOT the malformed item p3
    assert prods[2]["id"] == "p4", f"Slot 3 must be genuine value anchor p4, got {prods[2]['id']}"
    print("PASS: test_malformed_price_not_rewarded_by_affordability_or_value_anchor")


# =========================================================
# 2. DIETARY FILTERING TESTS USING M01 (SECTION 2)
# =========================================================

def test_dietary_filtering_veg_lock():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "b1", "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10},
                {"id": "b2", "name": "Chicken Whopper", "price": 199.0, "foodType": "non_veg", "stock": 10},
                {"id": "b3", "name": "Veg Whopper", "price": 179.0, "food_type": "veg", "stock": 10},
                {"id": "b4", "name": "Unknown Burger", "price": 150.0, "foodType": "unknown", "stock": 10},
                {"id": "b5", "name": "Missing Meta", "price": 120.0, "stock": 10},
            ]
        }
    ]
    result = organize_menu_sections("burger", raw_sections, preference="veg", cart=[])
    prods = result[0]["products"]
    prod_ids = [p["id"] for p in prods]

    assert "b1" in prod_ids, "Veg item b1 (foodType) must be included"
    assert "b3" in prod_ids, "Veg item b3 (food_type) must be included"
    assert "b2" not in prod_ids, "Non-veg item b2 must be excluded under veg lock"
    assert "b4" not in prod_ids, "Unknown dietary metadata must NOT be silently classified as veg"
    assert "b5" not in prod_ids, "Missing dietary metadata must NOT be classified as veg"
    print("PASS: test_dietary_filtering_veg_lock")


def test_dietary_filtering_non_veg_lock():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "b1", "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10},
                {"id": "b2", "name": "Chicken Whopper", "price": 199.0, "foodType": "non_veg", "stock": 10},
                {"id": "b3", "name": "Mutton Burger", "price": 220.0, "food_type": "non_veg", "stock": 10},
            ]
        }
    ]
    result = organize_menu_sections("burger", raw_sections, preference="non_veg", cart=[])
    prods = result[0]["products"]
    prod_ids = [p["id"] for p in prods]

    assert "b2" in prod_ids and "b3" in prod_ids
    assert "b1" not in prod_ids
    print("PASS: test_dietary_filtering_non_veg_lock")


def test_dietary_unrestricted_browsing():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "b1", "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10},
                {"id": "b2", "name": "Chicken Whopper", "price": 199.0, "foodType": "non_veg", "stock": 10},
                {"id": "b3", "name": "Untracked Food", "price": 99.0, "stock": 10},
            ]
        }
    ]
    # preference=None -> unrestricted browsing: both veg and non-veg remain visible
    res_none = organize_menu_sections("burger", raw_sections, preference=None, cart=[])
    assert len(res_none[0]["products"]) == 3, "preference=None must preserve unrestricted browsing"

    # preference="both" -> unrestricted browsing
    res_both = organize_menu_sections("burger", raw_sections, preference="both", cart=[])
    assert len(res_both[0]["products"]) == 3, "preference='both' must preserve unrestricted browsing"
    print("PASS: test_dietary_unrestricted_browsing")


def test_dietary_drinks_hot_cold_not_confused_with_food_type():
    raw_sections = [
        {
            "id": "drinks",
            "title": "Drinks",
            "products": [
                {"id": "d1", "name": "Cold Coffee", "price": 99.0, "type": "cold", "foodType": "veg", "stock": 10},
                {"id": "d2", "name": "Hot Chocolate", "price": 119.0, "type": "hot", "foodType": "veg", "stock": 10},
                {"id": "d3", "name": "Cold Soda Untracked", "price": 60.0, "type": "cold", "stock": 10},
            ]
        }
    ]
    result = organize_menu_sections("drink", raw_sections, preference="veg", cart=[])
    prods = result[0]["products"]
    prod_ids = [p["id"] for p in prods]

    assert "d1" in prod_ids, "Veg cold drink must be included"
    assert "d2" in prod_ids, "Veg hot drink must be included"
    assert "d3" not in prod_ids, "Drink with only type='cold' must not be classified as veg"
    print("PASS: test_dietary_drinks_hot_cold_not_confused_with_food_type")


# =========================================================
# 3. CART ITEM IDENTIFICATION & STABLE IDENTITY (SECTION 3)
# =========================================================

def test_cart_item_identification_separate_dict_objects():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "b1", "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10},
                {"id": "b2", "name": "Crispy Veg", "price": 79.0, "foodType": "veg", "stock": 10},
            ]
        }
    ]
    # Cart contains a separate dictionary object with same ID
    cart = [{"id": "b1", "name": "Paneer Royale", "price": 199.0}]
    assert is_item_in_cart(raw_sections[0]["products"][0], cart) is True

    result = organize_menu_sections("burger", raw_sections, preference="veg", cart=cart)
    products = result[0]["products"]

    # Paneer Royale (in cart) must be placed at the very end
    assert products[-1]["id"] == "b1", "Carted item must be placed at the end of section"
    print("PASS: test_cart_item_identification_separate_dict_objects")


def test_cart_item_id_normalization_int_vs_string():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": 12, "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10},
                {"id": 13, "name": "Crispy Veg", "price": 79.0, "foodType": "veg", "stock": 10},
            ]
        }
    ]
    # Cart has string ID "12"
    cart = [{"id": "12", "name": "Paneer Royale"}]
    assert is_item_in_cart(raw_sections[0]["products"][0], cart) is True

    result = organize_menu_sections("burger", raw_sections, preference="veg", cart=cart)
    products = result[0]["products"]
    assert products[-1]["id"] == 12, "Integer ID 12 must match cart string '12' and be placed last"
    print("PASS: test_cart_item_id_normalization_int_vs_string")


def test_cart_item_duplicate_names_different_ids_not_merged():
    raw_sections = [
        {
            "id": "sec-dips",
            "title": "Dips",
            "products": [
                {"id": "dip_1", "name": "Peri Peri Dip", "price": 25.0, "stock": 10},
                {"id": "dip_2", "name": "Peri Peri Dip", "price": 35.0, "stock": 10},
            ]
        }
    ]
    result = organize_menu_sections("side", raw_sections, preference=None, cart=[])
    prods = result[0]["products"]
    assert len(prods) == 2, "Products with same name but different IDs must NOT be merged"
    ids = {p["id"] for p in prods}
    assert ids == {"dip_1", "dip_2"}
    print("PASS: test_cart_item_duplicate_names_different_ids_not_merged")


def test_cart_item_products_without_ids():
    raw_sections = [
        {
            "id": "sec-desserts",
            "title": "Desserts",
            "products": [
                {"name": "Softie Vanilla", "price": 35.0, "stock": 10},
                {"name": "Softie Vanilla", "price": 35.0, "stock": 10},  # duplicate object
                {"name": "Choco Sundae", "price": 79.0, "stock": 10},
            ]
        }
    ]
    cart = [{"name": "Softie Vanilla", "price": 35.0}]
    result = organize_menu_sections("dessert", raw_sections, preference=None, cart=cart)
    prods = result[0]["products"]

    # Duplicates without ID must be deduplicated, and carted item at the end
    names = [p["name"] for p in prods]
    assert names.count("Softie Vanilla") == 1, "Duplicate items without ID must be deduplicated"
    assert prods[-1]["name"] == "Softie Vanilla", "Carted item without ID must be placed at the end"
    print("PASS: test_cart_item_products_without_ids")


def test_cart_item_missing_id_one_side_present_other():
    # Case A: Cart has name but no ID; Catalog item has ID and name
    raw_sections_a = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "b1", "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10},
                {"id": "b2", "name": "Crispy Veg", "price": 79.0, "foodType": "veg", "stock": 10},
            ]
        }
    ]
    cart_name_only = [{"name": "Paneer Royale"}]  # No ID
    result_a = organize_menu_sections("burger", raw_sections_a, preference="veg", cart=cart_name_only)
    assert result_a[0]["products"][-1]["id"] == "b1", "Item matching cart by name without ID must be moved to end"

    # Case B: Cart has ID but no name; Catalog item has ID and name
    cart_id_only = [{"id": "b1"}]  # No name
    result_b = organize_menu_sections("burger", raw_sections_a, preference="veg", cart=cart_id_only)
    assert result_b[0]["products"][-1]["id"] == "b1", "Item matching cart by ID without name must be moved to end"
    print("PASS: test_cart_item_missing_id_one_side_present_other")


def test_cart_item_meal_component_and_suffix_supported_by_m07():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "w1", "name": "Veg Whopper", "price": 179.0, "foodType": "veg", "stock": 10},
                {"id": "w2", "name": "Crispy Veg", "price": 79.0, "foodType": "veg", "stock": 10},
            ]
        }
    ]

    # Suffix stripping: 'Veg Whopper Regular Meal' matches catalog 'Veg Whopper'
    cart_with_suffix = [{"name": "Veg Whopper Regular Meal"}]
    res_suffix = organize_menu_sections("burger", raw_sections, preference="veg", cart=cart_with_suffix)
    assert res_suffix[0]["products"][-1]["id"] == "w1", "Cart meal suffix must match base catalog item"

    # Composite meal component: 'Combo Meal' containing 'burger' component
    cart_with_combo = [
        {
            "id": "combo_1",
            "name": "Super Saver Combo",
            "burger": {"id": "w1", "name": "Veg Whopper"}
        }
    ]
    res_combo = organize_menu_sections("burger", raw_sections, preference="veg", cart=cart_with_combo)
    assert res_combo[0]["products"][-1]["id"] == "w1", "Composite meal component must match base catalog item"
    print("PASS: test_cart_item_meal_component_and_suffix_supported_by_m07")


def test_duplicate_catalog_entries_deduplicated():
    item1 = {"id": "b1", "name": "Paneer Royale", "price": 199.0, "foodType": "veg", "stock": 10}
    item2 = {"id": "b2", "name": "Crispy Veg", "price": 79.0, "foodType": "veg", "stock": 10}
    # Duplicate item1 inserted twice in the raw section
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [item1, item2, item1]
        }
    ]
    result = organize_menu_sections("burger", raw_sections, preference="veg", cart=[])
    prods = result[0]["products"]
    assert len(prods) == 2, f"Duplicate catalog items with same ID must be deduplicated, got {len(prods)}"
    assert {p["id"] for p in prods} == {"b1", "b2"}
    print("PASS: test_duplicate_catalog_entries_deduplicated")


# =========================================================
# 4. STRATEGIC ORDERING & BUDGET MINDSETS (SECTION 4)
# =========================================================

def test_budget_mindsets_strategic_top4():
    # Catalog containing both an affordable hero candidate and a premium hero candidate
    catalog = [
        {"id": "p_prem_hero", "name": "Whopper Gourmet Double", "price": 220.0, "stock": 10},
        {"id": "p_afford_hero", "name": "Whopper Jr Value", "price": 99.0, "stock": 10},
        {"id": "p_reg", "name": "Regular Burger", "price": 130.0, "stock": 10},
        {"id": "p_val", "name": "Crispy Budget", "price": 69.0, "stock": 10},
        {"id": "p_treat", "name": "Special Treat", "price": 160.0, "stock": 10},
    ]

    # 1. low_budget mindset: must prefer affordable hero (Whopper Jr Value, 99.0) in Slot 1
    top4_low = _arrange_strategic_top4(catalog, mindset="low_budget")
    assert top4_low[0]["id"] == "p_afford_hero", (
        f"In low_budget, Slot 1 must be affordable hero p_afford_hero, got {top4_low[0]['id']}"
    )
    assert len(top4_low) == 5, "No items dropped or duplicated in low_budget"
    assert len({p["id"] for p in top4_low}) == 5

    # 2. premium mindset: must choose high-margin hero (Whopper Gourmet Double, 220.0) in Slot 1
    top4_prem = _arrange_strategic_top4(catalog, mindset="premium")
    assert top4_prem[0]["id"] == "p_prem_hero", (
        f"In premium, Slot 1 must be premium hero p_prem_hero, got {top4_prem[0]['id']}"
    )
    assert len(top4_prem) == 5

    # 3. upsell mindset: preserves high-margin hero in Slot 1
    top4_upsell = _arrange_strategic_top4(catalog, mindset="upsell")
    assert top4_upsell[0]["id"] == "p_prem_hero"
    assert len(top4_upsell) == 5

    # 4. neutral mindset: preserves high-margin hero in Slot 1
    top4_neutral = _arrange_strategic_top4(catalog, mindset="neutral")
    assert top4_neutral[0]["id"] == "p_prem_hero"
    assert len(top4_neutral) == 5

    # In all mindsets, Slot 3 must be a value anchor <= 119
    for mindset_name, top4 in [("low_budget", top4_low), ("premium", top4_prem), ("upsell", top4_upsell), ("neutral", top4_neutral)]:
        assert top4[2]["price"] <= 119.0, f"Slot 3 in {mindset_name} must be value anchor <= 119"

    print("PASS: test_budget_mindsets_strategic_top4")


def test_budget_mindset_detection():
    # 1. Empty cart -> neutral
    assert compute_budget_mindset([]) == "neutral"
    assert compute_budget_mindset(None) == "neutral"

    # 2. Premium cart -> recent >= 140 or max >= 170
    cart_prem = [{"name": "Whopper", "price": 199.0}]
    assert compute_budget_mindset(cart_prem) == "premium"

    # 3. Upsell cart -> max >= 110
    cart_upsell = [{"name": "Fries Large", "price": 120.0}]
    assert compute_budget_mindset(cart_upsell) == "upsell"

    # 4. Low budget cart -> all < 100
    cart_low = [{"name": "Softie", "price": 35.0}, {"name": "Small Fries", "price": 60.0}]
    assert compute_budget_mindset(cart_low) == "low_budget"

    # 5. Cart with malformed price strings -> handles gracefully
    cart_malformed = [{"name": "Bad Item", "price": "N/A"}]
    assert compute_budget_mindset(cart_malformed) == "neutral"
    print("PASS: test_budget_mindset_detection")


# =========================================================
# 5. STOCK AND EXPIRY ELIGIBILITY (SECTION 5)
# =========================================================

def test_stock_and_expiry_eligibility():
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "p_zero_stock", "name": "Zero Stock Burger", "price": 100.0, "stock": 0},
                {"id": "p_neg_stock", "name": "Negative Stock Burger", "price": 100.0, "stock": -2},
                {"id": "p_malformed_stock", "name": "Bad Stock Burger", "price": 100.0, "stock": "out-of-stock"},
                {"id": "p_expired", "name": "Expired Burger", "price": 100.0, "stock": 10, "expiry": yesterday.isoformat()},
                {"id": "p_malformed_expiry", "name": "Bad Expiry Burger", "price": 100.0, "stock": 10, "expiry": "not-a-date"},
                {"id": "p_valid_expiry", "name": "Valid Expiry Burger", "price": 120.0, "stock": 10, "expiry": tomorrow.isoformat()},
                {"id": "p_missing_expiry", "name": "Non-perishable Burger", "price": 110.0, "stock": 10, "expiry": None},
            ]
        }
    ]

    result = organize_menu_sections("burger", raw_sections, preference=None, cart=[])
    assert len(result) == 1
    survivors = result[0]["products"]
    survivor_ids = {p["id"] for p in survivors}

    # Zero, negative, malformed stock must be excluded
    assert "p_zero_stock" not in survivor_ids, "Zero stock must be excluded"
    assert "p_neg_stock" not in survivor_ids, "Negative stock must be excluded"
    assert "p_malformed_stock" not in survivor_ids, "Malformed stock must be excluded"

    # Expired and malformed expiry must be excluded
    assert "p_expired" not in survivor_ids, "Expired product must be excluded"
    assert "p_malformed_expiry" not in survivor_ids, "Malformed expiry product must be excluded"

    # Valid expiry and missing expiry (non-perishable) must be included
    assert "p_valid_expiry" in survivor_ids, "Valid future expiry must be included"
    assert "p_missing_expiry" in survivor_ids, "Missing expiry must be included"
    print("PASS: test_stock_and_expiry_eligibility")


def test_stock_missing_and_none_excluded():
    raw_sections = [
        {
            "id": "burgers",
            "title": "Burgers",
            "products": [
                {"id": "p_none_stock", "name": "None Stock Burger", "price": 100.0, "stock": None},
                {"id": "p_missing_stock", "name": "Missing Stock Burger", "price": 100.0},
                {"id": "p_positive_stock", "name": "Positive Stock Burger", "price": 100.0, "stock": 5},
            ]
        }
    ]
    result = organize_menu_sections("burger", raw_sections, preference=None, cart=[])
    assert len(result) == 1
    survivors = result[0]["products"]
    survivor_ids = {p["id"] for p in survivors}

    assert "p_none_stock" not in survivor_ids, "stock=None must be excluded"
    assert "p_missing_stock" not in survivor_ids, "Missing stock key must be excluded"
    assert "p_positive_stock" in survivor_ids, "Positive stock must be included"
    print("PASS: test_stock_missing_and_none_excluded")


def test_legitimate_zero_price_meal_component_filtering():
    raw_sections = [
        {
            "id": "sides",
            "title": "Sides",
            "products": [
                # 1. Meal-only item with price 0 -> excluded
                {"id": "m1", "name": "Meal Fry Addon", "price": 0.0, "is_meal_only": True, "stock": 10},
                # 2. Price 0 with missing is_meal_only -> fallback excluded
                {"id": "m2", "name": "Zero Price Untracked", "price": 0.0, "stock": 10},
                # 3. Legitimate item with price 0 but is_meal_only == False -> kept
                {"id": "m3", "name": "Free Promo Dip", "price": 0.0, "is_meal_only": False, "stock": 10},
                # 4. Normal item
                {"id": "m4", "name": "Standard Dip", "price": 25.0, "is_meal_only": False, "stock": 10},
            ]
        }
    ]
    result = organize_menu_sections("side", raw_sections, preference=None, cart=[])
    survivors = result[0]["products"]
    survivor_ids = {p["id"] for p in survivors}

    assert "m1" not in survivor_ids, "is_meal_only=True must be excluded"
    assert "m2" not in survivor_ids, "price=0 with missing is_meal_only must be excluded by fallback"
    assert "m3" in survivor_ids, "is_meal_only=False must be kept even if price is 0"
    assert "m4" in survivor_ids, "Standard priced item must be kept"
    print("PASS: test_legitimate_zero_price_meal_component_filtering")


def test_actual_repository_serializer_compatibility():
    # Construct items matching the exact schema returned by menu_repository.serialize_menu_item()
    serialized_products = [
        {
            "id": 101,
            "name": "Veg Whopper",
            "shortDescription": "Crispy veg patty with fresh lettuce and mayo",
            "longDescription": "The classic flame-grilled veg whopper",
            "price": 179.0,
            "image": "/images/whopper.png",
            "meal_image": "/images/whopper_meal.png",
            "type": "veg",
            "foodType": "veg",
            "is_meal_available": True,
            "stock": 25,
            "expiry": (date.today() + timedelta(days=10)).isoformat(),
            "category": "burger",
            "section": "Whopper",
            "section_order": 1,
            "display_order": 1,
            "meal_role": "burger",
            "is_meal_only": False,
        },
        {
            "id": 102,
            "name": "Paneer Royale",
            "shortDescription": "Thick paneer patty",
            "longDescription": "Premium paneer burger",
            "price": 199.0,
            "image": "/images/paneer.png",
            "meal_image": "/images/paneer_meal.png",
            "type": "veg",
            "foodType": "veg",
            "is_meal_available": True,
            "stock": 15,
            "expiry": (date.today() + timedelta(days=15)).isoformat(),
            "category": "burger",
            "section": "Whopper",
            "section_order": 1,
            "display_order": 2,
            "meal_role": "burger",
            "is_meal_only": False,
        },
        {
            "id": 103,
            "name": "Crispy Veg Value",
            "shortDescription": "Crispy patty on a toasted sesame bun",
            "longDescription": "Value burger for everyday cravings",
            "price": 79.0,
            "image": "/images/crispy.png",
            "meal_image": "/images/crispy_meal.png",
            "type": "veg",
            "foodType": "veg",
            "is_meal_available": False,
            "stock": 30,
            "expiry": (date.today() + timedelta(days=20)).isoformat(),
            "category": "burger",
            "section": "Whopper",
            "section_order": 1,
            "display_order": 3,
            "meal_role": "burger",
            "is_meal_only": False,
        },
        {
            "id": 104,
            "name": "Special Treat Burger",
            "shortDescription": "Gourmet indulgence burger",
            "longDescription": "Loaded with double cheese and sauce",
            "price": 149.0,
            "image": "/images/treat.png",
            "meal_image": "/images/treat_meal.png",
            "type": "veg",
            "foodType": "veg",
            "is_meal_available": True,
            "stock": 10,
            "expiry": (date.today() + timedelta(days=5)).isoformat(),
            "category": "burger",
            "section": "Whopper",
            "section_order": 1,
            "display_order": 4,
            "meal_role": "burger",
            "is_meal_only": False,
        },
    ]

    raw_sections = [
        {
            "id": "whopper",
            "title": "Whopper",
            "products": serialized_products
        }
    ]

    result = organize_menu_sections("burger", raw_sections, preference="veg", cart=[])
    assert len(result) == 1
    section = result[0]
    assert section["id"] == "whopper"
    assert section["title"] == "Whopper"
    assert len(section["products"]) == 4

    # Ensure all original repository serializer fields are preserved on output
    first_prod = section["products"][0]
    for key in ["id", "name", "shortDescription", "longDescription", "price", "image", "meal_image",
                "type", "foodType", "is_meal_available", "stock", "expiry", "category",
                "section", "section_order", "display_order", "meal_role", "is_meal_only"]:
        assert key in first_prod, f"Field '{key}' from repository serializer must be preserved"

    print("PASS: test_actual_repository_serializer_compatibility")


# =========================================================
# 6. RESILIENCE, GATING, & EDGE CASES
# =========================================================

def test_empty_catalog_and_empty_sections():
    assert organize_menu_sections("burger", [], preference=None, cart=[]) == []
    raw = [{"id": "s1", "title": "Empty", "products": []}]
    assert organize_menu_sections("burger", raw, preference=None, cart=[]) == []
    print("PASS: test_empty_catalog_and_empty_sections")


def test_dip_section_gating_with_and_without_fries():
    sections = [
        {
            "id": "sec-fries",
            "title": "Fries & Sides",
            "products": [{"id": "f1", "name": "Peri Peri Fries", "price": 110.0, "foodType": "veg", "stock": 10}]
        },
        {
            "id": "sec-dips",
            "title": "Dips",
            "products": [{"id": "d1", "name": "Fiery Hell Dip", "price": 29.0, "foodType": "veg", "stock": 10}]
        }
    ]

    # Without fries in cart -> Dips should be demoted below Fries
    result_no_fries = organize_menu_sections("side", sections, preference="veg", cart=[])
    titles_no_fries = [s["title"] for s in result_no_fries]
    assert titles_no_fries == ["Fries & Sides", "Dips"], "Without fries, dips should be ranked below fries"

    # With fries in cart -> Dips score jumps by +5.0 and ranks #1
    cart_with_fries = [{"name": "Peri Peri Fries", "price": 110.0, "category": "side"}]
    result_with_fries = organize_menu_sections("side", sections, preference="veg", cart=cart_with_fries)
    titles_with_fries = [s["title"] for s in result_with_fries]
    assert titles_with_fries == ["Dips", "Fries & Sides"], "With fries in cart, dips section should rank first"
    print("PASS: test_dip_section_gating_with_and_without_fries")


if __name__ == "__main__":
    # Section 6: Price parsing
    test_parse_price_robustness()
    test_malformed_price_does_not_crash_menu_organization()
    test_malformed_price_not_rewarded_by_affordability_or_value_anchor()

    # Section 2: Dietary filtering
    test_dietary_filtering_veg_lock()
    test_dietary_filtering_non_veg_lock()
    test_dietary_unrestricted_browsing()
    test_dietary_drinks_hot_cold_not_confused_with_food_type()

    # Section 3: Cart item identification
    test_cart_item_identification_separate_dict_objects()
    test_cart_item_id_normalization_int_vs_string()
    test_cart_item_duplicate_names_different_ids_not_merged()
    test_cart_item_products_without_ids()
    test_cart_item_missing_id_one_side_present_other()
    test_cart_item_meal_component_and_suffix_supported_by_m07()
    test_duplicate_catalog_entries_deduplicated()

    # Section 4: Budget-aware strategic top 4
    test_budget_mindsets_strategic_top4()
    test_budget_mindset_detection()

    # Section 5: Stock and expiry eligibility
    test_stock_and_expiry_eligibility()
    test_stock_missing_and_none_excluded()
    test_legitimate_zero_price_meal_component_filtering()

    # Section 7: Edge cases, serializer compatibility & gating
    test_empty_catalog_and_empty_sections()
    test_dip_section_gating_with_and_without_fries()
    test_actual_repository_serializer_compatibility()

    print("\nALL MENU ORGANIZER UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
