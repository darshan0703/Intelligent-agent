from conversation import (
    handle_correction,
    handle_decline,
    handle_checkout
)

from intent import extract_intent
from screen_intent import extract_screen_intent
from state import conversation_context
from typing import Optional

from services.menuservice import (
    handle_menu,
    handle_category,
    handle_more_options,
    handle_full_menu
)

from orderservice import (
    handle_order,
    handle_remove
)

from itemclassifiers import resolve_burger_clarification

from schemas import (
    KioskResponse,
    ScreenTypes
)

from services.productservice import handle_product
from screen_controls import get_screen_controls
from services.cashier_response import generate_cashier_response

from langchain_core.tools import tool


# ==========================================
# SCREEN TRACKING
# ==========================================

def track_screen(screen_or_response, extra=None):
    """
    Authoritative central synchronization point for kiosk UI state.
    Handles KioskResponse objects, direct screen strings, controls,
    active product selection, meal offers, and monotonic sequence validation.
    """
    if isinstance(screen_or_response, KioskResponse):
        screen = screen_or_response.screen
        data = screen_or_response.data or {}
    elif isinstance(screen_or_response, str):
        screen = screen_or_response
        data = extra or {}
    else:
        return screen_or_response

    # Verify that screen is a recognized kiosk screen identifier
    valid_screens = {
        ScreenTypes.HOME, ScreenTypes.CATEGORY_SELECTION,
        ScreenTypes.BURGER_TYPE_SELECTION,
        ScreenTypes.RECOMMENDED_BURGERS, ScreenTypes.FULL_BURGER_MENU, ScreenTypes.BURGER_MENU,
        ScreenTypes.RECOMMENDED_DRINKS, ScreenTypes.FULL_DRINK_MENU, ScreenTypes.DRINK_MENU,
        ScreenTypes.RECOMMENDED_SIDES, ScreenTypes.FULL_SIDE_MENU, ScreenTypes.SIDE_MENU,
        ScreenTypes.RECOMMENDED_DESSERTS, ScreenTypes.FULL_DESSERT_MENU, ScreenTypes.DESSERT_MENU,
        ScreenTypes.PRODUCT, ScreenTypes.MEAL_CONVERSION,
        ScreenTypes.UPSELL, ScreenTypes.CART, ScreenTypes.CHECKOUT,
        ScreenTypes.PAYMENT, ScreenTypes.ORDER_COMPLETE,
    }
    if screen not in valid_screens:
        if isinstance(screen_or_response, KioskResponse):
            return screen_or_response
        return screen_or_response, True

    # 1. Session & Monotonic sequence validation to prevent stale overwrites
    incoming_session_id = data.get("session_id")
    current_session_id = conversation_context.get("session_id")

    # If incoming session is specified and current session is active,
    # reject updates belonging to a different/previous session.
    # For client screen syncs (screen_or_response is str), if an active session exists,
    # reject updates lacking or mismatching the active session.
    if isinstance(screen_or_response, str) and current_session_id:
        if not incoming_session_id or incoming_session_id != current_session_id:
            print(
                f"[track_screen] Stale/mismatched session update ignored: {incoming_session_id} != {current_session_id}"
            )
            return screen_or_response, False
    elif incoming_session_id and current_session_id and incoming_session_id != current_session_id:
        print(
            f"[track_screen] Stale/mismatched session update ignored: {incoming_session_id} != {current_session_id}"
        )
        if isinstance(screen_or_response, KioskResponse):
            return screen_or_response
        return screen_or_response, False

    if incoming_session_id and not current_session_id:
        conversation_context["session_id"] = incoming_session_id

    incoming_seq = data.get("seq")
    if incoming_seq is not None:
        current_seq = conversation_context.get("_screen_seq", 0)
        if incoming_seq <= current_seq:
            print(
                f"[track_screen] Stale screen sync ignored: incoming seq {incoming_seq} <= current {current_seq} (screen: {screen})"
            )
            if isinstance(screen_or_response, KioskResponse):
                return screen_or_response
            return screen_or_response, False
        conversation_context["_screen_seq"] = incoming_seq

    # 2. Update Current Screen & Available Controls
    conversation_context["current_screen"] = screen
    controls = list(get_screen_controls(screen))

    # Track last category screen for smart back navigation
    if screen in [
        ScreenTypes.RECOMMENDED_BURGERS,
        ScreenTypes.FULL_BURGER_MENU,
        ScreenTypes.RECOMMENDED_DRINKS,
        ScreenTypes.FULL_DRINK_MENU,
        ScreenTypes.RECOMMENDED_SIDES,
        ScreenTypes.FULL_SIDE_MENU,
        ScreenTypes.RECOMMENDED_DESSERTS,
        ScreenTypes.FULL_DESSERT_MENU,
    ]:
        conversation_context["last_category_screen"] = screen

    # 3. Authoritative Active Product Selection
    if screen == ScreenTypes.PRODUCT:
        prod = data.get("product")
        if not prod and data.get("meal_offer"):
            mo = data.get("meal_offer")
            if mo.get("product_name") or mo.get("product_id"):
                prod = {"id": mo.get("product_id"), "name": mo.get("product_name")}
        if prod:
            if isinstance(prod, dict):
                p_name = prod.get("name")
                p_id = prod.get("id")
            else:
                p_name = str(prod)
                p_id = conversation_context.get("selected_product_id")
            conversation_context["selected_product"] = p_name
            if p_id is not None:
                conversation_context["selected_product_id"] = p_id
            conversation_context["last_item"] = p_name
        else:
            # Only establish selected_product when current response explicitly identifies the active product.
            # Missing active selection must NOT be inferred or restored from historical memory (last_item).
            conversation_context["selected_product"] = None
            conversation_context["selected_product_id"] = None
    else:
        # Non-product screen: clear active product selection!
        # Do NOT clear last_item: last_item is historical conversational memory!
        conversation_context["selected_product"] = None
        conversation_context["selected_product_id"] = None

    # 4. Meal Offer Synchronization
    if screen == ScreenTypes.PRODUCT:
        meal_offer = data.get("meal_offer")
        declined_ids = [str(x) for x in conversation_context.get("declined_meal_products", [])]
        if meal_offer is not None:
            conversation_context["meal_offer"] = meal_offer
            prod_id = meal_offer.get("product_id")
            if meal_offer.get("is_dismissed"):
                if prod_id is not None:
                    if "declined_meal_products" not in conversation_context:
                        conversation_context["declined_meal_products"] = []
                    if str(prod_id) not in [str(x) for x in conversation_context["declined_meal_products"]]:
                        conversation_context["declined_meal_products"].append(prod_id)
                meal_offer["is_open"] = False
            elif prod_id is not None and str(prod_id) in declined_ids:
                meal_offer["is_open"] = False

            if meal_offer.get("is_open"):
                for mc in ["select_meal", "decline_meal"]:
                    if mc not in controls:
                        controls.append(mc)
            else:
                controls = [c for c in controls if c not in ["select_meal", "decline_meal", "accept_meal"]]
        elif "meal_offer" in conversation_context and conversation_context["meal_offer"]:
            mo = conversation_context["meal_offer"]
            if mo.get("is_open"):
                for mc in ["select_meal", "decline_meal"]:
                    if mc not in controls:
                        controls.append(mc)
            else:
                controls = [c for c in controls if c not in ["select_meal", "decline_meal", "accept_meal"]]
    else:
        conversation_context.pop("meal_offer", None)
        controls = [c for c in controls if c not in ["select_meal", "decline_meal", "accept_meal"]]

    conversation_context["available_controls"] = controls

    print(
        f"[track_screen] Screen: {screen} (seq: {conversation_context.get('_screen_seq')}), "
        f"Active Product: {conversation_context.get('selected_product')}, Controls: {controls}"
    )

    if isinstance(screen_or_response, KioskResponse):
        return screen_or_response
    return screen_or_response, True


# ==========================================
# CREATE UI ACTION RESPONSE
# ==========================================

def create_ui_action(
    control,
    value=None,
    user_input=None,
    llm=None
):

    current_screen = conversation_context.get(
        "current_screen",
        ScreenTypes.CATEGORY_SELECTION
    )

    available_controls = conversation_context.get(
        "available_controls",
        []
    )

    ui_action = control

    # Target screen calculation
    target_screen = current_screen
    if control == "go_back":
        target_screen = ScreenTypes.CATEGORY_SELECTION
    elif control == "open_cart":
        target_screen = ScreenTypes.CART
    elif control == "select_product":
        target_screen = ScreenTypes.PRODUCT
        if value:
            conversation_context["selected_product"] = value
            conversation_context["last_item"] = value

    # ==========================================
    # SEMANTIC FILTER → FRONTEND ACTION
    # ==========================================

    if control == "filter":

        if value == "veg":

            ui_action = "filter_veg"

        elif value == "non_veg":

            ui_action = "filter_non_veg"

        elif value == "both":

            ui_action = "filter_both"

        else:

            print(
                "UNKNOWN FILTER VALUE:",
                value
            )

            return None

    # ==========================================
    # NATURAL CASHIER RESPONSE
    # ==========================================

    message = None

    if user_input and llm:

        message = generate_cashier_response(
            user_input=user_input,
            screen_intent=type(
                "ScreenAction",
                (),
                {
                    "control": control,
                    "value": value
                }
            )(),
            current_screen=current_screen,
            available_controls=available_controls,
            llm=llm
        )

    # ==========================================
    # RETURN UI ACTION + SPOKEN RESPONSE
    # ==========================================

    data = {
        "ui_action": ui_action
    }
    if value is not None:
        data["value"] = value
    if control == "select_product" and value is not None:
        data["product"] = {"name": value}

    reply = KioskResponse(
        screen=target_screen,
        message=message,
        data=data
    )
    track_screen(reply)
    return reply


# ==========================================
# AGENT SCREEN ACTION TOOL
# ==========================================

def create_screen_action_tool(conversation_context):

    @tool
    def screen_action(
        control: str,
        value: str | None = None
    ):
        """
        Perform an action on the current kiosk screen.

        Use this when the customer's request can be fulfilled
        by one of the capabilities available on the current
        screen.

        The control must be one of the current screen's available
        UI capabilities.

        For the filter capability, value must be:
        veg, non_veg, or both.

        This tool operates the kiosk UI. It does not retrieve
        the menu or database contents.

        Args:
            control:
                The UI capability to perform.

            value:
                Optional value required by the capability.

        Returns:
            A small action result for the agent.
            The complete KioskResponse remains inside the
            application for the frontend.
        """

        current_screen = conversation_context.get(
            "current_screen",
            ScreenTypes.CATEGORY_SELECTION
        )

        available_controls = conversation_context.get(
            "available_controls",
            []
        )

        # ==========================================
        # VALIDATE CURRENT SCREEN
        # ==========================================

        if not current_screen:
            err = "No current kiosk screen is available."
            conversation_context["_last_action_rejected"] = {
                "control": control,
                "error": err
            }
            return {
                "success": False,
                "error": err
            }

        # Normalize accept_meal with size to select_meal
        if control == "accept_meal" and value:
            control = "select_meal"

        # ==========================================
        # VALIDATE ADD TO CART
        # ==========================================
        if control == "add_to_cart":
            active_product = conversation_context.get("selected_product")
            if current_screen != ScreenTypes.PRODUCT or not active_product:
                err = (
                    f"Action 'add_to_cart' cannot be performed because current screen is '{current_screen}' "
                    f"and no product is actively selected on screen. The action was NOT executed. "
                    "Do NOT tell the customer an item was added to the cart."
                )
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                    "available_controls": available_controls,
                }

        # ==========================================
        # VALIDATE CONTROL
        # ==========================================

        if control not in available_controls:
            err = (
                f"Control '{control}' is not available on the current screen '{current_screen}'. "
                f"Available controls on this screen: {available_controls}. "
                "The action was NOT executed. Do NOT tell the customer this action was completed or to tap an unavailable button."
            )
            conversation_context["_last_action_rejected"] = {
                "control": control,
                "error": err,
            }
            return {
                "success": False,
                "error": err,
                "available_controls": available_controls
            }

        # ==========================================
        # NORMALIZE FILTER VALUE
        # ==========================================

        if control == "filter":

            if value:

                value = (
                    value
                    .lower()
                    .replace(" ", "_")
                    .strip()
                )

            if value not in [
                "veg",
                "non_veg",
                "both"
            ]:
                err = "Filter value must be veg, non_veg, or both."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err
                }

        # ==========================================
        # VALIDATE MEAL CONTROLS
        # ==========================================

        if control == "select_meal":
            if not value:
                err = "Customer must choose between 'medium' or 'large' meal size."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }

            val_norm = value.lower().replace(" meal", "").strip()
            if val_norm not in ["medium", "large"]:
                err = f"Invalid meal size '{value}'. Must be 'medium' or 'large'."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }
            value = val_norm

            meal_offer = conversation_context.get("meal_offer", {})
            if not meal_offer.get("is_open"):
                err = "The meal offer popup is not currently open."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }

            avail = [s.lower() for s in meal_offer.get("available_sizes", [])]
            if avail and value not in avail:
                err = f"Size '{value}' is not available. Available sizes: {', '.join(avail)}."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                    "available_sizes": avail,
                }

        if control == "decline_meal":
            meal_offer = conversation_context.get("meal_offer", {})
            meal_flow = conversation_context.get("meal_flow")
            prod_id = value or meal_offer.get("product_id") or (meal_flow.get("item_id") if meal_flow else None)
            if prod_id is not None:
                if "declined_meal_products" not in conversation_context:
                    conversation_context["declined_meal_products"] = []
                if str(prod_id) not in [str(x) for x in conversation_context["declined_meal_products"]]:
                    conversation_context["declined_meal_products"].append(prod_id)
            if meal_offer and (prod_id is None or meal_offer.get("product_id") is None or str(meal_offer.get("product_id")) == str(prod_id)):
                meal_offer["is_open"] = False
                if "available_controls" in conversation_context:
                    conversation_context["available_controls"] = [
                        c for c in conversation_context["available_controls"]
                        if c not in ["select_meal", "decline_meal", "accept_meal"]
                    ]
            if meal_flow and (prod_id is None or meal_flow.get("item_id") is None or str(meal_flow.get("item_id")) == str(prod_id)):
                meal_flow["status"] = "declined"

        # ==========================================
        # EXECUTE EXISTING UI BRIDGE
        # ==========================================

        response = create_ui_action(
            control,
            value
        )

        if response is None:
            err = "The kiosk could not perform this action."
            conversation_context["_last_action_rejected"] = {
                "control": control,
                "error": err,
            }
            return {
                "success": False,
                "error": err
            }

        # Clear rejected flag on successful execution
        conversation_context["_last_action_rejected"] = None

        # ==========================================
        # KEEP FULL RESPONSE INSIDE APPLICATION
        # ==========================================

        conversation_context[
            "_last_kiosk_response"
        ] = response

        # ==========================================
        # RETURN ONLY AGENT-RELEVANT INFORMATION
        # ==========================================

        return {
            "success": True,
            "screen": response.screen,
            "control": control,
            "value": value
        }

    return screen_action


# ==========================================
# MAIN MESSAGE PROCESSOR
# ==========================================

def process_message(user_input, llm):

    # ==========================================
    # 1. CHECKOUT PAYMENT FLOW
    # ==========================================

    if conversation_context.get(
        "checkout_pending",
        False
    ):

        lower = user_input.lower()

        if "cash" in lower or "card" in lower:

            from repositories.order_repository import complete_order

            result = complete_order(
                conversation_context["cart"]
            )

            if not result["success"]:

                conversation_context[
                    "checkout_pending"
                ] = False

                return result["message"]

            conversation_context["cart"] = []

            conversation_context[
                "checkout_pending"
            ] = False

            if "cash" in lower:

                reply = KioskResponse(
                    screen=ScreenTypes.ORDER_COMPLETE,
                    message=(
                        "Your order has been placed successfully. "
                        "Please pay at the counter. Thank you!"
                    )
                )

                return track_screen(reply)

            reply = KioskResponse(
                screen=ScreenTypes.PAYMENT,
                message=(
                    "Your order has been placed successfully. "
                    "Please proceed with card payment. Thank you!"
                )
            )

            return track_screen(reply)


    # ==========================================
    # 2. PENDING BURGER CLARIFICATION
    # ==========================================

    if conversation_context.get(
        "pending_clarification"
    ) == "burger_type":

        decision = resolve_burger_clarification(
            user_input,
            llm
        )

        print(
            "Clarification Decision:",
            decision
        )


        # --------------------------------------
        # VEG
        # --------------------------------------

        if (
            decision.action == "clarification_answer"
            and decision.value == "veg"
        ):

            conversation_context[
                "burger_type"
            ] = "veg"

            conversation_context[
                "pending_clarification"
            ] = None

            reply = create_ui_action(
                "filter",
                "veg"
            )

            if reply:

                return track_screen(reply)


        # --------------------------------------
        # NON VEG
        # --------------------------------------

        elif (
            decision.action == "clarification_answer"
            and decision.value == "non veg"
        ):

            conversation_context[
                "burger_type"
            ] = "non veg"

            conversation_context[
                "pending_clarification"
            ] = None

            reply = create_ui_action(
                "filter",
                "non_veg"
            )

            if reply:

                return track_screen(reply)


        # --------------------------------------
        # BOTH
        # --------------------------------------

        elif (
            decision.action == "clarification_answer"
            and decision.value == "both"
        ):

            conversation_context[
                "pending_clarification"
            ] = None

            reply = create_ui_action(
                "filter",
                "both"
            )

            if reply:

                return track_screen(reply)


        # --------------------------------------
        # NEW INTENT
        # --------------------------------------

        elif decision.action == "new_intent":

            conversation_context[
                "pending_clarification"
            ] = None


        # --------------------------------------
        # UNCLEAR
        # --------------------------------------

        elif decision.action == "unclear":

            reply = KioskResponse(
                screen=conversation_context.get(
                    "current_screen",
                    ScreenTypes.BURGER_TYPE_SELECTION
                ),
                message=(
                    "Please choose veg, non veg, or both."
                )
            )

            return track_screen(reply)


    # ==========================================
    # 3. SCREEN-SPECIFIC UNDERSTANDING
    # ==========================================

    current_screen = conversation_context.get(
        "current_screen"
    )

    available_controls = conversation_context.get(
        "available_controls",
        []
    )


    if current_screen and available_controls:

        screen_intent = extract_screen_intent(
            user_input,
            current_screen,
            available_controls,
            llm
        )

        print(
            "Screen Intent Result:",
            screen_intent
        )


        # ======================================
        # CURRENT SCREEN CAN HANDLE REQUEST
        # ======================================

        if screen_intent.action == "screen_action":

            print(
                "Screen Control:",
                screen_intent.control
            )

            print(
                "Screen Value:",
                screen_intent.value
            )


            # ----------------------------------
            # IMPORTANT
            # ----------------------------------
            #
            # We DO NOT:
            #
            # - query the database
            # - fetch the menu
            # - call recommendation logic
            # - call handle_burger_selection()
            #
            # The recommendation data already exists
            # in the frontend.
            #
            # We simply tell the frontend:
            #
            # "Perform this UI action."
            # ----------------------------------

            reply = create_ui_action(
                screen_intent.control,
                screen_intent.value,
                user_input,
                llm
            )


            if reply:

                return track_screen(reply)


    # ==========================================
    # 4. GLOBAL INTENT EXTRACTION
    # ==========================================

    intent = extract_intent(
        user_input,
        llm,
        conversation_context
    )

    print(
        "Intent Result:",
        intent
    )


    # ==========================================
    # 5. GLOBAL INTENT ROUTING
    # ==========================================

    if (
        intent.action == "show_category"
        and not intent.category
    ):

        reply = KioskResponse(
            screen=ScreenTypes.HOME,
            message=(
                "Which category would you like — "
                "burgers, beverages, desserts, or sides?"
            )
        )


    elif intent.action == "unknown":

        reply = (
            "Could you tell me a little more "
            "about what you'd like?"
        )


    elif intent.action == "expand_context":

        reply = handle_more_options()


    elif intent.action == "decline_offer":

        reply = handle_decline(
            conversation_context,
            llm
        )


    elif intent.action == "show_priority_menu":

        reply = handle_menu(
            user_input,
            conversation_context,
            llm
        )


    elif intent.action == "show_full_menu":

        reply = handle_full_menu(
            conversation_context
        )


    elif intent.action == "show_category":

        reply = handle_category(
            intent.category,
            conversation_context
        )


    elif intent.action == "correct_item":

        reply = handle_correction(
            intent.item_name,
            conversation_context
        )


    elif intent.action == "add_item":

        print("=" * 50)

        print(
            "Conversation:",
            conversation_context
        )

        print(
            "Intent:",
            intent
        )

        print(
            "Last Category:",
            conversation_context.get(
                "last_category"
            )
        )

        print("=" * 50)


        # --------------------------------------
        # Customer is browsing
        # → open product details
        # --------------------------------------

        if conversation_context.get(
            "last_category"
        ):

            print(
                "Opening Product Details"
            )

            reply = handle_product(
                intent.item_name,
                conversation_context
            )


        # --------------------------------------
        # Customer directly ordered an item
        # --------------------------------------

        else:

            print(
                "Going to Handle Order"
            )

            reply = handle_order(
                intent.item_name,
                intent.quantity,
                intent.category,
                conversation_context,
                llm
            )


    elif intent.action == "remove_item":

        reply = handle_remove(
            intent.item_name,
            conversation_context
        )


    elif intent.action == "checkout":

        reply = handle_checkout(
            conversation_context,
            llm
        )


    else:

        reply = (
            "I'm sorry, I didn't understand that."
        )


    # ==========================================
    # 6. SAVE NEW SCREEN
    # ==========================================

    print(
        "FINAL BACKEND RESPONSE:",
        reply
    )

    return track_screen(reply)