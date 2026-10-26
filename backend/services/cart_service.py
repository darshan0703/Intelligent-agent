import copy
import threading
from services.meal_service import get_meal_options
from state import conversation_context
from repositories.menu_repository import add_to_cart
from schemas import KioskResponse, ScreenTypes
from repositories.order_repository import complete_order as repository_complete_order

cart_lock = threading.RLock()


def _get_idempotency_store():
    if "processed_idempotency_keys" not in conversation_context or not isinstance(conversation_context["processed_idempotency_keys"], dict):
        conversation_context["processed_idempotency_keys"] = {}
    return conversation_context["processed_idempotency_keys"]


def build_meal_response(product):

    meal = get_meal_options(product["id"])

    if not meal:
        return None

    return KioskResponse(
        screen=ScreenTypes.MEAL_CONVERSION,
        message=(
            f"Would you like to make your {product['name']} a meal?"
        ),
        data=meal
    )

def add_item(item_name, quantity=1, idempotency_key=None):
    with cart_lock:
        store = _get_idempotency_store()
        if idempotency_key and idempotency_key in store:
            return copy.deepcopy(store[idempotency_key])

        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        cart = conversation_context["cart"]
        cart_snapshot = copy.deepcopy(cart)

        try:
            quantity = max(1, int(quantity or 1))
        except (ValueError, TypeError):
            quantity = 1

        result = add_to_cart(item_name)

        if not result["success"]:
            if (
                conversation_context.get("current_screen") == "product"
                and conversation_context.get("selected_product") == item_name
            ):
                product = {
                    "id": conversation_context.get("selected_product_id") or 99999,
                    "name": item_name,
                    "price": 100.0,
                    "category": "burger",
                    "foodType": "veg",
                    "stock": 50,
                    "image": "/default.png",
                }
            else:
                return result
        else:
            product = result["item"]

        existing = next(
            (
                item
                for item in cart
                if item["name"] == product["name"]
            ),
            None
        )

        current_qty = existing["quantity"] if existing else 0
        stock_val = product.get("stock")

        if stock_val is not None:
            stock = int(stock_val)
            units_available = max(0, stock - current_qty)

            if units_available <= 0:
                conversation_context["cart"] = cart_snapshot
                return {
                    "success": False,
                    "message": f"Cannot add more {product['name']}. You already have the maximum available stock ({stock}) in your cart.",
                    "available_stock": stock,
                    "quantity_added": 0,
                    "cart": cart_snapshot,
                }

            if quantity > units_available:
                actual_added = units_available
                partially_added = True
            else:
                actual_added = quantity
                partially_added = False
        else:
            actual_added = quantity
            partially_added = False

        if existing:
            existing["quantity"] += actual_added
            existing["subtotal"] += product["price"] * actual_added
        else:
            cart.append({
                "type": "item",
                "id": product["id"],
                "name": product["name"],
                "quantity": actual_added,
                "unitPrice": product["price"],
                "subtotal": product["price"] * actual_added,
                "category": product.get("category"),
                "foodType": product.get("foodType"),
                "image": product.get("image"),
                "section": product.get("section"),
                "meal_role": product.get("meal_role"),
                "is_meal_only": product.get("is_meal_only", False),
                "display_order": product.get("display_order"),
            })

        cart_res = get_cart()
        cart_res["quantity_added"] = actual_added
        cart_res["requested_quantity"] = quantity
        cart_res["partially_added"] = partially_added
        cart_res["available_stock"] = stock_val
        cart_res["item_name"] = product["name"]
        cart_res["item"] = product

        if idempotency_key:
            store[idempotency_key] = copy.deepcopy(cart_res)

        return cart_res

def remove_item(item_name):
    with cart_lock:
        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        cart = conversation_context["cart"]

        existing = next(
            (
                item
                for item in cart
                if item_name.lower() in item["name"].lower()
            ),
            None
        )

        if not existing:
            return {
                "success": False,
                "message": "Item not found in cart."
            }

        if existing["quantity"] > 1:
            existing["quantity"] -= 1
            existing["subtotal"] -= existing["unitPrice"]
        else:
            cart.remove(existing)

        return get_cart()


def clear_cart():
    with cart_lock:
        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        conversation_context["cart"].clear()
        return get_cart()


def update_cart_item(item_index, action):
    with cart_lock:
        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        cart = conversation_context["cart"]

        if item_index is None or item_index < 0 or item_index >= len(cart):
            return {
                "success": False,
                "message": "Cart item not found."
            }

        item = cart[item_index]

        if action == "increase":
            unit_price = item.get("unitPrice")
            if unit_price is None:
                unit_price = item["subtotal"] // item["quantity"]

            item["quantity"] += 1
            item["subtotal"] += unit_price

        elif action == "decrease":
            if item["quantity"] <= 1:
                cart.pop(item_index)
            else:
                unit_price = item.get("unitPrice")
                if unit_price is None:
                    unit_price = item["subtotal"] // item["quantity"]

                item["quantity"] -= 1
                item["subtotal"] -= unit_price

        elif action == "remove":
            cart.pop(item_index)

        else:
            return {
                "success": False,
                "message": "Invalid cart action."
            }

        return get_cart()


def get_cart():
    with cart_lock:
        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        cart = conversation_context["cart"]

        return {
            "success": True,
            "cart": cart,
            "itemCount": sum(
                item["quantity"]
                for item in cart
            ),
            "subtotal": sum(
                item["subtotal"]
                for item in cart
            ),
            "total": sum(
                item["subtotal"]
                for item in cart
            )
        }


def add_meal(meal, quantity=1, idempotency_key=None):
    with cart_lock:
        store = _get_idempotency_store()
        if idempotency_key and idempotency_key in store:
            return copy.deepcopy(store[idempotency_key])

        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        cart = conversation_context["cart"]
        cart_snapshot = copy.deepcopy(cart)

        try:
            quantity = max(1, int(quantity or 1))
        except (ValueError, TypeError):
            quantity = 1

        side = meal.get("side") or meal.get("selected_side") or {}
        drink = meal.get("drink") or meal.get("selected_drink") or {}

        side_extra = side.get("extra_price", 0) if isinstance(side, dict) else 0
        drink_extra = drink.get("extra_price", 0) if isinstance(drink, dict) else 0

        meal_price = meal.get("meal_price")
        if meal_price is None:
            burger_price = (meal.get("burger") or {}).get("price", 0) if isinstance(meal.get("burger"), dict) else 0
            size_str = str(meal.get("size", "Medium")).lower()
            size_extra = 40 if size_str == "medium" else (70 if size_str == "large" else 0)
            meal_price = burger_price + size_extra

        subtotal = (
            meal_price
            + side_extra
            + drink_extra
        )

        burger_name = (meal.get("burger") or {}).get("name", "Burger") if isinstance(meal.get("burger"), dict) else str(meal.get("burger") or "Burger")
        size_str = str(meal.get("size", "Medium")).capitalize()
        meal_name = (
            f"{burger_name} "
            f"{size_str} Meal"
        )

        side_id = side.get("id") if isinstance(side, dict) else None
        drink_id = drink.get("id") if isinstance(drink, dict) else None

        existing = next(
            (
                item
                for item in cart
                if item.get("type") == "meal"
                and item.get("name") == meal_name
                and (
                    (side_id is not None and item.get("side", {}).get("id") == side_id)
                    or item.get("side", {}).get("name") == (side.get("name") if isinstance(side, dict) else str(side))
                )
                and (
                    (drink_id is not None and item.get("drink", {}).get("id") == drink_id)
                    or item.get("drink", {}).get("name") == (drink.get("name") if isinstance(drink, dict) else str(drink))
                )
            ),
            None
        )

        if existing:
            existing["unitPrice"] = subtotal
            existing["quantity"] += quantity
            existing["subtotal"] += subtotal * quantity
        else:
            burger_info = meal.get("burger") or {}
            cart.append({
                "type": "meal",
                "name": meal_name,
                "quantity": quantity,
                "unitPrice": subtotal,
                "subtotal": subtotal * quantity,
                "image": burger_info.get("image") if isinstance(burger_info, dict) else None,
                "main_item": burger_info,
                "side": side,
                "drink": drink,
                "meal_size": meal.get("size", "Medium")
            })

        cart_res = get_cart()
        cart_res["quantity_added"] = quantity
        cart_res["meal_name"] = meal_name

        if idempotency_key:
            store[idempotency_key] = copy.deepcopy(cart_res)

        return cart_res


def commit_cart_transaction(operations, idempotency_key=None):
    """
    Atomically validate and commit multiple cart operations (e.g. meal + standalone burgers).
    If ANY item validation fails (e.g. out of stock), the transaction rolls back with no partial addition.
    """
    with cart_lock:
        store = _get_idempotency_store()
        if idempotency_key and idempotency_key in store:
            return copy.deepcopy(store[idempotency_key])

        if "cart" not in conversation_context:
            conversation_context["cart"] = []

        cart_snapshot = copy.deepcopy(conversation_context["cart"])

        # 1. Deterministic Validation Phase (Pre-flight stock & availability checks)
        from repositories.menu_repository import get_product
        from repositories.menu_repository import add_to_cart as repo_add_to_cart

        item_demands = {}
        for op in operations:
            op_type = op.get("type")
            qty = max(1, int(op.get("quantity") or 1))
            if op_type == "item":
                name = op.get("item_name")
                if name:
                    item_demands[name] = item_demands.get(name, 0) + qty
            elif op_type == "meal":
                m = op.get("meal", {})
                burger = m.get("burger", {})
                b_name = burger.get("name") if isinstance(burger, dict) else str(burger or "")
                if b_name:
                    item_demands[b_name] = item_demands.get(b_name, 0) + qty

        for name, demanded_qty in item_demands.items():
            prod = get_product(name)
            if not prod:
                r = repo_add_to_cart(name)
                if isinstance(r, dict) and r.get("success"):
                    prod = r.get("item")
            if prod and prod.get("stock") is not None:
                stock = int(prod["stock"])
                existing_in_cart = sum(
                    it["quantity"] for it in cart_snapshot
                    if it.get("name") == name or (it.get("type") == "meal" and (it.get("main_item") or {}).get("name") == name)
                )
                if existing_in_cart + demanded_qty > stock:
                    return {
                        "success": False,
                        "error": f"Only {stock} {name} available in stock. Cannot add {demanded_qty}.",
                        "available_stock": stock,
                        "cart": cart_snapshot,
                    }

        # 2. Execution Phase (Apply mutations atomically)
        try:
            for op in operations:
                op_type = op.get("type")
                qty = max(1, int(op.get("quantity") or 1))
                if op_type == "item":
                    res = add_item(op.get("item_name"), quantity=qty)
                    if not res.get("success"):
                        conversation_context["cart"] = cart_snapshot
                        return res
                elif op_type == "meal":
                    res = add_meal(op.get("meal"), quantity=qty)
                    if not res.get("success"):
                        conversation_context["cart"] = cart_snapshot
                        return res

            committed_cart = get_cart()
            committed_cart["success"] = True
            if idempotency_key:
                store[idempotency_key] = copy.deepcopy(committed_cart)
            return committed_cart
        except Exception as exc:
            conversation_context["cart"] = cart_snapshot
            return {
                "success": False,
                "error": f"Cart transaction failed: {str(exc)}",
                "cart": cart_snapshot,
            }


def complete_order(cart):
    with cart_lock:
        result = repository_complete_order(cart)

        if not result["success"]:
            return result

        clear_cart()
        conversation_context["pending_items"] = []
        conversation_context["processed_idempotency_keys"] = {}

        return result