from typing import Optional

from langchain_core.tools import tool

from services.menu_service import get_product
from services.recommendation import get_agent_recommendations
from services.product_selector import resolve_product
from services.productservice import handle_product
from screen_controls import get_screen_controls
from state import conversation_context

def _sync_screen_state(response):
    """
    Synchronize the active kiosk screen and its available controls
    whenever a tool creates a new KioskResponse.

    This keeps the agent's screen_action tool aligned with the screen
    currently being displayed by the frontend.
    """

    if hasattr(response, "screen"):

        conversation_context["current_screen"] = response.screen

        conversation_context["available_controls"] = (
            get_screen_controls(response.screen)
        )

        print(
            "SCREEN STATE SYNC:",
            conversation_context["current_screen"]
        )

        print(
            "AVAILABLE CONTROLS:",
            conversation_context["available_controls"]
        )


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

            # --------------------------------------------------
            # PRESERVE COMPLETE FRONTEND RESPONSE
            # --------------------------------------------------

            conversation_context["_last_kiosk_response"] = response

            # --------------------------------------------------
            # SYNCHRONIZE ACTIVE SCREEN
            # --------------------------------------------------

            _sync_screen_state(response)

            data = response.data or {}

            selected = data.get(
                "selected_type",
                "both",
            )

            section = data.get(
                selected,
                {},
            )

            priority = section.get(
                "priority",
                [],
            )

            premium = section.get(
                "premium",
                [],
            )

            additional = section.get(
                "additional",
                [],
            )

            # --------------------------------------------------
            # COMPLETE VISUAL ORDER SHOWN ON KIOSK
            # --------------------------------------------------

            displayed_items = (
                priority
                + premium
                + additional
            )

            # --------------------------------------------------
            # TOOL RESULT
            # --------------------------------------------------

            return {
                "success": True,
                "screen": response.screen,

                # Canonical backend identifier
                "category": category.lower().strip(),

                # --------------------------------------------------
                # CUSTOMER-FACING SUMMARY
                # --------------------------------------------------

                "summary": {
                    "top_choices": [
                        item["name"]
                        for item in priority[:2]
                    ],
                    "has_more_options": (
                        len(displayed_items) > 2
                    ),
                },

                # --------------------------------------------------
                # INTERNAL REASONING / NAVIGATION CONTEXT
                # --------------------------------------------------

                "context": {
                    "displayed_items": [
                        {
                            "position": index + 1,
                            "name": item["name"],
                            "id": item.get("id"),
                        }
                        for index, item in enumerate(
                            displayed_items
                        )
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
    Select and display a specific restaurant product on the kiosk.

    Use this whenever the customer requests, asks for, or mentions a specific menu item
    (e.g., 'Can I get a Chicken Makhani', 'I want Crispy Veg Double Patty', 'switch to Chicken Makhani'),
    including when selecting a product or switching to a different product from any screen.
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

        conversation_context["last_item"] = product.get("name")
        conversation_context["selected_product_id"] = product.get("id")

        # --------------------------------------------------
        # BUILD PRODUCT PAGE RESPONSE
        # --------------------------------------------------

        response = handle_product(
            product["name"],
            conversation_context,
        )

        # --------------------------------------------------
        # PRESERVE COMPLETE PRODUCT RESPONSE
        # --------------------------------------------------

        conversation_context["_last_kiosk_response"] = response

        # --------------------------------------------------
        # SYNCHRONIZE ACTIVE SCREEN
        # --------------------------------------------------

        _sync_screen_state(response)

        # --------------------------------------------------
        # CHECK MEAL OFFER ELIGIBILITY
        # --------------------------------------------------

        declined_ids = [str(x) for x in conversation_context.get("declined_meal_products", [])]
        is_already_declined = str(product.get("id")) in declined_ids

        is_meal_eligible = False
        available_meal_sizes = []
        if not is_already_declined:
            try:
                from services.meal_service import get_meal_options
                cart = conversation_context.get("cart", [])
                pref = conversation_context.get("food_preference")
                offer = get_meal_options(product.get("id"), food_preference=pref, cart=cart)
                if offer and offer.get("is_meal_available") and isinstance(offer.get("meals"), dict):
                    for sz in ["medium", "large"]:
                        if offer["meals"].get(sz):
                            available_meal_sizes.append(sz)
                    is_meal_eligible = len(available_meal_sizes) > 0
            except Exception as e:
                print(f"Error checking meal options in select_product: {e}")

        if is_meal_eligible:
            conversation_context["meal_offer"] = {
                "is_open": True,
                "product_id": product.get("id"),
                "product_name": product.get("name"),
                "available_sizes": available_meal_sizes,
            }
            controls = list(conversation_context.get("available_controls", []))
            for mc in ["select_meal", "decline_meal"]:
                if mc not in controls:
                    controls.append(mc)
            conversation_context["available_controls"] = controls
        else:
            conversation_context["meal_offer"] = {
                "is_open": False,
                "product_id": product.get("id"),
                "product_name": product.get("name"),
                "available_sizes": [],
            }
            controls = [
                c for c in conversation_context.get("available_controls", [])
                if c not in ["select_meal", "decline_meal", "accept_meal"]
            ]
            conversation_context["available_controls"] = controls

        ret = {
            "success": True,
            "status": "selected",

            "product": {
                "id": product.get("id"),
                "name": product.get("name"),
                "price": product.get("price"),
            },

            "screen": response.screen,
        }

        if is_meal_eligible:
            ret["meal_offer"] = {
                "eligible": True,
                "available_sizes": available_meal_sizes,
                "suggested_cashier_prompt": (
                    "Good choice! Would you like to make that a meal with a side and a drink?"
                ),
            }
        elif is_already_declined:
            ret["meal_offer"] = {
                "eligible": False,
                "already_declined": True,
            }

        return ret

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