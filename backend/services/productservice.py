from schemas import KioskResponse, ScreenTypes
from services.menu_service import (get_product,get_category)


def handle_product(item_name):

    product = get_product(item_name)

    meal_offer = None


    if not product:
        return KioskResponse(
            screen=ScreenTypes.HOME,
            message="Sorry, I couldn't find that item."
        )

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