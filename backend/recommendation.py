from datetime import date
from db_service import get_available_menu, get_menu_by_category
from knowledgeservice import get_relevant_knowledge


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

    return menu_sorted[:2]


def handle_recommendation(user_input, conversation_context, llm):

    knowledge = get_relevant_knowledge(user_input, llm)

    if conversation_context["last_category"]:

        category_items = get_menu_by_category(conversation_context["last_category"])

        category_names = " ".join(
            [item["name"].lower() for item in category_items]
        )

        if any(word in knowledge.lower() for word in category_names.split()):
            items = category_items
            category = conversation_context["last_category"]
        else:
            items = get_available_menu()
            category = "menu"

    else:
        items = get_available_menu()
        category = "menu"

    priority = get_priority_items(items)

    if not priority:
        return "Everything available is already shown."

    priority_text = "\n".join(
        [f"{item['name']} – ₹{int(item['price'])}" for item in priority]
    )

    prompt = f"""
You are a Burger King India cashier.

Customer asked:
{user_input}

Current category:
{category}

Priority items:
{priority_text}

Relevant product knowledge:
{knowledge}

Rules:
- Recommend naturally
- Prefer priority items when suitable
- Use product knowledge if relevant
- Do not invent unavailable items
- Keep answer short and natural
"""

    response = llm.invoke(prompt)

    return response.content