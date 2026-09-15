from langchain_core.tools import tool

from services.menu_service import (
    get_available,
    get_category,
    get_product,
)

from services.recommendation import get_agent_recommendations

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

    Args:
        item_name:
            The name of the menu item.

    Returns:
        The matching menu item details, or None if no item is found.
    """

    return get_product(item_name)


# ==========================================================
# RESTAURANT RECOMMENDATIONS
# ==========================================================

@tool
def get_recommendations(
    category: str | None = None,
    food_type: str | None = None,
):
    """
    Get restaurant recommendations using the existing deterministic
    recommendation system.

    Use this when you need to recommend items to a customer rather
    than simply search for available menu items.

    Args:
        category:
            Optional category such as burger, drink, side, or dessert.

        food_type:
            Optional food preference such as veg or non veg.

    Returns:
        Recommendation candidates selected by the restaurant's
        deterministic recommendation logic.
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

        Args:
            category:
                The restaurant category to open.

        Returns:
            Only the information needed by the agent after
            the category has been opened.
        """

        response = handle_category(
            category,
            conversation_context,
        )

        # Keep the complete KioskResponse inside the application.
        # The frontend needs the full menu data.
        if hasattr(response, "screen") and hasattr(response, "data"):

            conversation_context["_last_kiosk_response"] = response

            data = response.data or {}

            priority = data.get("priority", [])
            premium = data.get("premium", [])
            additional = data.get("additional", [])

            return {
                "success": True,
                "category": category,

                # Only one of each is exposed to the agent.
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
# ALL STATIC RESTAURANT TOOLS
# ==========================================================

restaurant_tools = [
    get_menu_item_details,
    get_recommendations,
]