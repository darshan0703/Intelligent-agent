from db_service import add_to_cart, get_available_menu
from recommendation import get_priority_items
from semanticresolver import semantic_resolve


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

    return best_match if best_score >= 2 else None

def infer_category_from_menu(clean_item, menu):
    user_tokens = set(clean_item.split())
    category_scores = {}

    for item in menu:
        item_tokens = set(item["name"].lower().split())
        score = len(user_tokens & item_tokens)

        if score > 0:
            category = item["category"]
            category_scores[category] = category_scores.get(category, 0) + score

    if category_scores:
        return max(category_scores, key=category_scores.get)

    return None

def handle_order(item_name, quantity, category, conversation_context, llm):

    if not item_name:
        return "Could you tell me which item you'd like?"

    menu = get_available_menu()

    resolved = semantic_resolve(
        item_name,
        menu,
        conversation_context
    )

    if resolved["needs_clarification"]:
        conversation_context["pending_suggestion"] = [
            item["name"] for item in resolved["candidates"]
        ]
        return resolved["clarification_question"]

    if not resolved["resolved_item"]:
        return f"Sorry, we don't currently have {item_name}."

    exact_match = resolved["resolved_item"]

    for _ in range(quantity):
        result = add_to_cart(exact_match["name"])

        if not result["success"]:
            return result["message"]

        conversation_context["cart"].append({
            "name": exact_match["name"],
            "price": exact_match["price"]
        })

    conversation_context["pending_suggestion"] = None
    conversation_context["last_item"] = exact_match["name"]

    total_price = exact_match["price"] * quantity
    item_name = exact_match["name"]

    if quantity > 1:
        base_reply = f"You've added {quantity} {item_name} to your order, that's ₹{int(total_price)}."
    else:
        base_reply = f"You've added {item_name} to your order, that's ₹{int(total_price)}."

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