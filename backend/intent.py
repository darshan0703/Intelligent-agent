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

    situation_block = ""

    if conversation_context.get("last_category"):
     situation_block += f"Customer is currently browsing {conversation_context['last_category']} items.\n"

    if conversation_context.get("last_offer"):
     situation_block += "System has already shown some items in this category.\n"

    if conversation_context.get("pending_suggestion"):
     situation_block += "System is waiting for confirmation on a suggested item.\n"

    if conversation_context.get("pending_clarification"):
     situation_block += f"System is waiting for clarification about {conversation_context['pending_clarification']}.\n"
    
    if not situation_block:
     situation_block = "No special dialogue state."

    pre_category = infer_category_from_text(user_input)
    
    if pre_category:

     text = user_input.lower()

     if pre_category == "burger":

        return OrderIntent(
            action="show_category",
            category="burger"
        )

     if any(
        word in text
        for word in [
            "what",
            "show",
            "have",
            "options"
        ]
      ):
        return OrderIntent(
            action="show_category",
            category=pre_category
         )

    prompt = f"""
You are an intelligent restaurant intent extractor.

Your job is to classify customer intent strictly and extract structured meaning.

CURRENT SITUATION (read carefully before classifying):
{situation_block}

Given this situation, classify the customer's intent.

If the customer appears to continue browsing current category
(using phrases like more, what else, anything else, other options),
use expand_context.
Available menu items:

{menu_names}

Current cart:
{conversation_context["cart"]}

Current category:
{conversation_context["last_category"]}

Last offered items:
{conversation_context.get("last_offer")}

Pending suggestion:
{conversation_context.get("pending_suggestion")}

Waiting for confirmation:
{True if conversation_context.get("pending_suggestion") else False}


Follow this decision order strictly:
0. If the customer wants to order a category item
   but has not specified a concrete item:

Examples:
- can i get a burger
- i want a burger
- give me a burger
- i'd like a burger
- can i have a dessert
- can i get a drink

action = show_category

category = inferred category

Do NOT use recommend.

1. If customer asks for a class/list/group/category of items
   (burgers, desserts, drinks, beverages, sides, options, what do you have, show items):
   action = show_category

2. If customer names a specific purchasable menu item directly:
   action = add_item

3. If customer describes taste, ingredient, size, texture, preparation, or preference
   without exact item:
   action = recommend

4. If customer wants to remove / cancel / delete something already ordered:
   action = remove_item

5. If current category exists AND customer says:
   what else
   anything else
   more
   show more
   other options
   action = expand_context

6. If customer declines recommendation or upsell:
   action = decline_offer

7. If customer says:
   that's it
   done
   enough
   action = checkout

8. If pending suggestion exists and customer confirms:
   action = add_item
   item_name = pending suggestion

9. If customer refers to previous order and changes item:
   action = correct_item

10. Otherwise:
   action = unknown


Allowed categories:
burger
beverage
dessert
side


Important extraction rules:

- Extract quantity separately
- item_name must not contain quantity words
- Preserve customer wording
- Do NOT force exact menu item names
- Do NOT replace unavailable items
- Keep raw partial names


Examples:

Customer: what burgers do you have
action = show_category
category = burger

Customer: show desserts
action = show_category
category = dessert

Customer: what drinks are available
action = show_category
category = beverage

Customer: what sides do you have
action = show_category
category = side

Customer: two crispy chicken
action = add_item
item_name = crispy chicken
quantity = 2

Customer: one coke
action = add_item
item_name = coke
quantity = 1

Customer: strawberry sundae
action = add_item
item_name = strawberry sundae

Customer: crispy chicken
action = add_item
item_name = crispy chicken

Customer: vanilla
action = add_item
item_name = vanilla

Customer: chocolate
action = add_item
item_name = chocolate

Customer: something spicy
action = recommend

Customer: what else
(Current category exists)
action = expand_context

Pending suggestion: BK Fusion Sundae
Customer: yeah
action = add_item
item_name = BK Fusion Sundae

Customer: remove fries
action = remove_item

Customer: done
action = checkout


Customer message:
{user_input}
"""

    try:
        result = structured_llm.invoke(prompt)

        # ----------------------------
        # ONTOLOGY CATEGORY NORMALIZATION
        # ----------------------------
        if result.category:
            normalized = infer_category_from_text(result.category)
            if normalized:
                result.category = normalized

        # ----------------------------
        # SAFE FALLBACK FOR SHORT UNKNOWN INPUTS
        # ----------------------------
        menu_text = " ".join([item["name"].lower() for item in menu])

        greetings = {
            "hi", "hello", "hey", "good morning", "good evening"
        }

        exits = {
            "bye", "goodbye", "see you", "exit"
        }

        clean_input = user_input.lower().strip()
        single_word = len(clean_input.split()) <= 2

        if result.action == "unknown":

            if clean_input in greetings:
                result.action = "greeting"

            elif clean_input in exits:
                result.action = "exit"

            elif single_word and any(word in menu_text for word in clean_input.split()):
                result.action = "add_item"
                result.item_name = user_input.strip()

        return result

    except Exception:
        return OrderIntent(action="unknown")