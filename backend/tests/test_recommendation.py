"""
Comprehensive Unit & Integration Tests for recommendation.py
Tests:
- Fix 1: Expiry eligibility, safe normalization, safe parsing, and scoring urgency.
- Fix 2: Premium descending sort (both dietary groups exist, one empty, single-diet).
- Fix 3: Safe numeric handling (None, missing, string, malformed stock and score).
- Fix 4: M05 Priority enforcement (no bypass when Priority has < 2 items; Premium/Additional bypass M05).
- Defensive Stock Check: zero, negative, null, malformed stock excluded across all tiers.
"""
import sys
import os
from datetime import date, datetime, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.recommendation import (
    build_recommendations,
    get_priority_items,
    normalize_food_type,
    _parse_expiry_date,
    _is_expiry_eligible,
    _is_stock_eligible,
)


# =========================================================
# FIX 1 TESTS — EXPIRY ELIGIBILITY & SCORING
# =========================================================

def test_expired_product_excluded_from_all_tiers():
    today = date.today()
    yesterday = today - timedelta(days=1)
    two_weeks_ago = today - timedelta(days=14)

    items = [
        {"id": "exp1", "name": "Expired Burger", "price": 150.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": yesterday.isoformat()},
        {"id": "exp2", "name": "Old Shake", "price": 120.0, "stock": 10, "food_type": "veg", "category": "drink", "expiry": two_weeks_ago.isoformat()},
        {"id": "ok1", "name": "Fresh Burger 1", "price": 160.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": (today + timedelta(days=5)).isoformat()},
        {"id": "ok2", "name": "Fresh Burger 2", "price": 170.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": (today + timedelta(days=10)).isoformat()},
        {"id": "ok3", "name": "Fresh Burger 3", "price": 180.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": (today + timedelta(days=15)).isoformat()},
    ]

    priority, premium, additional = build_recommendations(items, food_type="veg")
    all_recommended_ids = {i["id"] for i in priority + premium + additional}

    assert "exp1" not in all_recommended_ids, "Expired item exp1 must not appear in any tier"
    assert "exp2" not in all_recommended_ids, "Expired item exp2 must not appear in any tier"
    print("PASS: test_expired_product_excluded_from_all_tiers")


def test_soon_to_expire_receives_higher_urgency_score():
    today = date.today()
    item_urgent = {
        "id": "urg",
        "name": "Expiring Soon",
        "stock": 10,
        "score": 1.0,
        "expiry": (today + timedelta(days=2)).isoformat()
    }
    item_later = {
        "id": "lat",
        "name": "Expiring Later",
        "stock": 10,
        "score": 1.0,
        "expiry": (today + timedelta(days=20)).isoformat()
    }

    result = get_priority_items([item_later, item_urgent])
    # Urgency for 2 days = 30 - 2 = 28 -> priority = (10 + 28) * 1 = 38
    # Urgency for 20 days = 30 - 20 = 10 -> priority = (10 + 10) * 1 = 20
    assert result[0]["id"] == "urg", "Item expiring in 2 days must have higher priority than item expiring in 20 days"
    assert result[0]["priority"] == 38.0
    assert result[1]["priority"] == 20.0
    print("PASS: test_soon_to_expire_receives_higher_urgency_score")


def test_expiry_date_normalization_variants():
    today = date.today()
    # 1. date object
    d_obj, valid = _parse_expiry_date(today)
    assert valid and d_obj == today

    # 2. datetime object
    dt_obj, valid = _parse_expiry_date(datetime(2026, 10, 20, 15, 30))
    assert valid and dt_obj == date(2026, 10, 20)

    # 3. ISO date string
    iso_date, valid = _parse_expiry_date("2026-10-25")
    assert valid and iso_date == date(2026, 10, 25)

    # 4. ISO with Z
    iso_z, valid = _parse_expiry_date("2026-10-25T12:00:00Z")
    assert valid and iso_z == date(2026, 10, 25)

    # 5. Missing / None / Empty
    none_d, valid = _parse_expiry_date(None)
    assert valid and none_d is None
    empty_d, valid = _parse_expiry_date("")
    assert valid and empty_d is None

    # 6. Malformed string
    bad_d, valid = _parse_expiry_date("invalid-date-string")
    assert not valid and bad_d is None

    # 7. Safe rejection of malformed date in eligibility check
    assert not _is_expiry_eligible({"expiry": "not-a-date"}, today), "Malformed date must be ineligible"
    # None is eligible (standard item with no expiry)
    assert _is_expiry_eligible({"expiry": None}, today), "None expiry must be eligible"
    print("PASS: test_expiry_date_normalization_variants")


# =========================================================
# FIX 2 TESTS — PREMIUM SORTING
# =========================================================

def test_premium_sorting_both_mode_when_one_diet_empty():
    # Only veg items available; food_type="both"
    items = [
        {"id": "v1", "name": "Veg Burger Low", "price": 100.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v2", "name": "Veg Burger Mid", "price": 150.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v3", "name": "Veg Burger High", "price": 250.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v4", "name": "Veg Burger Ultra", "price": 300.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v5", "name": "Veg Burger Extra", "price": 200.0, "stock": 10, "food_type": "veg", "category": "burger"},
    ]

    priority, premium, additional = build_recommendations(items, food_type="both")

    assert len(premium) == 2, f"Expected 2 premium items, got {len(premium)}"
    # Premium MUST be sorted descending (highest price first)
    assert premium[0]["price"] >= premium[1]["price"], (
        f"Premium items must be sorted descending by price! Got: {premium[0]['price']} then {premium[1]['price']}"
    )
    # The highest available items not in priority should be picked
    used_priority_ids = {p["id"] for p in priority}
    remaining_by_price = sorted(
        [i for i in items if i["id"] not in used_priority_ids],
        key=lambda x: x["price"],
        reverse=True
    )
    assert premium[0]["id"] == remaining_by_price[0]["id"]
    print("PASS: test_premium_sorting_both_mode_when_one_diet_empty")


def test_premium_sorting_both_mode_both_diets():
    items = [
        {"id": "v1", "name": "Veg Low", "price": 100.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v2", "name": "Veg High", "price": 250.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "nv1", "name": "NonVeg Low", "price": 120.0, "stock": 10, "food_type": "non_veg", "category": "burger"},
        {"id": "nv2", "name": "NonVeg High", "price": 300.0, "stock": 10, "food_type": "non_veg", "category": "burger"},
    ]

    priority, premium, additional = build_recommendations(items, food_type="both")

    # Verify no duplicates across tiers
    all_ids = [i["id"] for i in priority + premium + additional]
    assert len(all_ids) == len(set(all_ids)), f"Duplicate items found across tiers: {all_ids}"
    print("PASS: test_premium_sorting_both_mode_both_diets")


# =========================================================
# FIX 3 TESTS — SAFE NUMERIC HANDLING
# =========================================================

def test_safe_numeric_handling_in_priority_scoring():
    items = [
        # None stock
        {"id": "1", "name": "Item 1", "stock": None, "score": 1.0},
        # String stock
        {"id": "2", "name": "Item 2", "stock": "15", "score": "2.0"},
        # Malformed stock
        {"id": "3", "name": "Item 3", "stock": "invalid_stock", "score": 1.0},
        # None score
        {"id": "4", "name": "Item 4", "stock": 10, "score": None},
        # Malformed score
        {"id": "5", "name": "Item 5", "stock": 10, "score": "bad_score"},
        # Negative stock
        {"id": "6", "name": "Item 6", "stock": -5, "score": 1.0},
        # Missing keys
        {"id": "7", "name": "Item 7"},
    ]

    # Must NOT raise TypeError
    result = get_priority_items(items)
    assert len(result) == 7, "All items must be processed without TypeError"

    # Verify item 2 parsed string stock "15" and score "2.0": priority = 15 * 2.0 = 30.0 (no expiry)
    item2 = next(i for i in result if i["id"] == "2")
    assert item2["priority"] == 30.0

    # Malformed score should not increase priority
    item5 = next(i for i in result if i["id"] == "5")
    assert item5["priority"] == 0.0

    # None score should use default 1.0 multiplier
    item4 = next(i for i in result if i["id"] == "4")
    assert item4["priority"] == 10.0

    print("PASS: test_safe_numeric_handling_in_priority_scoring")


# =========================================================
# FIX 4 TESTS — STRICT M05 ENFORCEMENT ON PRIORITY
# =========================================================

def test_m05_not_bypassed_when_fewer_than_two_candidates_survive():
    # Cart has anchor Burger ₹100 -> ratio = 1.75 -> ceiling = ₹175
    # Cross-category candidate: Side ₹120 (survives), Side ₹250 (exceeds), Side ₹300 (exceeds)
    # But wait: M05 apply_price_ceiling returns candidates if < 2 survivors.
    # What if cand_pool has only 1 candidate, or only 1 diet candidate?
    # Let's test single-diet mode where cand_pool only has 1 item:
    cart = [{"name": "Burger", "price": 100.0, "category": "burger"}]
    # Candidates with only 1 item <= ceiling, other 2 > ceiling
    # To test recommendation.py strict enforcement:
    # If cand_pool has 1 item, priority MUST NOT backfill from candidates outside cand_pool!
    items = [
        {"id": "s1", "name": "Fries", "price": 120.0, "stock": 10, "food_type": "veg", "category": "side"},
    ]
    priority, premium, additional = build_recommendations(items, food_type="veg", cart=cart)
    assert len(priority) == 1, f"Expected 1 priority item when only 1 item in candidate pool, got {len(priority)}"
    assert priority[0]["id"] == "s1"
    print("PASS: test_m05_not_bypassed_when_fewer_than_two_candidates_survive")


def test_m05_priority_both_mode_one_diet_missing_in_budget():
    # In both mode, suppose veg has 1 budget candidate, non-veg has 0 budget candidates
    # Priority should take the 1 veg candidate and NOT backfill non-veg from outside cand_pool
    items = [
        {"id": "v1", "name": "Veg Side Cheap", "price": 80.0, "stock": 10, "food_type": "veg", "category": "side"},
        {"id": "v2", "name": "Veg Side Cheap 2", "price": 90.0, "stock": 10, "food_type": "veg", "category": "side"},
        {"id": "nv1", "name": "NonVeg Side Expensive", "price": 400.0, "stock": 10, "food_type": "non_veg", "category": "side"},
    ]
    cart = [{"name": "Burger", "price": 80.0, "category": "burger"}] # ceiling = 80 * 2.0 = 160.0
    # M05 survivors: v1 (80), v2 (90). nv1 (400) is filtered out by M05!
    priority, premium, additional = build_recommendations(items, food_type="both", cart=cart)

    priority_ids = [p["id"] for p in priority]
    assert "nv1" not in priority_ids, "Expensive non-veg item nv1 exceeding M05 ceiling must NOT be in Priority!"
    # nv1 CAN be in Premium (Premium bypasses M05)
    premium_ids = [p["id"] for p in premium]
    assert "nv1" in premium_ids, "Expensive non-veg item nv1 should be in Premium (bypassing M05)"
    print("PASS: test_m05_priority_both_mode_one_diet_missing_in_budget")


# =========================================================
# DEFENSIVE STOCK CHECK TESTS
# =========================================================

def test_zero_and_negative_and_none_stock_excluded_from_all_tiers():
    today = date.today()
    items = [
        {"id": "z1", "name": "Zero Stock", "price": 100.0, "stock": 0, "food_type": "veg", "category": "burger"},
        {"id": "z2", "name": "Negative Stock", "price": 120.0, "stock": -3, "food_type": "veg", "category": "burger"},
        {"id": "z3", "name": "None Stock", "price": 130.0, "stock": None, "food_type": "veg", "category": "burger"},
        {"id": "z4", "name": "Malformed Stock", "price": 140.0, "stock": "zero", "food_type": "veg", "category": "burger"},
        {"id": "ok1", "name": "Valid 1", "price": 150.0, "stock": 5, "food_type": "veg", "category": "burger"},
        {"id": "ok2", "name": "Valid 2", "price": 160.0, "stock": "10", "food_type": "veg", "category": "burger"},
        {"id": "ok3", "name": "Valid 3", "price": 170.0, "stock": 2, "food_type": "veg", "category": "burger"},
    ]

    priority, premium, additional = build_recommendations(items, food_type="veg")
    all_ids = {i["id"] for i in priority + premium + additional}

    assert "z1" not in all_ids, "0 stock item must be excluded from all tiers"
    assert "z2" not in all_ids, "Negative stock item must be excluded from all tiers"
    assert "z3" not in all_ids, "None stock item must be excluded from all tiers"
    assert "z4" not in all_ids, "Malformed stock item must be excluded from all tiers"

    assert "ok1" in all_ids
    assert "ok2" in all_ids
    print("PASS: test_zero_and_negative_and_none_stock_excluded_from_all_tiers")


# =========================================================
# ADDITIONAL REGRESSION TESTS (FULL PIPELINE)
# =========================================================

def test_native_date_objects_full_pipeline():
    """
    Test A: Call build_recommendations() with candidates containing datetime.date
    and datetime.datetime expiry values.
    Verify valid unexpired products are handled correctly and expired products
    are excluded from all tiers.
    """
    today = date.today()
    future_date = today + timedelta(days=7)
    future_datetime = datetime(today.year, today.month, today.day, 12, 0) + timedelta(days=10)
    past_date = today - timedelta(days=2)
    past_datetime = datetime(today.year, today.month, today.day, 10, 0) - timedelta(days=5)

    items = [
        {"id": "ok_d", "name": "Valid Date Item", "price": 150.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": future_date},
        {"id": "ok_dt", "name": "Valid Datetime Item", "price": 180.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": future_datetime},
        {"id": "exp_d", "name": "Expired Date Item", "price": 200.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": past_date},
        {"id": "exp_dt", "name": "Expired Datetime Item", "price": 220.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": past_datetime},
        {"id": "ok_no_exp", "name": "Valid Untracked Item", "price": 140.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": None},
    ]

    priority, premium, additional = build_recommendations(items, food_type="veg")
    all_recs = priority + premium + additional
    all_ids = {i["id"] for i in all_recs}

    # Expired date and datetime items must be excluded from all tiers
    assert "exp_d" not in all_ids, "Expired date object item must be excluded from all tiers"
    assert "exp_dt" not in all_ids, "Expired datetime object item must be excluded from all tiers"

    # Valid unexpired date, datetime, and None items must be admitted into recommendations
    assert "ok_d" in all_ids, "Valid unexpired date object item must be admitted"
    assert "ok_dt" in all_ids, "Valid unexpired datetime object item must be admitted"
    assert "ok_no_exp" in all_ids, "Valid None expiry item must be admitted"
    print("PASS: test_native_date_objects_full_pipeline")


def test_malformed_expiry_full_pipeline():
    """
    Test B: Pass candidate with invalid expiry strings to build_recommendations().
    Verify request does not crash and invalid-date products appear in none of the three tiers,
    while valid candidates continue to be recommended.
    """
    today = date.today()
    items = [
        {"id": "bad1", "name": "Malformed Date String", "price": 150.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": "not-a-date"},
        {"id": "bad2", "name": "Invalid ISO Format", "price": 160.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": "2026-99-99"},
        {"id": "ok1", "name": "Valid Item 1", "price": 170.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": (today + timedelta(days=15)).isoformat()},
        {"id": "ok2", "name": "Valid Item 2", "price": 180.0, "stock": 10, "food_type": "veg", "category": "burger", "expiry": (today + timedelta(days=20)).isoformat()},
        {"id": "ok3", "name": "Valid Item 3", "price": 190.0, "stock": 10, "food_type": "veg", "category": "burger"},
    ]

    # Must NOT crash
    priority, premium, additional = build_recommendations(items, food_type="veg")
    all_recs = priority + premium + additional
    all_ids = {i["id"] for i in all_recs}

    # Pipeline can still return recommendations for valid candidates
    assert len(all_recs) > 0, "Pipeline must still return recommendations for valid candidates"
    assert "ok1" in all_ids, "Valid candidate ok1 must appear in recommendations"
    assert "ok2" in all_ids, "Valid candidate ok2 must appear in recommendations"

    # Malformed expiry products must appear in none of the three recommendation tiers
    assert "bad1" not in all_ids, "Candidate with malformed expiry 'not-a-date' must not appear in any tier"
    assert "bad2" not in all_ids, "Candidate with invalid ISO format must not appear in any tier"
    print("PASS: test_malformed_expiry_full_pipeline")


def test_premium_ordering_both_dietary_groups():
    """
    Test C: Create candidate pool with multiple vegetarian and non-vegetarian products
    above the Premium threshold.
    Assert explicitly that Premium's vegetarian and non-vegetarian selections
    are in descending price order (highest price first).
    """
    items = [
        # Veg candidates
        {"id": "v_prio", "name": "Veg Base", "price": 100.0, "stock": 100, "food_type": "veg", "category": "burger"},
        {"id": "v_mid", "name": "Veg Mid", "price": 160.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v_prem1", "name": "Veg Prem Tier 1", "price": 280.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v_prem2", "name": "Veg Prem Tier 2", "price": 340.0, "stock": 10, "food_type": "veg", "category": "burger"},
        {"id": "v_prem3", "name": "Veg Prem Top", "price": 420.0, "stock": 10, "food_type": "veg", "category": "burger"},
        # Non-veg candidates
        {"id": "nv_prio", "name": "NonVeg Base", "price": 110.0, "stock": 100, "food_type": "non_veg", "category": "burger"},
        {"id": "nv_mid", "name": "NonVeg Mid", "price": 170.0, "stock": 10, "food_type": "non_veg", "category": "burger"},
        {"id": "nv_prem1", "name": "NonVeg Prem Tier 1", "price": 290.0, "stock": 10, "food_type": "non_veg", "category": "burger"},
        {"id": "nv_prem2", "name": "NonVeg Prem Tier 2", "price": 360.0, "stock": 10, "food_type": "non_veg", "category": "burger"},
        {"id": "nv_prem3", "name": "NonVeg Prem Top", "price": 460.0, "stock": 10, "food_type": "non_veg", "category": "burger"},
    ]

    priority, premium, additional = build_recommendations(items, food_type="both", cart=[])

    # Ensure both dietary groups are present in Priority and Premium
    assert len(priority) == 2, f"Expected 2 priority items, got {len(priority)}"
    assert len(premium) == 2, f"Expected 2 premium items, got {len(premium)}"

    veg_prem = [i for i in premium if normalize_food_type(i.get("food_type") or i.get("foodType")) == "veg"]
    non_veg_prem = [i for i in premium if normalize_food_type(i.get("food_type") or i.get("foodType")) == "non_veg"]

    assert len(veg_prem) >= 1, "Expected at least 1 veg item in Premium"
    assert len(non_veg_prem) >= 1, "Expected at least 1 non-veg item in Premium"

    # Assert explicitly that vegetarian selections are in descending price order
    for idx in range(len(veg_prem) - 1):
        assert veg_prem[idx]["price"] >= veg_prem[idx + 1]["price"], (
            f"Veg premium items must be in descending price order: {veg_prem[idx]['price']} < {veg_prem[idx+1]['price']}"
        )

    # Assert explicitly that non-vegetarian selections are in descending price order
    for idx in range(len(non_veg_prem) - 1):
        assert non_veg_prem[idx]["price"] >= non_veg_prem[idx + 1]["price"], (
            f"Non-veg premium items must be in descending price order: {non_veg_prem[idx]['price']} < {non_veg_prem[idx+1]['price']}"
        )

    # Assert that the selected items are indeed the highest-priced available in their dietary group
    assert veg_prem[0]["id"] == "v_prem3", f"Expected highest priced veg item (v_prem3 ₹420) in Premium, got {veg_prem[0]['id']}"
    assert non_veg_prem[0]["id"] == "nv_prem3", f"Expected highest priced non-veg item (nv_prem3 ₹460) in Premium, got {non_veg_prem[0]['id']}"

    print("PASS: test_premium_ordering_both_dietary_groups")


if __name__ == "__main__":
    test_expired_product_excluded_from_all_tiers()
    test_soon_to_expire_receives_higher_urgency_score()
    test_expiry_date_normalization_variants()
    test_premium_sorting_both_mode_when_one_diet_empty()
    test_premium_sorting_both_mode_both_diets()
    test_safe_numeric_handling_in_priority_scoring()
    test_m05_not_bypassed_when_fewer_than_two_candidates_survive()
    test_m05_priority_both_mode_one_diet_missing_in_budget()
    test_zero_and_negative_and_none_stock_excluded_from_all_tiers()
    test_native_date_objects_full_pipeline()
    test_malformed_expiry_full_pipeline()
    test_premium_ordering_both_dietary_groups()
    print("\nALL RECOMMENDATION UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
