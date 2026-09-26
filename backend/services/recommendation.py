from datetime import date, datetime
from services.menu_service import get_available, get_category

def get_priority_items(menu):
    today = date.today()

    for item in menu:
        expiry = item["expiry"]

        # Supabase returns ISO date strings
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry).date()

        days_to_expiry = (expiry - today).days
        expiry_score = max(0, 30 - days_to_expiry)

        item["priority"] = item["stock"] + expiry_score

    return sorted(menu, key=lambda x: x["priority"], reverse=True)

def build_recommendations(items):
    from app.intelligence.recommendation.pipeline_runner import run_recommendation_pipeline
    res = run_recommendation_pipeline(items)
    return res["priority"], res["premium"], res["additional"]



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
