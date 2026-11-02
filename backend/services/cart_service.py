from services.meal_service import get_meal_options
from state import conversation_context
from repositories.menu_repository import add_to_cart
from schemas import KioskResponse, ScreenTypes
from repositories.order_repository import complete_order as repository_complete_order

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

def add_item(item_name, quantity=1):

    if "cart" not in conversation_context:
        conversation_context["cart"] = []

    cart = conversation_context["cart"]

    result = add_to_cart(item_name)

    if not result["success"]:
        return result

    product = result["item"]

    existing = next(
        (
            item
            for item in cart
            if item["name"] == product["name"]
        ),
        None
    )

    if existing:

        existing["quantity"] += quantity
        existing["subtotal"] += product["price"] * quantity

    else:

        cart.append({
            "type": "item",

            "id": product["id"],

            "name": product["name"],

            "quantity": quantity,

            "unitPrice": product["price"],

            "subtotal": product["price"] * quantity,

            "category": product["category"],

            "foodType": product["foodType"],

            "image": product["image"],

            "section": product.get("section"),

            "meal_role": product.get("meal_role"),

            "is_meal_only": product.get("is_meal_only", False),

            "display_order": product.get("display_order"),

        })

    return get_cart()

def remove_item(item_name):

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

    if "cart" not in conversation_context:
        conversation_context["cart"] = []

    conversation_context["cart"].clear()

    return get_cart()

def update_cart_item(item_index, action):
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

def add_meal(meal, quantity=1, replace_index=None, expected_item_id=None, expected_side_id=None, expected_drink_id=None):

    if "cart" not in conversation_context:
        conversation_context["cart"] = []

    cart = conversation_context["cart"]

    if replace_index is not None:
        if not isinstance(replace_index, int) or replace_index < 0 or replace_index >= len(cart):
            return {
                "success": False,
                "message": "Invalid cart item index for replacement.",
                "cart": cart,
                "itemCount": sum(item["quantity"] for item in cart),
                "subtotal": sum(item["subtotal"] for item in cart),
                "total": sum(item["subtotal"] for item in cart),
            }

        target_item = cart[replace_index]

        # Verify that target item is a meal
        if not isinstance(target_item, dict) or target_item.get("type") != "meal":
            return {
                "success": False,
                "message": "Cart item at specified index is not a meal.",
                "cart": cart,
                "itemCount": sum(item["quantity"] for item in cart),
                "subtotal": sum(item["subtotal"] for item in cart),
                "total": sum(item["subtotal"] for item in cart),
            }

        # Verify burger identifier against original meal
        target_burger = target_item.get("main_item") or target_item.get("burger") or {}
        target_burger_id = target_burger.get("id") if isinstance(target_burger, dict) else None

        expected_burger_id = expected_item_id
        if expected_burger_id is None:
            sub_burger = meal.get("burger") or meal.get("main_item") or {}
            expected_burger_id = sub_burger.get("id") if isinstance(sub_burger, dict) else None

        if expected_burger_id is not None:
            if target_burger_id is None or str(target_burger_id) != str(expected_burger_id):
                return {
                    "success": False,
                    "message": "Cart item at specified index no longer matches the meal being customized.",
                    "cart": cart,
                    "itemCount": sum(item["quantity"] for item in cart),
                    "subtotal": sum(item["subtotal"] for item in cart),
                    "total": sum(item["subtotal"] for item in cart),
                }

        # Verify side identifier if specified
        if expected_side_id is not None:
            target_side = target_item.get("side") or {}
            target_side_id = target_side.get("id") if isinstance(target_side, dict) else None
            if target_side_id is None or str(target_side_id) != str(expected_side_id):
                return {
                    "success": False,
                    "message": "Cart item at specified index no longer matches the meal being customized.",
                    "cart": cart,
                    "itemCount": sum(item["quantity"] for item in cart),
                    "subtotal": sum(item["subtotal"] for item in cart),
                    "total": sum(item["subtotal"] for item in cart),
                }

        # Verify drink identifier if specified
        if expected_drink_id is not None:
            target_drink = target_item.get("drink") or {}
            target_drink_id = target_drink.get("id") if isinstance(target_drink, dict) else None
            if target_drink_id is None or str(target_drink_id) != str(expected_drink_id):
                return {
                    "success": False,
                    "message": "Cart item at specified index no longer matches the meal being customized.",
                    "cart": cart,
                    "itemCount": sum(item["quantity"] for item in cart),
                    "subtotal": sum(item["subtotal"] for item in cart),
                    "total": sum(item["subtotal"] for item in cart),
                }

    side = meal.get("side") or {}
    drink = meal.get("drink") or {}

    side_extra = side.get("extra_price", 0) if isinstance(side, dict) else 0
    drink_extra = drink.get("extra_price", 0) if isinstance(drink, dict) else 0

    subtotal = (
        meal["meal_price"]
        + side_extra
        + drink_extra
    )

    burger_info = meal.get("burger") or {}
    burger_name = burger_info.get("name", "Burger") if isinstance(burger_info, dict) else str(burger_info)

    meal_name = (
        f"{burger_name} "
        f"{meal['size'].capitalize()} Meal"
    )

    new_item = {
        "type": "meal",
        "name": meal_name,
        "quantity": quantity,
        "unitPrice": subtotal,
        "subtotal": subtotal * quantity,
        "image": burger_info.get("image") if isinstance(burger_info, dict) else None,
        "main_item": burger_info,
        "side": side,
        "drink": drink,
        "meal_size": meal["size"]
    }

    if replace_index is not None:
        cart[replace_index] = new_item
    else:
        existing = next(
            (
                item
                for item in cart
                if item["type"] == "meal"
                and item["name"] == meal_name
                and item.get("side", {}).get("id") == side.get("id")
                and item.get("drink", {}).get("id") == drink.get("id")
            ),
            None
        )

        if existing:
            existing["unitPrice"] = subtotal
            existing["quantity"] += quantity
            existing["subtotal"] += subtotal * quantity
        else:
            cart.append(new_item)

    return get_cart()


def complete_order(cart):
    result = repository_complete_order(cart)

    if not result["success"]:
        return result

    clear_cart()

    return result