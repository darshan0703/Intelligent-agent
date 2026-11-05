"""
Tests for Kiosk Order Checkout Integration with TheAtom Control Centre.
Verifies touch and voice checkout, payload normalization, error handling,
timeout behavior, and authentication.
"""

from unittest.mock import patch, MagicMock
import pytest
import httpx

from repositories.order_repository import complete_order, normalize_cart_for_persistence
from state import conversation_context, reset_conversation


@pytest.fixture(autouse=True)
def clean_state():
    reset_conversation("test_session_123")
    yield


def test_normalize_cart_standalone_and_combo():
    """Verify that cart items are normalized accurately without client prices."""
    cart = [
        {
            "type": "item",
            "id": 13,
            "name": "BK Veggie",
            "quantity": 2,
            "unitPrice": 139.0,
            "subtotal": 278.0,
        },
        {
            "type": "meal",
            "name": "Chicken Whopper Meal",
            "quantity": 1,
            "meal_size": "King",
            "main_item": {"id": 8, "name": "Chicken Whopper"},
            "side": {"id": 66, "name": "Large Fries"},
            "drink": {"id": 40, "name": "Pepsi"},
        },
    ]

    normalized = normalize_cart_for_persistence(cart)
    assert len(normalized) == 2

    # Standalone
    assert normalized[0]["combo"] is False
    assert normalized[0]["item_id"] == 13
    assert normalized[0]["quantity"] == 2
    assert "unitPrice" not in normalized[0]

    # Combo
    assert normalized[1]["combo"] is True
    assert normalized[1]["burger_id"] == 8
    assert normalized[1]["meal_size"] == "large"  # King mapped to large
    assert normalized[1]["side_id"] == 66
    assert normalized[1]["drink_id"] == 40
    assert normalized[1]["quantity"] == 1


def test_complete_order_success_calls_control_centre():
    """Verify complete_order sends authenticated POST to Control Centre and returns confirmed order."""
    cart = [{"type": "item", "id": 13, "quantity": 1}]

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "success": True,
        "order_id": 888,
        "session_id": "sess_888",
        "branch_id": 1,
        "status": "pending_payment",
        "total_amount": 139.00,
        "payment_method": "cash",
        "created_at": "2026-10-27T17:00:00Z",
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = complete_order(cart, session_id="sess_888", payment_method="cash", idempotency_key="key_888")

        assert res["success"] is True
        assert res["order_id"] == 888
        assert res["status"] == "pending_payment"

        # Verify call arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/api/v1/orders/checkout" in args[0]
        assert "X-Kiosk-Key" in kwargs["headers"]
        assert kwargs["json"]["session_id"] == "sess_888"
        assert kwargs["json"]["idempotency_key"] == "key_888"
        assert kwargs["json"]["items"] == [{"combo": False, "item_id": 13, "quantity": 1}]


def test_complete_order_timeout_preserves_cart():
    """Verify network timeout returns controlled error and does not claim success."""
    cart = [{"type": "item", "id": 13, "quantity": 1}]

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Connection timed out")):
        res = complete_order(cart, session_id="sess_to", payment_method="cash", idempotency_key="key_to")
        assert res["success"] is False
        assert res["code"] == "NETWORK_TIMEOUT"
        assert "timed out" in res["message"]


def test_complete_order_auth_failure():
    """Verify that a 401 Unauthorized from Control Centre returns controlled error."""
    cart = [{"type": "item", "id": 13, "quantity": 1}]

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"detail": "Unauthorized: Valid kiosk integration credential required."}

    with patch("httpx.Client.post", return_value=mock_resp):
        res = complete_order(cart, session_id="sess_bad_auth")
        assert res["success"] is False
        assert res["status_code"] == 401
        assert "Unauthorized" in res["message"]


def test_complete_order_empty_cart_fails_fast():
    """Verify empty cart is rejected immediately without network request."""
    res = complete_order([])
    assert res["success"] is False
    assert "Cart is empty" in res["message"]


def test_touch_endpoint_order_complete_success():
    """Verify touch endpoint completes order, transitions screen to ORDER_COMPLETE, and generates fresh session ID."""
    from api import complete_order_endpoint
    from screen_controls import ScreenTypes

    conversation_context["cart"] = [{"type": "item", "id": 13, "quantity": 1}]
    conversation_context["session_id"] = "touch_session_1"
    conversation_context["current_screen"] = ScreenTypes.CART

    mock_resp = {
        "success": True,
        "order_id": 999,
        "status": "pending_payment",
        "total_amount": 139.00,
        "payment_method": "cash",
        "session_id": "touch_session_1",
    }

    with patch("api.complete_order", return_value=mock_resp):
        res = complete_order_endpoint()
        assert res["success"] is True
        assert res["order_id"] == 999

        # Screen transitioned
        assert conversation_context["current_screen"] == ScreenTypes.ORDER_COMPLETE
        # Cart cleared
        assert conversation_context["cart"] == []
        # New session ID generated for next customer
        assert conversation_context["session_id"] != "touch_session_1"


def test_touch_endpoint_order_complete_failure_preserves_cart():
    """Verify touch endpoint preserves cart when checkout fails."""
    from api import complete_order_endpoint
    from screen_controls import ScreenTypes

    initial_cart = [{"type": "item", "id": 13, "quantity": 1}]
    conversation_context["cart"] = list(initial_cart)
    conversation_context["session_id"] = "touch_session_2"
    conversation_context["current_screen"] = ScreenTypes.CART

    mock_resp = {
        "success": False,
        "status_code": 400,
        "code": "OUT_OF_STOCK",
        "message": "Insufficient stock for item 13",
    }
    mock_fastapi_response = MagicMock()

    with patch("api.complete_order", return_value=mock_resp):
        res = complete_order_endpoint(response=mock_fastapi_response)
        assert res["success"] is False
        assert mock_fastapi_response.status_code == 400

        # Screen remains on CART
        assert conversation_context["current_screen"] == ScreenTypes.CART
        # Cart is NOT cleared
        assert len(conversation_context["cart"]) == 1
        # Session ID remains same for retry
        assert conversation_context["session_id"] == "touch_session_2"


def test_voice_checkout_delegates_to_shared_complete_order():
    """Verify voice checkout invokes complete_order and transitions screen based on payment method."""
    from screen_controls import ScreenTypes
    from kiosk_service import process_message

    conversation_context["checkout_pending"] = True
    conversation_context["cart"] = [{"type": "item", "id": 13, "quantity": 1}]
    conversation_context["session_id"] = "voice_session_1"

    mock_resp = {
        "success": True,
        "order_id": 1234,
        "status": "pending_payment",
        "total_amount": 139.00,
        "payment_method": "cash",
        "session_id": "voice_session_1",
    }

    with patch("repositories.order_repository.complete_order", return_value=mock_resp) as mock_complete:
        response = process_message("I want to pay by cash", MagicMock())

        mock_complete.assert_called_once()
        args, kwargs = mock_complete.call_args
        assert kwargs["payment_method"] == "cash"
        assert kwargs["session_id"] == "voice_session_1"

        # Screen transitioned to ORDER_COMPLETE
        assert response.screen == ScreenTypes.ORDER_COMPLETE
        assert "1234" in response.message or "placed successfully" in response.message
        # Cart cleared
        assert conversation_context["cart"] == []
        assert conversation_context["checkout_pending"] is False


def test_voice_checkout_upi_payment():
    """Verify voice checkout supports UPI payment method and transitions to PAYMENT screen."""
    from screen_controls import ScreenTypes
    from kiosk_service import process_message

    conversation_context["checkout_pending"] = True
    conversation_context["cart"] = [{"type": "item", "id": 13, "quantity": 1}]
    conversation_context["session_id"] = "voice_session_upi"

    mock_resp = {
        "success": True,
        "order_id": 1235,
        "status": "pending_payment",
        "total_amount": 139.00,
        "payment_method": "upi",
        "session_id": "voice_session_upi",
    }

    with patch("repositories.order_repository.complete_order", return_value=mock_resp) as mock_complete:
        response = process_message("I will pay using UPI", MagicMock())

        mock_complete.assert_called_once()
        args, kwargs = mock_complete.call_args
        assert kwargs["payment_method"] == "upi"
        assert kwargs["session_id"] == "voice_session_upi"

        assert response.screen == ScreenTypes.PAYMENT
        assert "UPI" in response.message or "QR code" in response.message
        assert conversation_context["cart"] == []
        assert conversation_context["checkout_pending"] is False


def test_voice_checkout_cancel_preserves_cart():
    """Verify voice user saying cancel when checkout is pending resets checkout_pending and preserves cart."""
    from screen_controls import ScreenTypes
    from kiosk_service import process_message

    conversation_context["checkout_pending"] = True
    conversation_context["cart"] = [{"type": "item", "id": 13, "quantity": 1}]
    conversation_context["session_id"] = "voice_session_cancel"

    response = process_message("cancel checkout", MagicMock())

    assert response.screen == ScreenTypes.CART
    assert "cancelled" in response.message.lower()
    assert len(conversation_context["cart"]) == 1
    assert conversation_context["checkout_pending"] is False


def test_voice_checkout_timeout_preserves_checkout_pending_for_retry():
    """Verify timeout during voice checkout preserves checkout_pending so customer can retry."""
    from kiosk_service import process_message

    conversation_context["checkout_pending"] = True
    conversation_context["cart"] = [{"type": "item", "id": 13, "quantity": 1}]
    conversation_context["session_id"] = "voice_session_timeout"

    mock_resp = {
        "success": False,
        "code": "NETWORK_TIMEOUT",
        "message": "Connection to order control centre timed out. Please retry.",
    }

    with patch("repositories.order_repository.complete_order", return_value=mock_resp):
        response = process_message("pay with cash", MagicMock())

        assert "timed out" in str(response).lower() or "retry" in str(response).lower()
        # Cart preserved
        assert len(conversation_context["cart"]) == 1
        # checkout_pending remains True for retry
        assert conversation_context["checkout_pending"] is True
