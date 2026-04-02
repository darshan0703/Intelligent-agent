from db_service import add_to_cart, get_available_menu
from recommendation import get_priority_items


def find_best_match(clean_item, menu):
    user_tokens = set(clean_item.split())

    best_match = None
    best_score = 0

    for item in menu:
        item_tokens = set(item["name"].lower().split())
        score = len(user_tokens & item_tokens)

        if score > best_score:
            best_score = score
            best_match = item

    return best_match if best_score > 0 else None


def handle_order(item_name, quantity, conversation_context, llm):

    if conversation_context["pending_suggestion"]:
        for item in conversation_context["pending_suggestion"]:
            if item_name.lower() in item.lower():
                item_name = item
                conversation_context["pending_suggestion"] = None
                break

    menu = get_available_menu()

    clean_item = item_name.lower().strip()

    exact_match = next(
        (
            item for item in menu
            if item["name"].lower().strip() == clean_item
        ),
        None
    )

    if not exact_match:

        partial_matches = [
            item for item in menu
            if clean_item in item["name"].lower()
        ]

        if len(partial_matches) == 1:
            exact_match = partial_matches[0]

        elif len(partial_matches) > 1:
            options = ", ".join([item["name"] for item in partial_matches])
            return f"Did you mean {options}?"

        else:
          exact_match = find_best_match(clean_item, menu)

          if not exact_match:
            similar = [
             item["name"]
             for item in menu
             if any(word in item["name"].lower() for word in clean_item.split())
              ]

            if similar:
              conversation_context["pending_suggestion"] = similar
              return f"We don't currently have {item_name}, but we do have {', '.join(similar)}. Would you like one of those?"

          return f"Sorry, we don't currently have {item_name}."
    for _ in range(quantity):
        result = add_to_cart(exact_match["name"])

        if not result["success"]:
            return result["message"]

        conversation_context["cart"].append({
            "name": exact_match["name"],
            "price": exact_match["price"]
        })

    total_price = exact_match["price"] * quantity
    item_name = exact_match["name"]

    if quantity > 1:
        base_reply = f"You've added {quantity} {item_name} to your order, that's ₹{int(total_price)}."
    else:
        base_reply = f"You've added {item_name} to your order, that's ₹{int(total_price)}."

    menu = get_available_menu()
    priority_items = get_priority_items(menu)

    upsell = None
    for item in priority_items:
        if item["name"] != item_name:
            upsell = item["name"]
            break

    if upsell:
        return base_reply + f" Would you like to try our {upsell} with that?"

    return base_reply


def handle_remove(item_name, conversation_context):

    cart = conversation_context["cart"]

    matched = None

    for item in cart:
        if item_name.lower() in item["name"].lower():
            matched = item
            break

    if matched:
        cart.remove(matched)
        return f"{matched['name']} removed from your order. Anything else?"

    return "That item is not in your cart."