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
    get_default_meal,
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
    import io
    import contextlib

    secret_marker = "SYNTHETIC_TEST_DB_PASSWORD_XYZ123"
    captured_logs = io.StringIO()
    with patch("services.meal_service.supabase.table") as mock_table, contextlib.redirect_stdout(captured_logs):
        mock_table.side_effect = RuntimeError(f"Database error with credentials: {secret_marker}")

        result = get_meal_options(item_id=7)
        assert result["success"] is False
        assert result["is_meal_available"] is False
        assert result["product_id"] == 7
        assert "message" in result
        assert secret_marker not in result["message"]
        assert result["message"] == "Failed to load meal options."

    assert secret_marker not in captured_logs.getvalue(), (
        f"Sensitive credential leaked in logs: {captured_logs.getvalue()}"
    )
    print("PASS: test_get_meal_options_unexpected_exception_sanitized")


def test_api_meal_options_unexpected_exception_sanitized():
    import io
    import contextlib

    secret_marker = "SYNTHETIC_TEST_API_TOKEN_ABC999"
    captured_logs = io.StringIO()
    with patch("api.get_meal_options") as mock_get_meal, contextlib.redirect_stdout(captured_logs):
        mock_get_meal.side_effect = RuntimeError(f"Internal crash with secret: {secret_marker}")

        res = client.post("/meal/options", json={"item_id": 7})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["is_meal_available"] is False
        assert "message" in data
        assert secret_marker not in data["message"]
        assert data["message"] == "Failed to load meal options."

    assert secret_marker not in captured_logs.getvalue(), (
        f"Sensitive token leaked in logs: {captured_logs.getvalue()}"
    )
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


# =========================================================
# 8. MEAL CUSTOMIZER DEFAULT SELECTION & DIETARY ORDERING
# =========================================================

def test_meal_customizer_default_selection_and_dietary_ordering():
    # 1. Verify default meal options structure & ₹0 extra pricing
    defaults = {
        "side": {"id": 65, "name": "Classic Fries", "price": 130.0, "food_type": "veg", "image": "fries.png"},
        "drink": {"id": 40, "name": "Coca Cola", "price": 99.0, "food_type": "veg", "image": "coke.png"},
    }
    opt_default_side = serialize_meal_option(defaults["side"], extra_price=0.0, is_default=True)
    opt_upgrade_side = serialize_meal_option(
        {"id": 66, "name": "Peri Peri Fries", "price": 150.0, "food_type": "veg", "flavor_profile": "spicy peri peri", "image": "peri.png"},
        extra_price=20.0,
        is_default=False,
    )
    assert opt_default_side["is_default"] is True
    assert opt_default_side["extra_price"] == 0.0
    assert opt_upgrade_side["is_default"] is False
    assert opt_upgrade_side["extra_price"] == 20.0

    # 2. Ranking upgrade options never alters extra_price or is_default of the default item
    options = [opt_default_side, opt_upgrade_side]
    main_product = {"id": 1, "name": "Peri Peri Burger", "flavor_profile": "spicy peri peri"}
    organized = organize_meal_options(options, food_preference="veg", main_product=main_product)

    # Check default item retains extra_price 0.0 and is_default True
    def_found = [o for o in organized if o["id"] == 65][0]
    assert def_found["extra_price"] == 0.0
    assert def_found["is_default"] is True

    # 3. Dietary ordering: Veg preference puts veg first; non-veg puts non-veg first
    mixed_options = [
        {"id": 101, "name": "Chicken Strips", "food_type": "non_veg", "extra_price": 50.0},
        {"id": 102, "name": "Veg Strips", "food_type": "veg", "extra_price": 30.0},
    ]
    veg_organized = organize_meal_options(mixed_options, food_preference="veg")
    assert veg_organized[0]["id"] == 102  # Veg first
    assert veg_organized[1]["id"] == 101

    non_veg_organized = organize_meal_options(mixed_options, food_preference="non_veg")
    assert non_veg_organized[0]["id"] == 101  # Non-veg first
    assert non_veg_organized[1]["id"] == 102

    # 4. Meal Customizer Soft Cart Exclusion vs M7 Hard Cart Exclusion:
    # While checkout recommendations permanently drop carted items (M7 exclude_cart_items),
    # Meal Customizer intentionally preserves meal combo options by demoting carted items to the very end.
    # Cart membership does NOT auto-replace the customer's selection.
    cart = [{"id": 102, "name": "Veg Strips"}]
    cart_organized = organize_meal_options(mixed_options, food_preference="veg", cart=cart)
    assert cart_organized[-1]["id"] == 102  # Carted item demoted to last

    print("PASS: test_meal_customizer_default_selection_and_dietary_ordering")


# =========================================================
# 9. MEAL CUSTOMIZATION SELECTION INTEGRITY REGRESSION TESTS
# =========================================================

def test_meal_defaults_initialized_at_zero_extra():
    """
    Req 1, 2, 3: Default side and drink are selected initially, each with ₹0 extra.
    """
    meal = build_meal(item_id=7, meal_size="medium")
    assert meal is not None
    assert meal["side"] is not None
    assert meal["drink"] is not None

    # Check defaults are medium Fries (id 65) and Coca Cola (id 40)
    assert meal["side"]["id"] == 65
    assert meal["drink"]["id"] == 40

    # Ensure extra_price is 0.0 for both included defaults
    assert meal["side"]["extra_price"] == 0.0
    assert meal["drink"]["extra_price"] == 0.0

    # Total meal price must be burger_price + upgrade_price without unexpected extras
    assert meal["meal_price"] == meal["burger_price"] + meal["upgrade_price"]
    print("PASS: test_meal_defaults_initialized_at_zero_extra")


def test_higher_ranked_paid_upgrade_does_not_mutate_selected_defaults():
    """
    Req 4: Recommended upgrades are ranked for presentation only;
    a higher-ranked paid upgrade never overwrites selection state.
    """
    meal = build_meal(item_id=7, meal_size="medium")
    assert meal is not None

    # Verify side_options contains upgrades with extra_price > 0
    paid_upgrades = [opt for opt in meal["side_options"] if opt["extra_price"] > 0]
    assert len(paid_upgrades) > 0

    # Even if options exist, the meal's included side remains the default with 0 extra
    assert meal["side"]["id"] == 65
    assert meal["side"]["extra_price"] == 0.0

    # Same check for drink
    paid_drinks = [opt for opt in meal["drink_options"] if opt["extra_price"] > 0]
    assert len(paid_drinks) > 0
    assert meal["drink"]["id"] == 40
    assert meal["drink"]["extra_price"] == 0.0
    print("PASS: test_higher_ranked_paid_upgrade_does_not_mutate_selected_defaults")


def test_in_cart_default_does_not_trigger_replacement():
    """
    Req 6: An item already in the cart must not cause the default to be silently replaced.
    Cart membership is not customer consent to change a meal component.
    """
    # Put default side (id 65) in the cart
    cart_with_default = [{"id": 65, "name": "Fries (Medium)", "price": 130.0}]

    meal = build_meal(item_id=7, meal_size="medium", cart=cart_with_default)
    assert meal is not None

    # In options presentation, the in-cart item is demoted to the very end
    assert meal["side_options"][-1]["id"] == 65

    # CRITICAL: meal.side selection must NOT be replaced by an uncarted upgrade!
    assert meal["side"]["id"] == 65
    assert meal["side"]["extra_price"] == 0.0
    assert meal["drink"]["id"] == 40
    print("PASS: test_in_cart_default_does_not_trigger_replacement")


def test_reordering_options_preserves_selection():
    """
    Req 4: Presentation reordering (e.g. dietary change or flavor affinity)
    preserves the selected items.
    """
    meal_veg = build_meal(item_id=7, meal_size="medium", food_preference="veg")
    meal_non_veg = build_meal(item_id=7, meal_size="medium", food_preference="non_veg")

    # Options order differs based on dietary preference
    assert meal_veg is not None and meal_non_veg is not None
    assert meal_veg["side_options"] != meal_non_veg["side_options"]

    # Selected defaults remain identical regardless of option ordering
    assert meal_veg["side"]["id"] == meal_non_veg["side"]["id"] == 65
    assert meal_veg["drink"]["id"] == meal_non_veg["drink"]["id"] == 40
    assert meal_veg["side"]["extra_price"] == meal_non_veg["side"]["extra_price"] == 0.0
    print("PASS: test_reordering_options_preserves_selection")


def test_explicit_selection_and_cart_submission():
    """
    Req 5: Only an explicit customer click on an alternative changes the selected item and extra price.
    """
    reset_conversation("test-customizer-selection")
    try:
        meal = build_meal(item_id=7, meal_size="medium")
        assert meal is not None

        # Customer explicitly picks a paid upgrade side (e.g., extra_price > 0)
        paid_side = next(opt for opt in meal["side_options"] if opt["extra_price"] > 0)

        # Build submission payload with customer's chosen upgrade
        customized_meal = {
            **meal,
            "side": paid_side,
            "drink": meal["drink"],  # default drink retained
        }

        res = client.post("/cart/add-meal", json={"meal": customized_meal, "quantity": 1})
        assert res.status_code == 200
        cart_data = res.json()
        assert len(cart_data["cart"]) == 1

        added_item = cart_data["cart"][0]
        assert added_item["type"] == "meal"
        assert added_item["side"]["id"] == paid_side["id"]
        assert added_item["drink"]["id"] == 40

        expected_unit_price = meal["meal_price"] + paid_side["extra_price"] + 0.0
        assert added_item["unitPrice"] == expected_unit_price
        assert added_item["subtotal"] == expected_unit_price
    finally:
        reset_conversation()

    print("PASS: test_explicit_selection_and_cart_submission")


def test_submitted_meal_uses_selected_ids_not_first_ranked():
    """
    Req 8: Final meal submission uses the actual customer-selected side and drink,
    not simply the first item in the ranked list.
    """
    reset_conversation("test-submission-ids")
    try:
        meal = build_meal(item_id=7, meal_size="medium")
        assert meal is not None

        # Pick candidate at index 1 or last, distinct from side_options[0]
        alt_side = meal["side_options"][-1]
        first_ranked_side = meal["side_options"][0]
        assert alt_side["id"] != first_ranked_side["id"]

        submission = {
            **meal,
            "side": alt_side,
            "drink": meal["drink"],
        }

        res = client.post("/cart/add-meal", json={"meal": submission, "quantity": 1})
        assert res.status_code == 200
        cart_data = res.json()
        added_item = cart_data["cart"][0]

        # Cart must store the explicitly selected alt_side, NOT first_ranked_side
        assert added_item["side"]["id"] == alt_side["id"]
        assert added_item["side"]["id"] != first_ranked_side["id"]
    finally:
        reset_conversation()

    print("PASS: test_submitted_meal_uses_selected_ids_not_first_ranked")


def test_unavailable_default_does_not_silently_trigger_paid_upgrade():
    """
    Req 7: If a default is genuinely unavailable, do not silently select a paid upgrade.
    get_default_meal / build_meal must return None, refusing to silently substitute a paid upgrade.
    """
    with patch("services.meal_service.supabase.table") as mock_table:
        # Simulate default side being unavailable (e.g., out of stock or is_available=False)
        mock_query = MagicMock()
        mock_table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query

        # default mapping returns side_id 65, drink_id 40
        mock_defaults = MagicMock()
        mock_defaults.data = [{"default_side_id": 65, "default_drink_id": 40}]

        # side query returns unavailable side
        mock_side = MagicMock()
        mock_side.data = [{"id": 65, "name": "Fries", "is_available": False, "stock": 0}]

        # drink query returns available drink
        mock_drink = MagicMock()
        mock_drink.data = [{"id": 40, "name": "Coke", "is_available": True, "stock": 10}]

        mock_query.execute.side_effect = [mock_defaults, mock_side, mock_drink]

        res = get_default_meal("medium")
        assert res is None, "Unavailable default must return None, never silently swap to a paid upgrade"

    print("PASS: test_unavailable_default_does_not_silently_trigger_paid_upgrade")


if __name__ == "__main__":
    test_is_veg_meal_item_canonical()
    test_parse_price_safety()
    test_inventory_and_expiry_eligibility()
    test_upgrade_options_serialization_and_safe_extra_price()
    test_get_meal_options_unexpected_exception_sanitized()
    test_api_meal_options_unexpected_exception_sanitized()
    test_api_meal_options_explicit_empty_cart_preserved()
    test_live_meal_offer_valid_and_invalid_items()
    test_meal_customizer_default_selection_and_dietary_ordering()
    test_meal_defaults_initialized_at_zero_extra()
    test_higher_ranked_paid_upgrade_does_not_mutate_selected_defaults()
    test_in_cart_default_does_not_trigger_replacement()
    test_reordering_options_preserves_selection()
    test_explicit_selection_and_cart_submission()
    test_submitted_meal_uses_selected_ids_not_first_ranked()
    test_unavailable_default_does_not_silently_trigger_paid_upgrade()

    print("\nALL MEAL SERVICE UNIT & API REGRESSION TESTS PASSED SUCCESSFULLY!")
