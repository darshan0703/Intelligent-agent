from typing import Optional

from langchain_core.tools import tool

from services.menu_service import get_product
from services.recommendation import get_agent_recommendations
from services.product_selector import resolve_product
from services.productservice import handle_product
from state import conversation_context


# ==========================================================
# ITEM DETAILS
# ==========================================================

@tool
def get_menu_item_details(item_name: str):
    """
    Get complete details about a specific menu item.

    Use this when you need information about a particular item,
    including its description, price, category, food type,
    availability, meal availability, or other stored details.
    """

    return get_product(item_name)


# ==========================================================
# RESTAURANT RECOMMENDATIONS
# ==========================================================

@tool
def get_recommendations(
    category: Optional[str] = None,
    food_type: Optional[str] = None,
):
    """
    Get restaurant recommendations using the existing deterministic
    recommendation system.
    """

    return get_agent_recommendations(
        category=category,
        food_type=food_type,
    )


# ==========================================================
# RUNTIME CATEGORY TOOL
# ==========================================================

def create_open_category_tool(conversation_context):
    from services.menuservice import handle_category

    @tool
    def open_category(category: str):
        """
        Open a restaurant category on the kiosk.

        Use this when the customer wants to browse a category.
        """

        response = handle_category(
            category,
            conversation_context,
        )

        # Keep the complete KioskResponse inside the application.
        if hasattr(response, "screen") and hasattr(response, "data"):

            conversation_context["_last_kiosk_response"] = response

            data = response.data or {}

            priority = data.get("priority", [])
            premium = data.get("premium", [])
            additional = data.get("additional", [])

            return {
                "success": True,
                "category": category,

                "priority_recommendation": (
                    {
                        "name": priority[0].get("name"),
                        "price": priority[0].get("price"),
                    }
                    if priority
                    else None
                ),

                "premium_recommendation": (
                    {
                        "name": premium[0].get("name"),
                        "price": premium[0].get("price"),
                    }
                    if premium
                    else None
                ),

                "more_options_available": bool(additional),
            }

        return response

    return open_category


# ==========================================================
# PRODUCT SELECTION
# ==========================================================

@tool
def select_product(product_query: str):
    """
    Resolve a customer's reference to a specific restaurant product.

    Use this capability when the customer is referring to a particular
    menu item they want, are asking about, or are checking whether it
    is available.

    The query should contain the product the customer is referring to.
    The resolver checks the real restaurant menu and returns matching
    products.

    Do not determine whether the product exists yourself.
    Do not invent product names or variants.
    """

    result = resolve_product(
        product_query,
        conversation_context,
    )

    # ==========================================================
    # PRODUCT FOUND
    # ==========================================================

    if result["status"] == "selected":

        product = result["product"]

        # Build the existing product-page KioskResponse.
        response = handle_product(
            product["name"],
            conversation_context,
        )

        # Store the complete response for the API layer.
        conversation_context["_last_kiosk_response"] = response

        return {
            "success": True,
            "status": "selected",
            "product": {
                "id": product.get("id"),
                "name": product.get("name"),
                "price": product.get("price"),
            },
            "screen": response.screen,
        }

    # ==========================================================
    # MULTIPLE PRODUCTS MATCH
    # ==========================================================

    if result["status"] == "ambiguous":

        return {
            "success": True,
            "status": "ambiguous",
            "matches": [
                {
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "price": product.get("price"),
                }
                for product in result["matches"]
            ],
        }

    # ==========================================================
    # PRODUCT NOT FOUND
    # ==========================================================

    return {
        "success": False,
        "status": "not_found",
        "product_query": product_query,
    }


# ==========================================================
# STATIC RESTAURANT TOOLS
# ==========================================================

restaurant_tools = [
    get_menu_item_details,
    get_recommendations,
    select_product,
]