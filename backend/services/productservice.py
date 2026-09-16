from schemas import KioskResponse, ScreenTypes
from services.menu_service import get_product, get_category


def handle_product(item_name, conversation_context):

    product = get_product(item_name)

    if not product:
        return KioskResponse(
            screen=ScreenTypes.HOME,
            message="Sorry, I couldn't find that item."
        )

    # ==========================================
    # START A NEW PRODUCT / MEAL INTERACTION
    # ==========================================

    conversation_context["meal_flow"] = {
        "item_id": product["id"],
        "status": "pending"
    }

    # ==========================================
    # RECOMMENDATIONS
    # ==========================================

    recommendations = []

    for item in get_category(product["category"]):

        if item["name"] != product["name"]:
            recommendations.append(item)

        if len(recommendations) == 3:
            break

    return KioskResponse(
        screen=ScreenTypes.PRODUCT_DETAILS,
        message=f"Here's {product['name']}.",
        data={
            "product": product,
            "recommendations": recommendations
        }
    )