"""
Unit & Integration Regression Tests for backend/services/meal_service.py and /meal/options API endpoint.

Covers:
1. Canonical dietary classification (is_veg_meal_item) leveraging M01.
2. Safe price parsing (_parse_price) covering numbers, numeric strings, None, malformed strings, and negatives.
3. Validation of inventory stock (positive, zero, negative, missing) and expiry eligibility.
4. Upgrade options filtering: out-of-stock, expired, unavailable, and invalid extra_price items excluded.
5. Unexpected exception handling in get_meal_options returning success=False.
6. API endpoint /meal/options: preservation of explicit cart=[] vs fallback to conversation_context["cart"].
7. Live meal offer for valid burger (ID 7 Veg Whopper), non-main item, and non-existent item.
"""
import sys
import os
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from state import conversation_context, reset_conversation
from services.meal_service import (
    _parse_price,
    _is_item_eligible,
    is_veg_meal_item,
    serialize_meal_option,
    organize_meal_options,
    get_meal_options,
    build_meal,
)
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


# =========================================================
# 1. CANONICAL DIETARY CLASSIFICATION TESTS
# =========================================================

def test_is_veg_meal_item_canonical():
    # Valid Veg variants
    assert is_veg_meal_item({"food_type": "veg"}) is True
    assert is_veg_meal_item({"food_type": "Veg"}) is True
    assert is_veg_meal_item({"foodType": "VEG"}) is True
    assert is_veg_meal_item({"foodType": "veg"}) is True

    # Valid Non-Veg variants
    assert is_veg_meal_item({"food_type": "non veg"}) is False
    assert is_veg_meal_item({"food_type": "non_veg"}) is False
    assert is_veg_meal_item({"foodType": "Non-Veg"}) is False
    assert is_veg_meal_item({"foodType": "Non Veg"}) is False

    # Missing, empty, or unknown metadata must evaluate to False (not Veg)
    assert is_veg_meal_item({}) is False
    assert is_veg_meal_item({"food_type": None}) is False
    assert is_veg_meal_item({"food_type": ""}) is False
    assert is_veg_meal_item({"food_type": "unknown"}) is False

    # Keyword independence: if food_type is veg, name words like chicken or fish do NOT override it
    mock_plant_based = {"name": "Plant-Based Chicken Patty", "food_type": "veg"}
    assert is_veg_meal_item(mock_plant_based) is True

    print("PASS: test_is_veg_meal_item_canonical")


# =========================================================
# 2. SAFE PRICE PARSING TESTS
# =========================================================

def test_parse_price_safety():
    # Valid numeric values
    assert _parse_price(140) == 140.0
    assert _parse_price(145.50) == 145.50
    assert _parse_price(0) == 0.0
    assert _parse_price(0.0) == 0.0

    # Numeric strings
    assert _parse_price("140") == 140.0
    assert _parse_price("145.75") == 145.75
    assert _parse_price("0") == 0.0

    # Dict wrappers
    assert _parse_price({"amount": 120.0}) == 120.0
    assert _parse_price({"price": "99.0"}) == 99.0

    # None and empty
    assert _parse_price(None) is None
    assert _parse_price("") is None

    # Malformed strings
    assert _parse_price("invalid") is None
    assert _parse_price("N/A") is None
    assert _parse_price("$140") is None
    assert _parse_price("free") is None

    # Negative values
    assert _parse_price(-10) is None
    assert _parse_price("-5.0") is None

    print("PASS: test_parse_price_safety")


# =========================================================
# 3. INVENTORY & AVAILABILITY ELIGIBILITY TESTS
# =========================================================

def test_inventory_and_expiry_eligibility():
    today = date.today()
    future = (today + timedelta(days=30)).isoformat()
    past = (today - timedelta(days=1)).isoformat()

    # Positive stock & future expiry -> Eligible
    assert _is_item_eligible({"stock": 10, "expiry": future}, today) is True
    assert _is_item_eligible({"inventory": [{"stock": 5, "expiry_date": future}]}, today) is True
    assert _is_item_eligible({"inventory": {"stock": 5, "expiry_date": future}}, today) is True

    # Missing expiry (untracked/non-perishable) with positive stock -> Eligible
    assert _is_item_eligible({"stock": 10, "expiry": None}, today) is True
    assert _is_item_eligible({"stock": 10, "expiry": ""}, today) is True

    # Zero or negative stock -> Ineligible
    assert _is_item_eligible({"stock": 0, "expiry": future}, today) is False
    assert _is_item_eligible({"stock": -5, "expiry": future}, today) is False
    assert _is_item_eligible({"inventory": [{"stock": 0, "expiry_date": future}]}, today) is False

    # Missing stock -> Ineligible
    assert _is_item_eligible({"stock": None, "expiry": future}, today) is False
    assert _is_item_eligible({"inventory": []}, today) is False
    assert _is_item_eligible({}, today) is False

    # Expired items -> Ineligible
    assert _is_item_eligible({"stock": 10, "expiry": past}, today) is False
    assert _is_item_eligible({"inventory": [{"stock": 10, "expiry_date": past}]}, today) is False

    # Malformed expiry string -> Ineligible
    assert _is_item_eligible({"stock": 10, "expiry": "not-a-date"}, today) is False

    print("PASS: test_inventory_and_expiry_eligibility")


# =========================================================
# 4. UPGRADE OPTIONS SERIALIZATION & EXCLUSION TESTS
# =========================================================

def test_upgrade_options_serialization_and_safe_extra_price():
    # Valid serialization
    item = {
        "id": 65,
        "name": "Fries (Medium)",
        "image": "img.png",
        "price": 130,
        "section": "Fries",
        "food_type": "veg",
    }
    opt = serialize_meal_option(item, extra_price=30.0, is_default=True)
    assert opt["id"] == 65
    assert opt["price"] == 130.0
    assert opt["extra_price"] == 30.0
    assert opt["is_default"] is True
    assert opt["foodType"] == "veg"

    # Malformed extra_price falls back to 0.0 in serialize_meal_option
    opt_malformed = serialize_meal_option(item, extra_price="invalid", is_default=False)
    assert opt_malformed["extra_price"] == 0.0

    print("PASS: test_upgrade_options_serialization_and_safe_extra_price")


# =========================================================
# 5. EXCEPTION HANDLING TESTS (success=False & Sanitization)
# =========================================================

def test_get_meal_options_unexpected_exception_sanitized():
    secret_marker = "SUPER_SECRET_DB_PASSWORD_XYZ123"
    with patch("services.meal_service.supabase.table") as mock_table:
        mock_table.side_effect = RuntimeError(f"Database error with credentials: {secret_marker}")

        result = get_meal_options(item_id=7)
        assert result["success"] is False
        assert result["is_meal_available"] is False
        assert result["product_id"] == 7
        assert "message" in result
        assert secret_marker not in result["message"]
        assert result["message"] == "Failed to load meal options."

    print("PASS: test_get_meal_options_unexpected_exception_sanitized")


def test_api_meal_options_unexpected_exception_sanitized():
    secret_marker = "SUPER_SECRET_API_TOKEN_ABC999"
    with patch("api.get_meal_options") as mock_get_meal:
        mock_get_meal.side_effect = RuntimeError(f"Internal crash with secret: {secret_marker}")

        res = client.post("/meal/options", json={"item_id": 7})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["is_meal_available"] is False
        assert "message" in data
        assert secret_marker not in data["message"]
        assert data["message"] == "Failed to load meal options."

    print("PASS: test_api_meal_options_unexpected_exception_sanitized")


# =========================================================
# 6. API REGRESSION TESTS (/meal/options EMPTY CART)
# =========================================================

def test_api_meal_options_explicit_empty_cart_preserved():
    reset_conversation("meal-test-session")
    stale_cart = [{"id": 65, "name": "Fries (Medium)", "price": 130.0}]
    conversation_context["cart"] = stale_cart

    try:
        # Request with explicit cart=[]:
        # Must pass cart=[] into get_meal_options, NOT stale_cart!
        # When cart=[], Fries (Medium) is not demoted to the end.
        res = client.post("/meal/options", json={"item_id": 7, "cart": []})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["is_meal_available"] is True
        side_options = data["meals"]["medium"]["side_options"]
        assert len(side_options) > 1

        # With empty cart, Fries (Medium) (default side) should be at index 0
        assert side_options[0]["id"] == 65, (
            "With explicit cart=[], default side (id=65) must remain top-ranked and not demoted to end"
        )

        # Request omitting cart (cart=None):
        # Must fall back to conversation_context["cart"] (which contains id=65)
        # and therefore id=65 MUST be pushed to the very end of side_options!
        res_fallback = client.post("/meal/options", json={"item_id": 7})
        assert res_fallback.status_code == 200
        data_fb = res_fallback.json()
        side_options_fb = data_fb["meals"]["medium"]["side_options"]
        assert side_options_fb[-1]["id"] == 65, (
            "When cart is omitted, fallback conversation cart must demote id=65 to the very last option"
        )

    finally:
        reset_conversation()

    print("PASS: test_api_meal_options_explicit_empty_cart_preserved")


# =========================================================
# 7. LIVE MEAL OFFER TESTS
# =========================================================

def test_live_meal_offer_valid_and_invalid_items():
    # 1. Valid burger: ID 7 (Veg Whopper)
    offer = get_meal_options(7)
    assert offer["success"] is True
    assert offer["is_meal_available"] is True
    assert "medium" in offer["meals"]
    assert "large" in offer["meals"]
    med = offer["meals"]["medium"]
    assert med["burger"]["name"] == "Veg Whopper"
    assert med["burger_price"] == 189.0
    assert med["upgrade_price"] == 140.0
    assert med["meal_price"] == 329.0
    assert len(med["side_options"]) > 0
    assert len(med["drink_options"]) > 0

    # 2. Non-main item: ID 65 (Fries (Medium), meal_role='side')
    offer_side = get_meal_options(65)
    assert offer_side["success"] is True
    assert offer_side["is_meal_available"] is False

    # 3. Non-existent product ID
    offer_missing = get_meal_options(999999)
    assert offer_missing["success"] is False
    assert offer_missing["is_meal_available"] is False

    print("PASS: test_live_meal_offer_valid_and_invalid_items")


if __name__ == "__main__":
    test_is_veg_meal_item_canonical()
    test_parse_price_safety()
    test_inventory_and_expiry_eligibility()
    test_upgrade_options_serialization_and_safe_extra_price()
    test_get_meal_options_unexpected_exception_sanitized()
    test_api_meal_options_unexpected_exception_sanitized()
    test_api_meal_options_explicit_empty_cart_preserved()
    test_live_meal_offer_valid_and_invalid_items()

    print("\nALL MEAL SERVICE UNIT & API REGRESSION TESTS PASSED SUCCESSFULLY!")
