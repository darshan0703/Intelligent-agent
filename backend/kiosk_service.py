from conversation import (
    handle_correction,
    handle_decline,
    handle_checkout
)

from intent import extract_intent
from screen_intent import extract_screen_intent
from state import conversation_context

from services.recommendation import handle_recommendation

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
# ==========================================
# SCREEN TRACKING
# ==========================================

def track_screen(response):

    if isinstance(response, KioskResponse):

        conversation_context["current_screen"] = response.screen

        conversation_context["available_controls"] = (
            get_screen_controls(response.screen)
        )

        print(
            "Current Screen:",
            response.screen
        )

        print(
            "Available Controls:",
            conversation_context["available_controls"]
        )

    return response


# ==========================================
# CREATE UI ACTION RESPONSE
# ==========================================

def create_ui_action(control, value=None):

    current_screen = conversation_context.get(
        "current_screen"
    )

    ui_action = control


    # ==========================================
    # SEMANTIC FILTER
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
    # CREATE FRONTEND UI ACTION
    # ==========================================

    return KioskResponse(
        screen=current_screen,
        data={
            "ui_action": ui_action
        }
    )


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


    elif intent.action == "recommend":

        reply = handle_recommendation(
            user_input,
            conversation_context,
            llm
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
    print("FINAL BACKEND RESPONSE:", reply)

    return track_screen(reply)

def create_ui_action(
    control,
    value=None,
    user_input=None,
    llm=None
):

    current_screen = conversation_context.get(
        "current_screen"
    )

    available_controls = conversation_context.get(
        "available_controls",
        []
    )

    ui_action = control

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

    return KioskResponse(
        screen=current_screen,
        message=message,
        data={
            "ui_action": ui_action
        }
    )