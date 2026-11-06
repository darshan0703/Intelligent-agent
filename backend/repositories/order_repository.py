"""
Kiosk Order Repository.
Routes order completion through TheAtom Control Centre atomic checkout endpoint
via authenticated backend-to-backend communication.
"""

import os
import uuid
import logging
import httpx
from repositories.menu_repository import clear_menu_cache

logger = logging.getLogger(__name__)

def get_control_centre_url():
    """Dynamically resolve Control Centre URL from environment with sensible default."""
    url = os.getenv("CONTROL_CENTRE_URL") or "http://localhost:8001"
    # Safeguard against accidental self-referencing to kiosk's own port 8000
    if url.rstrip("/").endswith(":8000"):
        logger.warning("CONTROL_CENTRE_URL points to port 8000 (kiosk port). Falling back to http://localhost:8001.")
        return "http://localhost:8001"
    return url


def get_control_centre_key():
    return os.getenv("CONTROL_CENTRE_API_KEY", "theatom_kiosk_integration_dev_secret_2026")


def get_branch_id():
    try:
        return int(os.getenv("KIOSK_BRANCH_ID", "1"))
    except (ValueError, TypeError):
        return 1


def normalize_cart_for_persistence(cart):
    """
    Transform kiosk cart items into the structured format required by Control Centre checkout RPC.
    Preserves standalone items and combo component structures without trusting client-provided prices.
    Fails closed on unidentifiable items.
    """
    items = []
    for item in cart:
        if not isinstance(item, dict):
            continue
        try:
            qty = max(1, int(item.get("quantity") or 1))
        except (ValueError, TypeError):
            qty = 1

        if item.get("type") == "meal" or item.get("combo"):
            main_item = item.get("main_item") or {}
            side = item.get("side") or {}
            drink = item.get("drink") or {}
            burger_id = main_item.get("id") or item.get("burger_id")
            side_id = side.get("id") or item.get("side_id")
            drink_id = drink.get("id") or item.get("drink_id")
            size = str(item.get("meal_size") or "medium").lower()
            if size == "king":
                size = "large"
            if burger_id and side_id and drink_id:
                try:
                    items.append({
                        "combo": True,
                        "burger_id": int(burger_id),
                        "meal_size": size,
                        "side_id": int(side_id),
                        "drink_id": int(drink_id),
                        "quantity": qty,
                    })
                except (ValueError, TypeError):
                    continue
        else:
            item_id = item.get("id") or item.get("item_id")
            if item_id is not None:
                try:
                    items.append({
                        "combo": False,
                        "item_id": int(item_id),
                        "quantity": qty,
                    })
                except (ValueError, TypeError):
                    continue
    return items


def complete_order(cart, session_id=None, payment_method="cash", idempotency_key=None):
    """
    Atomically complete order via Control Centre authenticated checkout endpoint.
    Handles timeout, retries with the same idempotency key, and prevents duplicate deductions.
    Shared across both touch and voice checkout paths.
    """
    if not cart:
        return {
            "success": False,
            "status_code": 400,
            "code": "EMPTY_CART",
            "message": "Cart is empty. Please add items before checkout."
        }

    # Ensure explicit session_id
    if not session_id or not str(session_id).strip():
        try:
            from state import conversation_context
            session_id = conversation_context.get("session_id")
        except Exception:
            pass
        if not session_id:
            session_id = str(uuid.uuid4())

    # Ensure durable idempotency_key (stable across retries of the same logical checkout)
    if not idempotency_key or not str(idempotency_key).strip():
        try:
            from state import conversation_context
            idempotency_key = conversation_context.get("current_idempotency_key")
            if not idempotency_key:
                idempotency_key = f"kiosk_{uuid.uuid4()}"
                conversation_context["current_idempotency_key"] = idempotency_key
        except Exception:
            idempotency_key = f"kiosk_{uuid.uuid4()}"

    # Validate payment method — reject invalid values instead of silently defaulting
    pm = str(payment_method or "").lower().strip()
    if pm not in ("cash", "card", "upi"):
        return {
            "success": False,
            "status_code": 400,
            "code": "INVALID_PAYMENT_METHOD",
            "message": f"Invalid payment method: {payment_method!r}. Must be cash, card, or upi.",
        }

    normalized_items = normalize_cart_for_persistence(cart)
    if not normalized_items:
        return {
            "success": False,
            "status_code": 400,
            "code": "INVALID_ITEMS",
            "message": "Cart contains no valid recognized menu items for persistence.",
        }

    base_url = get_control_centre_url()
    api_key = get_control_centre_key()
    branch_id = get_branch_id()

    endpoint_url = f"{base_url.rstrip('/')}/api/v1/orders/checkout"
    headers = {
        "Content-Type": "application/json",
        "X-Kiosk-Key": api_key,
    }
    payload = {
        "session_id": str(session_id).strip(),
        "idempotency_key": str(idempotency_key).strip(),
        "branch_id": branch_id,
        "payment_method": pm,
        "items": normalized_items,
    }

    try:
        # Bounded 10.0s timeout for backend-to-backend call
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint_url, headers=headers, json=payload)

        if resp.status_code in (200, 201):
            try:
                data = resp.json()
            except Exception:
                logger.error("Control Centre returned non-JSON 200/201 response.")
                return {
                    "success": False,
                    "status_code": 502,
                    "code": "MALFORMED_RESPONSE",
                    "message": "Order service returned an unreadable response format.",
                }

            # Invalidate the menu cache after stock deductions succeed
            clear_menu_cache()
            return {
                "success": True,
                "status_code": resp.status_code,
                "order_id": data.get("order_id"),
                "total_amount": data.get("total_amount"),
                "status": data.get("status", "pending_payment"),
                "payment_method": data.get("payment_method", pm),
                "session_id": session_id,
                "idempotency_key": idempotency_key,
                "created_at": data.get("created_at"),
                "message": "Order completed successfully.",
            }
        else:
            try:
                err_body = resp.json()
                detail = err_body.get("detail") or err_body.get("message") or resp.text
            except Exception:
                detail = resp.text

            logger.error(f"Control Centre checkout failed with status {resp.status_code}: {detail}")
            
            # Map HTTP error codes to clear domain codes
            if resp.status_code == 401:
                code = "AUTH_ERROR"
            elif resp.status_code == 404:
                code = "NOT_FOUND"
            elif resp.status_code == 409:
                code = "CONFLICT"
            elif resp.status_code == 422:
                code = "VALIDATION_ERROR"
            elif resp.status_code >= 500:
                code = "UPSTREAM_ERROR"
            else:
                code = "ORDER_REJECTED"

            return {
                "success": False,
                "status_code": resp.status_code,
                "code": code,
                "message": f"Order checkout failed ({resp.status_code}): {detail}",
                "detail": detail,
            }

    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to Control Centre checkout ({endpoint_url}): {e}")
        return {
            "success": False,
            "status_code": 504,
            "code": "NETWORK_TIMEOUT",
            "message": "Connection to order control centre timed out. Please retry.",
        }
    except httpx.ConnectError as e:
        logger.error(f"Connection failed to Control Centre checkout ({endpoint_url}): {e}")
        return {
            "success": False,
            "status_code": 503,
            "code": "SERVICE_UNAVAILABLE",
            "message": "Could not connect to order control centre. Please ensure the control service is running.",
        }
    except Exception as e:
        logger.error(f"Unexpected connection error to Control Centre checkout: {e}")
        return {
            "success": False,
            "status_code": 502,
            "code": "CONNECTION_ERROR",
            "message": f"Checkout connection error: {str(e)}",
        }
