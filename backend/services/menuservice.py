from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)
from services.recommendation import get_priority_items
from state import conversation_context
from schemas import KioskResponse, ScreenTypes


def handle_menu(user_input,conversation_context,llm):

    if conversation_context["last_category"]:
        menu = get_category(conversation_context["last_category"])
    else:
        menu = get_available() 

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

def build_recommendations(items):

    priority = get_priority_items(items)

    premium = []

    for item in sorted(
        items,
        key=lambda x: x["price"],
        reverse=True
    ):
        if item not in priority:
            premium.append(item)

        if len(premium) == 2:
            break

    additional = []

    for item in items:
        if item not in priority and item not in premium:
            additional.append(item)

        if len(additional) == 4:
            break

    return priority, premium, additional

def handle_burger_selection(burger_type, conversation_context):

    burgers = get_category("burger")

    if burger_type == "both":

     filtered = burgers

    else:

     filtered = [
        item for item in burgers
        if item["food_type"].lower() == burger_type
     ]

    if not filtered:
        return "Sorry, no matching burgers are available right now."

    priority_burgers, premium_burgers, additional_burgers = build_recommendations(filtered)
    
    selected = []

    if priority_burgers:
     selected.append(priority_burgers[0])

    for item in premium_burgers:
     if item not in selected:
        selected.append(item)

     if len(selected) == 5:
        break

    conversation_context["last_offer"] = [
     item["name"] for item in selected
    ]
    print("PRIORITY")
    print([x["name"] for x in priority_burgers])

    print("PREMIUM")
    print([x["name"] for x in premium_burgers])

    print("ADDITIONAL")
    print([x["name"] for x in additional_burgers])
    
     
    return KioskResponse(
     screen=ScreenTypes.RECOMMENDED_BURGERS,
     message=(
        "Here are our top burger picks today. "
        "Are you looking for veg or non veg?"
     ),
     data={
        "selected_type": burger_type,
        "all_burgers": filtered,
        "priority": priority_burgers,
        "premium": premium_burgers,
        "additional": additional_burgers
    }
)

def handle_full_menu(conversation_context):

    if conversation_context["last_category"]:
        menu = get_category(conversation_context["last_category"])

        priority = get_priority_items(menu)

        remaining = [item for item in menu if item not in priority]

        if not remaining:
            return f"That's all we currently have in {conversation_context['last_category']}."

        response = "Besides those, we also have:\n\n"

        for item in remaining:
            response += f"• {item['name']} – ₹{int(item['price'])}\n"

        response += "\nThat completes our available options in this category."

        return response

    menu = get_available()

    response = "Sure, here are all available items today:\n\n"

    for item in menu:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nThat's everything currently available. What would you like to order?"

    return response

def handle_category(category, conversation_context):

    category_map = {
        "beverage": "drink",
        "beverages": "drink",
        "drinks": "drink",
        "burger": "burger",
        "burgers": "burger",
        "side": "side",
        "sides": "side",
        "dessert": "dessert",
        "desserts": "dessert"
    }

    category = category_map.get(
        category.lower(),
        category.lower()
    )

    conversation_context["last_category"] = category

    if category == "burger":
     return handle_burger_selection(
        "both",
        conversation_context
    )

    if category == "drink":
     return handle_drink_selection(
        conversation_context
    )

    if category == "side":
     return handle_side_selection(
        conversation_context
    )

    if category == "dessert":
     return handle_dessert_selection(
        conversation_context
    )

    return "Unknown category."

def handle_more_options():
    
    if conversation_context["last_category"]:
        menu = get_category(conversation_context["last_category"])
    else:
        menu = get_available()

    priority_items = get_priority_items(menu)

    remaining_items = [item for item in menu if item not in priority_items]

    if not remaining_items:
        return f"That's all we currently have in {conversation_context['last_category']}."

    response = "Besides those, we also have:\n\n"

    for item in remaining_items:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nWould you like to try any of these?"

    return response

def build_category_response(
    category,
    title,
    screen,
    conversation_context
):

    items = get_category(category)

    if not items:
        return KioskResponse(
            screen=screen,
            message=f"Sorry, no {title.lower()} are available right now.",
            data={}
        )

    priority, premium, additional = build_recommendations(items)

    conversation_context["last_offer"] = [
        item["name"]
        for item in priority + premium + additional
    ]

    return KioskResponse(
        screen=screen,
        message=f"Here are our top {title.lower()} picks today.",
        data={
            "priority": priority,
            "premium": premium,
            "additional": additional
        }
    )

def handle_drink_selection(conversation_context):

    return build_category_response(
        category="drink",
        title="Drinks",
        screen=ScreenTypes.RECOMMENDED_DRINKS,
        conversation_context=conversation_context
    )


def handle_side_selection(conversation_context):

    return build_category_response(
        category="side",
        title="Sides",
        screen=ScreenTypes.RECOMMENDED_SIDES,
        conversation_context=conversation_context
    )


def handle_dessert_selection(conversation_context):

    return build_category_response(
        category="dessert",
        title="Desserts",
        screen=ScreenTypes.RECOMMENDED_DESSERTS,
        conversation_context=conversation_context
    )