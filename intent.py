import json
from schemas import OrderIntent
from db_service import get_available_menu

def extract_intent(user_input,llm,conversation_context):

    structured_llm = llm.with_structured_output(OrderIntent)

    menu = get_available_menu()
    menu_names = [item["name"] for item in menu]

    prompt = f"""
You are an intelligent restaurant intent extractor.

Understand customer intent semantically.

Available menu items:
{menu_names}

Current cart:
{conversation_context["cart"]}

Current category:
{conversation_context["last_category"]}

Customer message:
{user_input}
Rules:

Rules:

- If customer names a specific purchasable menu item directly:
  action = add_item

- If customer describes a preference, ingredient, size, taste, texture, preparation style, or property
  without naming an exact menu item:
  action = recommend

- If customer mentions quantity, extract quantity separately

- If customer wants to remove something already ordered:
  action = remove_item

- If customer asks for specials / best / highlights:
  action = show_priority_menu

- If customer asks for all available items:
  action = show_full_menu

- If customer asks for a category:
  action = show_category
- If customer asks for more within current context:
  action = expand_context

- If customer declines recommendation or upsell:
  action = decline_offer

Allowed categories:
burger
beverage
dessert
side

- If customer asks for recommendation:
  action = recommend

- If customer asks for more within current context:
  action = expand_context

- If customer declines recommendation / upsell:
  action = decline_offer

- If customer says:
  that's it
  done
  enough
  action = checkout

- If greeting or casual talk:
  action = unknown

- If customer refers to previous order AND also mentions a new menu item:
  action = correct_item

- If customer only wants to remove something without adding new item:
  action = remove_item

Important:

- Extract only the meaningful product phrase
- Remove conversational filler words naturally
- Preserve customer meaning
- Do NOT force exact menu item names
- Do NOT replace unavailable items
- Keep raw customer wording

- If customer uses partial names:
  preserve the partial wording

Examples:

Customer: strawberry sundae
item_name = strawberry sundae

Customer: crispy chicken
item_name = crispy chicken

Customer: fusion sundae
item_name = fusion sundae

- If customer says cancel / remove / don't want / delete:
  action = remove_item
"""

    try:
        result = structured_llm.invoke(prompt)

        if result.category:
            mapping = {
                "burgers": "burger",
                "burger": "burger",
                "drinks": "beverage",
                "drink": "beverage",
                "beverages": "beverage",
                "desserts": "dessert",
                "dessert": "dessert",
                "sides": "side",
                "side": "side"
            }

            result.category = mapping.get(result.category.lower(), result.category.lower())

        return result

    except Exception:
        return OrderIntent(action="unknown")