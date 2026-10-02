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
    # SINGLE / ALREADY FILTERED TYPE
    # =====================================================

    if normalized_type in (
        "veg",
        "non veg",
        "hot",
        "cold"
    ):

        priority = get_priority_items(items)[:2]

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

    # =====================================================
    # IMPORTANT:
    # If the category contains only ONE food type
    # (example: desserts are all veg), treat the whole
    # category as one recommendation pool.
    # =====================================================

    if not non_veg_items or not veg_items:

        priority = get_priority_items(items)[:2]

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
    # BOTH VEG + NON-VEG
    # =====================================================

    veg_priority = get_priority_items(veg_items)

    non_veg_priority = get_priority_items(non_veg_items)

    priority = []

    if veg_priority:
        priority.append(
            veg_priority[0]
        )

    if non_veg_priority:
        priority.append(
            non_veg_priority[0]
        )

    # =====================================================
    # PREMIUM
    # =====================================================

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

    # =====================================================
    # ADDITIONAL
    # =====================================================

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
    # SEPARATE FOOD TYPES
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

    non_veg_burgers = [
        item
        for item in burgers
        if item.get("foodType", "")
        .lower()
        .replace("_", " ")
        .strip()
        == "non veg"
    ]

    # -----------------------------------------------------
    # BUILD EACH FOOD-TYPE RECOMMENDATION SET
    #
    # Each set contains:
    #   priority   -> 2
    #   premium    -> 2
    #   additional -> 4
    #
    # These are used only as the source for the combined
    # master lists below. The frontend performs filtering.
    # -----------------------------------------------------

    (
        veg_priority,
        veg_premium,
        veg_additional
    ) = build_recommendations(
        veg_burgers,
        "veg"
    )

    (
        non_veg_priority,
        non_veg_premium,
        non_veg_additional
    ) = build_recommendations(
        non_veg_burgers,
        "non veg"
    )

    # -----------------------------------------------------
    # COMBINED PRIORITY
    #
    # Desired order:
    #   veg1, nonVeg1, veg2, nonVeg2
    # -----------------------------------------------------

    priority = []

    for index in range(2):

        if index < len(veg_priority):
            priority.append(
                veg_priority[index]
            )

        if index < len(non_veg_priority):
            priority.append(
                non_veg_priority[index]
            )

    # -----------------------------------------------------
    # COMBINED PREMIUM
    #
    # Desired order:
    #   veg1, nonVeg1, veg2, nonVeg2
    # -----------------------------------------------------

    premium = []

    for index in range(2):

        if index < len(veg_premium):
            premium.append(
                veg_premium[index]
            )

        if index < len(non_veg_premium):
            premium.append(
                non_veg_premium[index]
            )

    # -----------------------------------------------------
    # COMBINED ADDITIONAL
    #
    # Desired order:
    #   veg1, veg2, veg3, veg4,
    #   nonVeg1, nonVeg2, nonVeg3, nonVeg4
    #
    # The frontend will filter this master list.
    # -----------------------------------------------------

    additional = (
        veg_additional[:4]
        + non_veg_additional[:4]
    )

    return {
        "priority": priority[:4],
        "premium": premium[:4],
        "additional": additional[:8]
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
    # BUILD ONE COMBINED MASTER DATASET
    #
    # The frontend owns the Veg / Non-Veg filter.
    # -----------------------------------------------------

    recommendation_data = (
        build_burger_recommendation_data(
            burgers
        )
    )

 
    print("BURGER MASTER RECOMMENDATION DATA")
   

    total = (
        len(recommendation_data["priority"])
        + len(recommendation_data["premium"])
        + len(recommendation_data["additional"])
    )

    print(
        "PRIORITY:",
        [
            item["name"]
            for item in recommendation_data["priority"]
        ]
    )

    print(
        "PREMIUM:",
        [
            item["name"]
            for item in recommendation_data["premium"]
        ]
    )

    print(
        "ADDITIONAL:",
        [
            item["name"]
            for item in recommendation_data["additional"]
        ]
    )

    print("TOTAL:", total)

    print("==============================\n")

    # -----------------------------------------------------
    # DEFAULT VIEW = BOTH
    # -----------------------------------------------------

    selected = (
        recommendation_data["priority"]
        + recommendation_data["premium"]
        + recommendation_data["additional"]
    )

    conversation_context["last_offer"] = [
        item["name"]
        for item in selected
    ]

    # -----------------------------------------------------
    # NATURAL OPENING MESSAGE
    # -----------------------------------------------------

    message_parts = []

    if recommendation_data["priority"]:

        message_parts.append(
            f"I'd recommend our "
            f"{recommendation_data['priority'][0]['name']}."
        )

    if recommendation_data["premium"]:

        message_parts.append(
            f"If you're looking for something premium, "
            f"we also have our "
            f"{recommendation_data['premium'][0]['name']}."
        )

    if recommendation_data["additional"]:

        message_parts.append(
            "We also have more options in burgers "
            "if you'd like to explore them."
        )

    message = " ".join(
        message_parts
    )

    # -----------------------------------------------------
    # RETURN ONE MASTER DATASET
    # -----------------------------------------------------

    return KioskResponse(
        screen=ScreenTypes.RECOMMENDED_BURGERS,
        message=message,
        data={
            "selected_type": "both",

            "all_burgers": burgers,

            "priority": (
                recommendation_data["priority"]
            ),

            "premium": (
                recommendation_data["premium"]
            ),

            "additional": (
                recommendation_data["additional"]
            )
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

def build_filtered_master_recommendation_data(
    items,
    filter_field,
    filter_values
):

    grouped = {}

    for filter_value in filter_values:

        filtered_items = [
            item
            for item in items
            if item.get(filter_field, "")
            .lower()
            .replace("_", " ")
            .strip()
            == filter_value
        ]

        grouped[filter_value] = build_recommendations(
            filtered_items,
            filter_value
        )

    priority = []
    premium = []
    additional = []

    # 2 priority + 2 premium from every filter value,
    # interleaved into one master list.
    for index in range(2):

        for filter_value in filter_values:

            recommendations = grouped[filter_value]

            if index < len(recommendations[0]):
                priority.append(
                    recommendations[0][index]
                )

            if index < len(recommendations[1]):
                premium.append(
                    recommendations[1][index]
                )

    # 4 additional items from every filter value,
    # interleaved into one master list.
    for index in range(4):

        for filter_value in filter_values:

            recommendations = grouped[filter_value]

            if index < len(recommendations[2]):
                additional.append(
                    recommendations[2][index]
                )

    return {
        "priority": priority,
        "premium": premium,
        "additional": additional
    }


# =========================================================
# CATEGORY RECOMMENDATION RESPONSE
# =========================================================

def build_category_response(
    category,
    title,
    screen,
    conversation_context,
    filter_field=None,
    filter_values=None,
    all_items_key=None
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

    # Filtered categories get a complete master dataset.
    if filter_field and filter_values:

        recommendation_data = (
            build_filtered_master_recommendation_data(
                items,
                filter_field,
                filter_values
            )
        )

    else:

        priority, premium, additional = (
            build_recommendations(items)
        )

        recommendation_data = {
            "priority": priority,
            "premium": premium,
            "additional": additional
        }

    priority = recommendation_data["priority"]
    premium = recommendation_data["premium"]
    additional = recommendation_data["additional"]

    selected = (
        priority
        + premium
        + additional
    )

    conversation_context["last_offer"] = [
        item["name"]
        for item in selected
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

    response_data = {
        "priority": priority,
        "premium": premium,
        "additional": additional
    }

    if filter_values:
        response_data["selected_type"] = "both"

    if all_items_key:
        response_data[all_items_key] = items

    return KioskResponse(
        screen=screen,
        message=message,
        data=response_data
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
        conversation_context=conversation_context,
        filter_field="type",
        filter_values=["hot", "cold"],
        all_items_key="all_drinks"
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
        conversation_context=conversation_context,
        filter_field="foodType",
        filter_values=["veg", "non veg"],
        all_items_key="all_sides"
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
        conversation_context=conversation_context,
        all_items_key="all_desserts"
    )