from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)
from state import conversation_context


def handle_greeting(user_input,conversation_context, llm):

    if conversation_context["cart"]:

        prompt = f"""
You are a Burger King India cashier.

Customer said:
{user_input}

Current cart:
{conversation_context["cart"]}

Rules:
- Respond naturally
- Understand customer may be closing order
- If customer declines suggestion, gently ask whether they want checkout
- Do not greet again unnecessarily
"""

    else:

        prompt = f"""
You are a friendly cashier at Burger King India.

Customer said:
{user_input}

Rules:
- Respond naturally
- Keep it short
- Do not repeat welcome every time
"""

    response = llm.invoke(prompt)

    return response.content

def handle_checkout(conversation_context, llm):

    cart = conversation_context.get("cart", [])

    if not cart:
        return "Your cart is empty."

    total = sum(
        item.get("subtotal", 0)
        for item in cart
    )

    conversation_context["checkout_pending"] = True

    item_names = []

    for item in cart:

        if item.get("type") == "meal":
            name = item.get("name", "Meal")
        else:
            name = item.get("name", "Item")

        quantity = item.get("quantity", 1)

        item_names.append(
            f"{quantity} x {name}"
        )

    items = ", ".join(item_names)

    prompt = f"""
You are a Burger King India cashier.

Facts:
- Items ordered: {items}
- Total: ₹{int(total)}

Rules:
- Speak naturally like a cashier
- Mention the total correctly
- Ask the customer whether they will pay by cash or card
- Do not change the total
- Do not add or remove any items
"""

    response = llm.invoke(prompt)

    return response.content

def handle_decline(conversation_context, llm):

    prompt = f"""
You are a Burger King India cashier.

Facts:
- Current cart: {conversation_context.get('cart', [])}

Customer declined the previous suggestion.

Rules:
- Do not greet again
- Speak naturally
- Do not change the cart
- Ask whether the customer wants checkout or more items
"""

    response = llm.invoke(prompt)

    return response.content


def handle_correction(item_name, conversation_context):

    cart = conversation_context.get("cart", [])

    if not cart:
        return "Tell me what you'd like to order."

    previous = cart.pop()

    result = add_to_cart(item_name)

    if result["success"]:

        new_item = result["item"]

        cart.append({
            **new_item,
            "quantity": previous.get("quantity", 1)
        })

        return (
            f"Sure 👍 I've replaced "
            f"{previous.get('name', 'that item')} with "
            f"{new_item['name']} for "
            f"₹{int(new_item['price'])}."
        )

    cart.append(previous)

    return (
        f"{item_name} is not available, so I kept "
        f"{previous.get('name', 'your previous item')} "
        f"in your cart."
    )