from schemas import OrderIntent

from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)

from ontology import infer_category_from_text


def extract_intent(user_input, llm, conversation_context):

    structured_llm = llm.with_structured_output(OrderIntent)

    menu = get_available()
    menu_names = [item["name"] for item in menu]

    # ... your existing situation/pre-category logic ...

    prompt = f"""
You are an intelligent restaurant intent extractor.

Your job is to classify customer intent strictly and extract structured meaning.

Available menu items:
{menu_names}

Current cart:
{conversation_context.get("cart", [])}

Current category:
{conversation_context.get("last_category")}

Last offered items:
{conversation_context.get("last_offer")}

Pending suggestion:
{conversation_context.get("pending_suggestion")}

Customer message:
{user_input}

Follow the intent rules defined for the restaurant kiosk.

Category-only requests such as:
"I want a burger"
"I want a drink"
"I want a dessert"
"I want a side"

must use:
action = show_category

They are not add_item requests because the customer has not selected a concrete menu item.

Allowed categories:
burger
beverage
dessert
side
"""

    try:
        result = structured_llm.invoke(prompt)

        if result.category:
            normalized = infer_category_from_text(result.category)

            if normalized:
                result.category = normalized

        menu_text = " ".join(
            item["name"].lower()
            for item in menu
        )

        greetings = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening"
        }

        exits = {
            "bye",
            "goodbye",
            "see you",
            "exit"
        }

        clean_input = user_input.lower().strip()
        single_word = len(clean_input.split()) <= 2

        if result.action == "unknown":

            if clean_input in greetings:
                result.action = "greeting"

            elif clean_input in exits:
                result.action = "exit"

            elif (
                single_word
                and any(
                    word in menu_text
                    for word in clean_input.split()
                )
            ):
                result.action = "add_item"
                result.item_name = user_input.strip()

        return result

    except Exception as e:
        print("INTENT ERROR:", e)
        raise