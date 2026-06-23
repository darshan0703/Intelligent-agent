from db_service import add_to_cart
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

    if not conversation_context["cart"]:
        return "Your cart is empty."

    total = sum(item["price"] for item in conversation_context["cart"])

    conversation_context["checkout_pending"] = True

    items = ", ".join([item["name"] for item in conversation_context["cart"]])

    prompt = f"""
You are a Burger King India cashier.

Facts:
- Items ordered: {items}
- Total: ₹{int(total)}

Rules:
- Speak naturally like a cashier
- Mention total correctly
- Ask customer whether they will pay by cash or card
- Do not change total
"""

    response = llm.invoke(prompt)

    return response.content

def handle_decline(conversation_context, llm):

    prompt = f"""
You are a Burger King India cashier.

Facts:
- Current cart: {conversation_context['cart']}

Customer declined the previous suggestion.

Rules:
- Do not greet again
- Speak naturally
- Ask whether customer wants checkout or more items
"""

    response = llm.invoke(prompt)

    return response.content


def handle_correction(item_name, conversation_context):

    if not conversation_context["cart"]:
        return "Tell me what you'd like to order."

    previous = conversation_context["cart"].pop()

    result = add_to_cart(item_name)

    if result["success"]:
        conversation_context["cart"].append(
            result["item"]
        )

        return (
            f"Sure 👍 I've replaced "
            f"{previous} with "
            f"{result['item']} for "
            f"₹{int(result['price'])}."
        )

    conversation_context["cart"].append(
        previous
    )

    return (
        f"I removed {previous}, "
        f"but {item_name} is not available."
    )