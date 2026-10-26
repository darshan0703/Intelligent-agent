import re
from typing import Optional

from langchain_core.tools import tool

from services.menu_service import get_product
from services.recommendation import get_agent_recommendations
from services.product_selector import resolve_product
from services.productservice import handle_product
from screen_controls import get_screen_controls
from state import conversation_context
from kiosk_service import track_screen
from schemas import ScreenTypes

WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "both": 2,
}

def extract_requested_quantity(quantity_param, text):
    if quantity_param is not None:
        if isinstance(quantity_param, int) and quantity_param > 0:
            return quantity_param
        if isinstance(quantity_param, str):
            clean = quantity_param.strip().lower()
            if clean in WORD_TO_NUM:
                return WORD_TO_NUM[clean]
            digits = re.findall(r"\b\d+\b", clean)
            if digits:
                return max(1, int(digits[0]))
    if text:
        clean = text.strip().lower()
        leading = re.match(r"^\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", clean)
        if leading:
            val = leading.group(1)
            return WORD_TO_NUM.get(val, int(val) if val.isdigit() else 1)
        match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:burgers?|items?|meals?|of|units?)\b", clean)
        if match:
            val = match.group(1)
            return WORD_TO_NUM.get(val, int(val) if val.isdigit() else 1)
        action_match = re.search(r"\b(?:get|want|have|order|need)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", clean)
        if action_match:
            val = action_match.group(1)
            return WORD_TO_NUM.get(val, int(val) if val.isdigit() else 1)
    return 1


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

get_menu_item_details.metadata = {"read_only": True, "concurrency_safe": True}


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

get_recommendations.metadata = {"read_only": True, "concurrency_safe": True}


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

        if conversation_context.get("current_screen") == "meal_conversion":
            return {
                "success": False,
                "error": (
                    "The customer is currently customizing a meal on the Meal Builder screen. "
                    "Do NOT navigate away with open_category. Use screen_action(control='swap_meal_item', value='...') "
                    "to swap sides and drinks for this meal."
                ),
            }

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

            track_screen(response)

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

def extract_meal_intent_and_size(text: str) -> tuple[bool, str | None, str]:
    if not text:
        return False, None, text
    clean = text.strip()
    if re.search(r"\b(?:no|not|without|don'?t\s+want|do\s+not\s+want)\s+(?:a\s+)?(?:meals?|combos?)\b", clean, re.IGNORECASE):
        is_meal = False
    else:
        is_meal = bool(re.search(r"\b(?:meals?|combos?)\b", clean, re.IGNORECASE))
    meal_size = None
    if is_meal:
        if re.search(r"\blarge\b", clean, re.IGNORECASE):
            meal_size = "large"
        elif re.search(r"\bmedium\b", clean, re.IGNORECASE):
            meal_size = "medium"

    query_for_prod = re.sub(r"\b(?:large|medium|regular)\b", "", clean, flags=re.IGNORECASE)
    query_for_prod = re.sub(r"\b(?:meals?|combos?)\b", "", query_for_prod, flags=re.IGNORECASE)
    query_for_prod = re.sub(r"^\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+", "", query_for_prod, flags=re.IGNORECASE)
    query_for_prod = re.sub(r"\s+(?:burgers?|items?|units?)\s*$", "", query_for_prod, flags=re.IGNORECASE)
    query_for_prod = re.sub(r"\s+", " ", query_for_prod).strip()
    return is_meal, meal_size, query_for_prod


@tool
def select_product(product_query: str, quantity: int | str | None = None):
    """
    Select and display a specific restaurant product on the kiosk.

    Use this whenever the customer requests, asks for, or mentions a specific menu item
    (e.g., 'Can I get a Chicken Makhani', 'I want four Peri Peri Veg burgers', 'switch to Chicken Makhani'),
    including when selecting a product or switching to a different product from any screen.
    """

    if conversation_context.get("current_screen") == "meal_conversion":
        return {
            "success": False,
            "status": "on_meal_screen",
            "error": (
                "The customer is currently customizing a meal on the Meal Builder screen. "
                "Do NOT call select_product. Use screen_action(control='swap_meal_item', value='...') "
                "to select or swap sides and drinks for this meal."
            ),
        }

    requested_quantity = extract_requested_quantity(quantity, product_query)
    is_explicit_meal, explicit_size, cleaned_query_for_prod = extract_meal_intent_and_size(product_query)

    # Check current customer utterance if meal intent or size was not in tool args
    user_msg = conversation_context.get("current_user_message")
    if user_msg and not conversation_context.get("_has_upgrade_to_meal_in_turn"):
        if re.search(r"\b(?:no|not|without|don'?t\s+want|do\s+not\s+want)\s+(?:a\s+)?(?:meals?|combos?)\b", user_msg, re.IGNORECASE):
            is_explicit_meal = False
            explicit_size = None
        else:
            msg_is_meal, msg_size, _ = extract_meal_intent_and_size(user_msg)
            if not is_explicit_meal and msg_is_meal:
                is_explicit_meal = True
            if not explicit_size and msg_size:
                explicit_size = msg_size

    result = resolve_product(
        product_query,
        conversation_context,
    )

    if result.get("status") != "selected" and cleaned_query_for_prod:
        result_clean = resolve_product(cleaned_query_for_prod, conversation_context)
        if result_clean.get("status") == "selected":
            result = result_clean

    if result.get("status") != "selected" and requested_quantity > 1:
        cleaned_query = re.sub(r"^\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+", "", product_query, flags=re.IGNORECASE).strip()
        cleaned_query = re.sub(r"\s+(?:burgers?|items?|meals?|units?)\s*$", "", cleaned_query, flags=re.IGNORECASE).strip()
        if cleaned_query:
            result_clean = resolve_product(cleaned_query, conversation_context)
            if result_clean.get("status") == "selected":
                result = result_clean

    # ==========================================================
    # PRODUCT FOUND
    # ==========================================================

    if result["status"] == "selected":

        product = result["product"]

        conversation_context["last_item"] = product.get("name")
        conversation_context["selected_product"] = product.get("name")
        conversation_context["selected_product_id"] = product.get("id")
        conversation_context["pending_product"] = product.get("name")
        conversation_context["pending_product_id"] = product.get("id")
        conversation_context["screen_quantity"] = requested_quantity
        conversation_context["original_requested_quantity"] = requested_quantity
        conversation_context["pending_quantity"] = requested_quantity
        conversation_context.pop("meal_stage", None)
        conversation_context.pop("meal_declined_pending_add", None)
        conversation_context.pop("meal_side_decision", None)
        conversation_context.pop("meal_drink_decision", None)

        # Preserve structured pending items for multi-item requests
        if "pending_items" not in conversation_context or not isinstance(conversation_context["pending_items"], list):
            conversation_context["pending_items"] = []

        existing_pending = next(
            (p for p in conversation_context["pending_items"] if p.get("product_id") == product.get("id")),
            None
        )
        if existing_pending:
            existing_pending["quantity"] = requested_quantity
            existing_pending["is_meal"] = is_explicit_meal
            existing_pending["size"] = explicit_size
            existing_pending["fulfilled"] = False
            existing_pending["fulfilled_quantity"] = 0
        else:
            conversation_context["pending_items"].append({
                "product_id": product.get("id"),
                "name": product.get("name"),
                "quantity": requested_quantity,
                "is_meal": is_explicit_meal,
                "size": explicit_size,
                "fulfilled": False,
                "fulfilled_quantity": 0,
            })

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

        # --------------------------------------------------
        # EXPLICIT MEAL INTENT HANDLING
        # --------------------------------------------------
        if is_meal_eligible and is_explicit_meal:
            chosen_size = explicit_size or ("medium" if "medium" in available_meal_sizes else available_meal_sizes[0])
            from services.meal_service import build_meal
            pref = conversation_context.get("food_preference")
            cart = conversation_context.get("cart", [])
            meal_data = build_meal(product.get("id"), chosen_size, food_preference=pref, cart=cart)
            if meal_data:
                conversation_context["active_meal"] = meal_data
                conversation_context["current_screen"] = ScreenTypes.MEAL_CONVERSION
                conversation_context["meal_stage"] = "side_upgrade"
                conversation_context["meal_offer"] = {
                    "is_open": False,
                    "product_id": product.get("id"),
                    "product_name": product.get("name"),
                    "available_sizes": available_meal_sizes,
                }
                conversation_context["explicit_meal_intent"] = {
                    "product_id": product.get("id"),
                    "product_name": product.get("name"),
                    "size": chosen_size,
                    "quantity": requested_quantity,
                }

                from schemas import KioskResponse
                meal_response = KioskResponse(
                    screen=ScreenTypes.MEAL_CONVERSION,
                    message=f"I've started your {chosen_size} {product['name']} meal.",
                    data={
                        "meal": meal_data,
                        "product": product,
                        "quantity": requested_quantity,
                    }
                )
                conversation_context["_last_kiosk_response"] = meal_response
                track_screen(meal_response, extra={"meal_customization": meal_data})

                return {
                    "success": True,
                    "status": "selected",
                    "product": {
                        "id": product.get("id"),
                        "name": product.get("name"),
                        "price": product.get("price"),
                    },
                    "requested_quantity": requested_quantity,
                    "screen": ScreenTypes.MEAL_CONVERSION,
                    "meal_offer": {
                        "eligible": True,
                        "explicit_meal": True,
                        "size": chosen_size,
                        "available_sizes": available_meal_sizes,
                        "suggested_cashier_prompt": (
                            f"I've set up your {chosen_size} {product['name']} meal with fries and a drink. "
                            "Would you like to customize your side or drink?"
                        ),
                    },
                }

        # --------------------------------------------------
        # STANDARD PRODUCT PAGE RESPONSE
        # --------------------------------------------------

        response = handle_product(
            product["name"],
            conversation_context,
        )
        response.data["quantity"] = requested_quantity

        conversation_context["_last_kiosk_response"] = response
        track_screen(response, extra={"product": product})

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
            "requested_quantity": requested_quantity,
            "screen": response.screen,
        }

        if is_meal_eligible:
            ret["meal_offer"] = {
                "eligible": True,
                "explicit_meal": False,
                "available_sizes": available_meal_sizes,
                "suggested_cashier_prompt": (
                    "Would you like to make that a meal?"
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

select_product.metadata = {"read_only": False, "concurrency_safe": False}

restaurant_tools = [
    get_menu_item_details,
    get_recommendations,
    select_product,
]