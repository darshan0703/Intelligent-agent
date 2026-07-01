from state import conversation_context
from repositories.menu_repository import add_to_cart


def add_item(item_name, quantity=1):

    cart = conversation_context["cart"]

    for _ in range(quantity):

        result = add_to_cart(item_name)

        if not result["success"]:
            return result

        existing = next(
            (
                item
                for item in cart
                if item["name"] == result["item"]
            ),
            None
        )

        if existing:

            existing["quantity"] += 1
            existing["subtotal"] += result["price"]

        else:

            cart.append({

                "name": result["item"],

                "quantity": 1,

                "unitPrice": result["price"],

                "subtotal": result["price"]

            })

    return get_cart()


def remove_item(item_name):

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

    conversation_context["cart"].clear()

    return get_cart()


def get_cart():

    cart = conversation_context["cart"]

    return {

        "success": True,

        "cart": cart,

        "itemCount": sum(
            item["quantity"]
            for item in cart
        ),

        "total": sum(
            item["subtotal"]
            for item in cart
        )

    }