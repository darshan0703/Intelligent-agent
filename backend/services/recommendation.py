from datetime import date
from services.menu_service import (
    get_available,
    get_category,
)
from pprint import pprint

def get_priority_items(menu):
    today = date.today()
    

    for item in menu:
        days_to_expiry = (item["expiry"] - today).days
        expiry_score = max(0, 30 - days_to_expiry)
        item["priority"] = item["stock"] + expiry_score

    menu_sorted = sorted(
        menu,
        key=lambda x: x["priority"],
        reverse=True
    )
    pprint(menu_sorted[0])

    return menu_sorted[:2]


def handle_recommendation(user_input, conversation_context, llm):
    """
    Version 1 Recommendation Engine

    - No Restaurant Knowledge
    - No Semantic Discovery
    - Recommend using current category
    - Fallback to full menu if no category selected
    """

    if conversation_context["last_category"]:
        items = get_category(conversation_context["last_category"])
        category = conversation_context["last_category"]
    else:
        items = get_available()
        category = "menu"

    priority = get_priority_items(items)

    if not priority:
        return "Sorry, there are no recommendations available right now."

    priority_text = "\n".join(
        [f"{item['name']} – ₹{int(item['price'])}" for item in priority]
    )

    prompt = f"""
You are a friendly Burger King India cashier.

The customer said:
{user_input}

Current category:
{category}

Recommended items:
{priority_text}

Rules:
- Recommend ONLY from the list above.
- Do not invent menu items.
- Keep the response short (1-2 sentences).
- Sound natural and friendly.
"""

    response = llm.invoke(prompt)

    return response.content