from datetime import date
from services.menu_service import get_available, get_category

def get_priority_items(menu):
    today = date.today()

    for item in menu:
        days_to_expiry = (item["expiry"] - today).days
        expiry_score = max(0, 30 - days_to_expiry)
        item["priority"] = item["stock"] + expiry_score
        
    menu_sorted = sorted(
        menu,
        key=lambda x: x["priority"],
        reverse=True
    )

    return menu_sorted[:2]


def build_recommendations(items):
    priority = get_priority_items(items)

    premium = []

    for item in sorted(items, key=lambda x: x["price"], reverse=True):
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


def get_agent_recommendations(category=None, food_type=None):
    if category:
        items = get_category(category)
    else:
        items = get_available()

    if food_type:
        normalized_food_type = food_type.lower().replace("_", " ").strip()

        items = [
            item for item in items
            if item.get("foodType", "").lower() == normalized_food_type
        ]

    if not items:
        return {
            "category": category,
            "recommended": None,
            "premium": None
        }

    priority, premium, _ = build_recommendations(items)

    return {
        "category": category,
        "recommended": priority[0] if priority else None,
        "premium": premium[0] if premium else None
    }
