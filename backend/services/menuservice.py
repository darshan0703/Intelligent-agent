from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)

from services.recommendation import get_priority_items

from state import conversation_context

from schemas import (
    KioskResponse,
    ScreenTypes
)


# =========================================================
# GENERAL MENU
# =========================================================

def handle_menu(user_input, conversation_context, llm):

    if conversation_context["last_category"]:
        menu = get_category(
            conversation_context["last_category"]
        )
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

    if any(
        word in user_input.lower()
        for word in expanded_keywords
    ):

        response = (
            "Sure, here are all the available items today:\n\n"
        )

        for item in menu:
            response += (
                f"• {item['name']} – ₹{int(item['price'])}\n"
            )

        response += "\nWhat would you like to order?"

        return response

    priority_text = "\n".join(
        [
            f"{item['name']} – ₹{int(item['price'])}"
            for item in priority_items
        ]
    )

    full_menu_text = "\n".join(
        [
            f"{item['name']} – ₹{int(item['price'])}"
            for item in menu
        ]
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


# =========================================================
# BURGER RECOMMENDATION ENGINE
# =========================================================

def build_recommendations(
    items,
    food_type="both"
):

    normalized_type = (
        food_type
        .lower()
        .replace("_", " ")
        .strip()
    )

    # =====================================================
    # SINGLE FOOD TYPE
    # =====================================================

    if normalized_type in ("veg", "non veg"):

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

            if (
                item not in priority
                and item not in premium
            ):
                additional.append(item)

            if len(additional) == 4:
                break

        return (
            priority[:2],
            premium[:2],
            additional[:4]
        )

    # =====================================================
    # BOTH
    # =====================================================

    veg_items = [
        item
        for item in items
        if item.get("foodType", "")
        .lower()
        .replace("_", " ")
        .strip()
        == "veg"
    ]

    non_veg_items = [
        item
        for item in items
        if item.get("foodType", "")
        .lower()
        .replace("_", " ")
        .strip()
        == "non veg"
    ]

    # -----------------------------------------------------
    # PRIORITY
    # -----------------------------------------------------

    veg_priority = (
        get_priority_items(veg_items)
        if veg_items
        else []
    )

    non_veg_priority = (
        get_priority_items(non_veg_items)
        if non_veg_items
        else []
    )

    priority = []

    if veg_priority:
        priority.append(
            veg_priority[0]
        )

    if non_veg_priority:
        priority.append(
            non_veg_priority[0]
        )

    # -----------------------------------------------------
    # PREMIUM
    # -----------------------------------------------------

    used_names = {
        item["name"]
        for item in priority
    }

    veg_premium_candidates = sorted(
        [
            item
            for item in veg_items
            if item["name"] not in used_names
        ],
        key=lambda x: x["price"],
        reverse=True
    )

    non_veg_premium_candidates = sorted(
        [
            item
            for item in non_veg_items
            if item["name"] not in used_names
        ],
        key=lambda x: x["price"],
        reverse=True
    )

    premium = []

    if veg_premium_candidates:
        premium.append(
            veg_premium_candidates[0]
        )

    if non_veg_premium_candidates:
        premium.append(
            non_veg_premium_candidates[0]
        )

    # -----------------------------------------------------
    # ADDITIONAL
    # -----------------------------------------------------

    used_names.update(
        item["name"]
        for item in premium
    )

    remaining = [
        item
        for item in items
        if item["name"] not in used_names
    ]

    additional = remaining[:4]

    return (
        priority[:2],
        premium[:2],
        additional[:4]
    )


# =========================================================
# BUILD COMPLETE BURGER DATASET
# =========================================================

def build_burger_recommendation_data(burgers):

    # -----------------------------------------------------
    # BOTH
    # -----------------------------------------------------

    (
        both_priority,
        both_premium,
        both_additional
    ) = build_recommendations(
        burgers,
        "both"
    )

    # -----------------------------------------------------
    # VEG
    # -----------------------------------------------------

    veg_burgers = [
        item
        for item in burgers
        if item.get("foodType", "")
        .lower()
        .replace("_", " ")
        .strip()
        == "veg"
    ]

    (
        veg_priority,
        veg_premium,
        veg_additional
    ) = build_recommendations(
        veg_burgers,
        "veg"
    )

    # -----------------------------------------------------
    # NON VEG
    # -----------------------------------------------------

    non_veg_burgers = [
        item
        for item in burgers
        if item.get("foodType", "")
        .lower()
        .replace("_", " ")
        .strip()
        == "non veg"
    ]

    (
        non_veg_priority,
        non_veg_premium,
        non_veg_additional
    ) = build_recommendations(
        non_veg_burgers,
        "non veg"
    )

    return {
        "both": {
            "priority": both_priority,
            "premium": both_premium,
            "additional": both_additional
        },

        "veg": {
            "priority": veg_priority,
            "premium": veg_premium,
            "additional": veg_additional
        },

        "non_veg": {
            "priority": non_veg_priority,
            "premium": non_veg_premium,
            "additional": non_veg_additional
        }
    }


# =========================================================
# BURGER SELECTION
# =========================================================

def handle_burger_selection(
    burger_type,
    conversation_context
):

    burgers = get_category("burger")

    if not burgers:

        return KioskResponse(
            screen=ScreenTypes.RECOMMENDED_BURGERS,
            message=(
                "Sorry, no burgers are "
                "available right now."
            ),
            data={}
        )

    # -----------------------------------------------------
    # BUILD ALL THREE DATASETS
    # -----------------------------------------------------

    recommendation_data = (
        build_burger_recommendation_data(
            burgers
        )
    )

    # -----------------------------------------------------
    # DEBUG
    # -----------------------------------------------------

    print("\n==============================")
    print("BURGER RECOMMENDATION DATA")
    print("==============================")

    for food_type, groups in recommendation_data.items():

        total = (
            len(groups["priority"])
            + len(groups["premium"])
            + len(groups["additional"])
        )

        print(f"\nTYPE: {food_type}")

        print(
            "PRIORITY:",
            [
                item["name"]
                for item in groups["priority"]
            ]
        )

        print(
            "PREMIUM:",
            [
                item["name"]
                for item in groups["premium"]
            ]
        )

        print(
            "ADDITIONAL:",
            [
                item["name"]
                for item in groups["additional"]
            ]
        )

        print("TOTAL:", total)

    print("==============================\n")

    # -----------------------------------------------------
    # DEFAULT VIEW = BOTH
    # -----------------------------------------------------

    both = recommendation_data["both"]

    selected = (
        both["priority"]
        + both["premium"]
        + both["additional"]
    )

    conversation_context["last_offer"] = [
        item["name"]
        for item in selected
    ]

    # -----------------------------------------------------
    # NATURAL OPENING MESSAGE
    # -----------------------------------------------------

    message_parts = []

    if both["priority"]:

        message_parts.append(
            f"I'd recommend our "
            f"{both['priority'][0]['name']}."
        )

    if both["premium"]:

        message_parts.append(
            f"If you're looking for something premium, "
            f"we also have our "
            f"{both['premium'][0]['name']}."
        )

    if both["additional"]:

        message_parts.append(
            "We also have more options in burgers "
            "if you'd like to explore them."
        )

    message = " ".join(
        message_parts
    )

    # -----------------------------------------------------
    # RETURN COMPLETE DATASET
    # -----------------------------------------------------

    return KioskResponse(
        screen=ScreenTypes.RECOMMENDED_BURGERS,
        message=message,
        data={
            "selected_type": "both",

            "all_burgers": burgers,

            "both": recommendation_data["both"],

            "veg": recommendation_data["veg"],

            "non_veg": recommendation_data["non_veg"]
        }
    )


# =========================================================
# FULL MENU
# =========================================================

def handle_full_menu(conversation_context):

    if conversation_context["last_category"]:

        menu = get_category(
            conversation_context["last_category"]
        )

        priority = get_priority_items(menu)

        remaining = [
            item
            for item in menu
            if item not in priority
        ]

        if not remaining:

            return (
                f"That's all we currently have in "
                f"{conversation_context['last_category']}."
            )

        response = "Besides those, we also have:\n\n"

        for item in remaining:

            response += (
                f"• {item['name']} – ₹{int(item['price'])}\n"
            )

        response += (
            "\nThat completes our available "
            "options in this category."
        )

        return response

    menu = get_available()

    response = (
        "Sure, here are all available items today:\n\n"
    )

    for item in menu:

        response += (
            f"• {item['name']} – ₹{int(item['price'])}\n"
        )

    response += (
        "\nThat's everything currently available. "
        "What would you like to order?"
    )

    return response


# =========================================================
# CATEGORY
# =========================================================

def handle_category(
    category,
    conversation_context
):

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


# =========================================================
# MORE OPTIONS
# =========================================================

def handle_more_options():

    if conversation_context["last_category"]:

        menu = get_category(
            conversation_context["last_category"]
        )

    else:

        menu = get_available()

    priority_items = get_priority_items(menu)

    remaining_items = [
        item
        for item in menu
        if item not in priority_items
    ]

    if not remaining_items:

        return (
            f"That's all we currently have in "
            f"{conversation_context['last_category']}."
        )

    response = "Besides those, we also have:\n\n"

    for item in remaining_items:

        response += (
            f"• {item['name']} – ₹{int(item['price'])}\n"
        )

    response += (
        "\nWould you like to try any of these?"
    )

    return response


# =========================================================
# OTHER CATEGORY RECOMMENDATIONS
# =========================================================

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
            message=(
                f"Sorry, no {title.lower()} "
                f"are available right now."
            ),
            data={}
        )

    priority, premium, additional = (
        build_recommendations(items)
    )

    conversation_context["last_offer"] = [
        item["name"]
        for item in priority
        + premium
        + additional
    ]

    message_parts = []

    if priority:

        message_parts.append(
            f"I'd recommend our "
            f"{priority[0]['name']}."
        )

    if premium:

        message_parts.append(
            f"For something premium, we also have "
            f"{premium[0]['name']}."
        )

    if additional:

        message_parts.append(
            f"We also have more {title.lower()} "
            f"options if you'd like to explore them."
        )

    message = " ".join(
        message_parts
    )

    return KioskResponse(
        screen=screen,
        message=message,
        data={
            "priority": priority,
            "premium": premium,
            "additional": additional
        }
    )


# =========================================================
# DRINKS
# =========================================================

def handle_drink_selection(
    conversation_context
):

    return build_category_response(
        category="drink",
        title="Drinks",
        screen=ScreenTypes.RECOMMENDED_DRINKS,
        conversation_context=conversation_context
    )


# =========================================================
# SIDES
# =========================================================

def handle_side_selection(
    conversation_context
):

    return build_category_response(
        category="side",
        title="Sides",
        screen=ScreenTypes.RECOMMENDED_SIDES,
        conversation_context=conversation_context
    )


# =========================================================
# DESSERTS
# =========================================================

def handle_dessert_selection(
    conversation_context
):

    return build_category_response(
        category="dessert",
        title="Desserts",
        screen=ScreenTypes.RECOMMENDED_DESSERTS,
        conversation_context=conversation_context
    )