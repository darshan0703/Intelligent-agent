from services.meal_service import get_meal_options
from state import conversation_context
from repositories.menu_repository import add_to_cart
from services.menu_service import get_meal_options
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

            "image": product["image"]

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

def add_meal(meal, quantity=1):

    if "cart" not in conversation_context:
        conversation_context["cart"] = []

    cart = conversation_context["cart"]

    side_extra = meal["side"].get("extra_price", 0)
    drink_extra = meal["drink"].get("extra_price", 0)

    subtotal = (
        meal["meal_price"]
        + side_extra
        + drink_extra
    )

    meal_name = (
        f"{meal['burger']['name']} "
        f"{meal['size'].capitalize()} Meal"
    )

    existing = next(
        (
            item
            for item in cart
            if item["type"] == "meal"
            and item["name"] == meal_name
            and item["side"]["id"] == meal["side"]["id"]
            and item["drink"]["id"] == meal["drink"]["id"]
        ),
        None
    )

    if existing:
        existing["unitPrice"] = subtotal
        existing["quantity"] += quantity
        existing["subtotal"] += subtotal * quantity
    else:
        cart.append({
            "type": "meal",
            "name": meal_name,
            "quantity": quantity,
            "unitPrice": subtotal,
            "subtotal": subtotal * quantity,
            "image": meal["burger"].get("image"),
            "main_item": meal["burger"],
            "side": meal["side"],
            "drink": meal["drink"],
            "meal_size": meal["size"]
        })

    return get_cart()

def complete_order(cart):
    result = repository_complete_order(cart)

    if not result["success"]:
        return result

    clear_cart()

    return result