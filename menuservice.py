from db_service import get_available_menu, get_menu_by_category
from recommendation import get_priority_items
from state import conversation_context


def handle_menu(user_input,conversation_context,llm):

    if conversation_context["last_category"]:
        menu = get_menu_by_category(conversation_context["last_category"])
    else:
        menu = get_available_menu() 

    priority_items = get_priority_items(menu)

    expanded_keywords = [
        "what else",
        "other items",
        "full menu",
        "all items",
        "more options"
    ]

    # If customer asks for more options → show full menu directly
    if any(word in user_input.lower() for word in expanded_keywords):

        response = "Sure, here are all the available items today:\n\n"

        for item in menu:
            response += f"• {item['name']} – ₹{int(item['price'])}\n"

        response += "\nWhat would you like to order?"

        return response

    # Otherwise use LLM for natural selling
    priority_text = "\n".join(
        [f"{item['name']} – ₹{int(item['price'])}" for item in priority_items]
    )

    full_menu_text = "\n".join(
        [f"{item['name']} – ₹{int(item['price'])}" for item in menu]
    )

    prompt = f"""
You are a Burger King India cashier.

Priority items:
{priority_text}

Full menu:
{full_menu_text}

Rules:
- Mention priority items first naturally
- Briefly mention there are more options
- Do not invent items
- Do not change prices
"""

    response = llm.invoke(prompt)

    return response.content

def handle_full_menu(conversation_context):

    if conversation_context["last_category"]:
        menu = get_menu_by_category(conversation_context["last_category"])

        priority = get_priority_items(menu)

        remaining = [item for item in menu if item not in priority]

        if not remaining:
            return f"That's all we currently have in {conversation_context['last_category']}."

        response = "Besides those, we also have:\n\n"

        for item in remaining:
            response += f"• {item['name']} – ₹{int(item['price'])}\n"

        response += "\nThat completes our available options in this category."

        return response

    menu = get_available_menu()

    response = "Sure, here are all available items today:\n\n"

    for item in menu:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nThat's everything currently available. What would you like to order?"

    return response

def handle_category(category, conversation_context):

    conversation_context["last_category"] = category

    items = get_menu_by_category(category)

    if not items:
        return f"Sorry, we don't have any {category} available right now."

    priority = get_priority_items(items)

    response = f"Here are our {category} options today:\n\n"

    for item in priority:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    if len(items) > len(priority):
     response += "\nWe also have more options in this category if you'd like to see them."
    else:
     response += "\nWhat would you like to order?"

    return response

def handle_more_options():
    
    if conversation_context["last_category"]:
        menu = get_menu_by_category(conversation_context["last_category"])
    else:
        menu = get_available_menu()

    priority_items = get_priority_items(menu)

    remaining_items = [item for item in menu if item not in priority_items]

    if not remaining_items:
        return f"That's all we currently have in {conversation_context['last_category']}."

    response = "Besides those, we also have:\n\n"

    for item in remaining_items:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nWould you like to try any of these?"

    return response

