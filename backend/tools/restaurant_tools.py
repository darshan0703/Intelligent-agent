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
    Get restaurant recommendations using the deterministic
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

        Returns:
        - Summary for the LLM (top 2 items only)
        - Hidden navigation context (entire displayed list)
        - Full KioskResponse is preserved for the frontend
        """

        response = handle_category(
            category,
            conversation_context,
        )

        if hasattr(response, "screen") and hasattr(response, "data"):

            # Preserve the complete frontend response
            conversation_context["_last_kiosk_response"] = response

            data = response.data or {}

            selected = data.get("selected_type", "both")
            section = data.get(selected, {})

            priority = section.get("priority", [])
            premium = section.get("premium", [])
            additional = section.get("additional", [])

            # Complete visual order shown on the kiosk
            displayed_items = priority + premium + additional

            return {
                "success": True,
                "screen": response.screen,

                # Canonical backend identifier
                "category": category.lower().strip(),

                # Customer-facing summary
                "summary": {
                    "top_choices": [
                        item["name"] for item in priority[:2]
                    ],
                    "has_more_options": len(displayed_items) > 2,
                },

                # Internal reasoning only
                "context": {
                    "displayed_items": [
                        {
                            "position": index + 1,
                            "name": item["name"],
                            "id": item.get("id"),
                        }
                        for index, item in enumerate(displayed_items)
                    ],
                    "selected_type": selected,
                },
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

    Use this when the customer mentions a particular menu item.
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

        response = handle_product(
            product["name"],
            conversation_context,
        )

        # Preserve the complete product page response
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
    # MULTIPLE MATCHES
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