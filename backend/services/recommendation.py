from datetime import date, datetime
from services.menu_service import get_available, get_category
from services.modules.m01_dietary_lock import apply_dietary_lock


def get_priority_items(menu):
    today = date.today()
    for item in menu:
        expiry = item.get("expiry")
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry).date()
        days_to_expiry = (expiry - today).days if expiry else 30
        expiry_score = max(0, 30 - days_to_expiry)
        item["priority"] = item.get("stock", 0) + expiry_score

    return sorted(menu, key=lambda x: x["priority"], reverse=True)


def build_recommendations(items, food_type="both", cart=None):
    """
    Builds 3-tier recommendation tuples: (priority, premium, additional).
    Guarantees strict dietary lock filtering (Module 1).
    Guarantees mutual exclusion (no item appears in more than one tier).
    """
    if cart is None:
        try:
            from state import conversation_context
            cart = conversation_context.get("cart", [])
        except Exception:
            cart = []

    pref = None if food_type == "both" else food_type
    filtered = apply_dietary_lock(items, preference=pref, cart=cart or [])

    priority_candidates = get_priority_items(filtered)
    priority = priority_candidates[:2]
    used_ids = {i.get("id") or i.get("name") for i in priority}

    premium = []
    for item in sorted(filtered, key=lambda x: float(x.get("price") or 0), reverse=True):
        item_id = item.get("id") or item.get("name")
        if item_id not in used_ids:
            premium.append(item)
        if len(premium) == 2:
            break
    for p in premium:
        used_ids.add(p.get("id") or p.get("name"))

    additional = []
    for item in filtered:
        item_id = item.get("id") or item.get("name")
        if item_id not in used_ids:
            additional.append(item)
        if len(additional) == 4:
            break

    return priority, premium, additional


def get_agent_recommendations(category=None, food_type=None, cart=None):
    if category:
        items = get_category(category)
    else:
        items = get_available()

    if not items:
        return {
            "category": category,
            "recommended": None,
            "premium": None
        }

    priority, premium, _ = build_recommendations(items, food_type=food_type or "both", cart=cart)

    return {
        "category": category,
        "recommended": priority[0] if priority else None,
        "premium": premium[0] if premium else None
    }
