from schemas import OrderIntent
from services.menu_service import get_available
from ontology import infer_category_from_text


VALID_ACTIONS = {
    "show_category",
    "add_item",
    "recommend",
    "remove_item",
    "expand_context",
    "decline_offer",
    "checkout",
    "correct_item",
    "greeting",
    "exit",
    "unknown",
}


def parse_intent_response(raw_response):
    if not raw_response:
        return OrderIntent(action="unknown")

    values = {
        "action": None,
        "item_name": None,
        "category": None,
        "reference": None,
        "preference": None,
        "quantity": None,
    }

    for line in str(raw_response).splitlines():
        line = line.strip()

        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip().lower()
        value = value.strip()

        if value.lower() in {"none", "null", ""}:
            value = None

        if key in values:
            values[key] = value

    action = values["action"]

    if action not in VALID_ACTIONS:
        return OrderIntent(action="unknown")

    quantity = values["quantity"]

    if quantity is not None:
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            quantity = 1
    else:
        quantity = 1

    return OrderIntent(
        action=action,
        item_name=values["item_name"],
        category=values["category"],
        reference=values["reference"],
        preference=values["preference"],
        quantity=quantity,
    )


def extract_intent(user_input, llm, conversation_context):

    menu = get_available()

    menu_names = [
        item["name"]
        for item in menu
    ]

    current_category = conversation_context.get(
        "last_category"
    )

    last_offer = conversation_context.get(
        "last_offer"
    )

    pending_suggestion = conversation_context.get(
        "pending_suggestion"
    )

    cart = conversation_context.get(
        "cart",
        []
    )

    prompt = f"""
You are the global intent understanding system for a restaurant kiosk.

The screen-level system has already determined that the customer's
message is NOT a direct action on the current screen.

Your job is to understand the customer's restaurant request and
classify it into one of these actions:

show_category
add_item
recommend
remove_item
expand_context
decline_offer
checkout
correct_item
greeting
exit
unknown

CURRENT CATEGORY:
{current_category}

LAST OFFERED ITEMS:
{last_offer}

PENDING SUGGESTION:
{pending_suggestion}

CURRENT CART:
{cart}

AVAILABLE MENU ITEMS:
{menu_names}

CUSTOMER MESSAGE:
{user_input}

Interpret the customer's meaning naturally.

Use show_category when the customer wants to browse or see a
category of food or drinks.

Use add_item only when the customer identifies a specific menu item
they want.

Use recommend when the customer is asking for a recommendation
rather than simply browsing.

Use expand_context when the customer wants additional options
after something has already been shown.

Use decline_offer when the customer rejects an existing suggestion.

Use remove_item when the customer wants something removed from the cart.

Use checkout when the customer wants to complete the order.

Use correct_item when the customer is correcting a previous request.

Use greeting for greetings.

Use exit when the customer wants to end the interaction.

Use unknown when the meaning cannot be understood.

Do not invent menu items or categories.

For category requests, identify the category and preference when
they are naturally expressed by the customer.

For specific menu items, identify the item name and quantity when
available.

Return exactly these fields:

ACTION=<action>
ITEM_NAME=<item name or None>
CATEGORY=<category or None>
REFERENCE=<reference or None>
PREFERENCE=<preference or None>
QUANTITY=<quantity or None>

Return nothing else.
"""

    try:
        print("\n" + "=" * 80)
        print("GLOBAL INTENT — PROMPT BEING SENT TO LLM")
        print("=" * 80)
        print(prompt)
        print("=" * 80 + "\n")

        response = llm.invoke(prompt)

        raw_response = response.content

        print(
            "RAW GLOBAL INTENT RESPONSE:",
            raw_response
        )

        result = parse_intent_response(
            raw_response
        )

        if result.category:
            normalized_category = (
                infer_category_from_text(
                    result.category
                )
            )

            if normalized_category:
                result.category = normalized_category

        print(
            "EXTRACTED INTENT:",
            result
        )

        return result

    except Exception as e:
        print(
            "INTENT ERROR:",
            e
        )

        return OrderIntent(
            action="unknown"
        )