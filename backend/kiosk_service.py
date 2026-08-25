from conversation import (
    handle_correction,
    handle_decline,
    handle_checkout
)

from intent import extract_intent
from state import conversation_context

from services.cart_service import complete_order
from services.recommendation import handle_recommendation

from services.menuservice import (
    handle_menu,
    handle_category,
    handle_more_options,
    handle_full_menu,
    handle_burger_selection
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

def process_message(user_input, llm):

    if conversation_context.get("checkout_pending", False):

        lower = user_input.lower()

        if "cash" in lower or "card" in lower:

         from repositories.order_repository import complete_order

         result = complete_order(
            conversation_context["cart"]
         )

        if not result["success"]:
            conversation_context["checkout_pending"] = False

            return result["message"]

        conversation_context["cart"] = []
        conversation_context["checkout_pending"] = False

        if "cash" in lower:
            return KioskResponse(
                screen=ScreenTypes.ORDER_COMPLETE,
                message=(
                    "Your order has been placed successfully. "
                    "Please pay at the counter. Thank you!"
                )
            )

        return KioskResponse(
            screen=ScreenTypes.PAYMENT,
            message=(
                "Your order has been placed successfully. "
                "Please proceed with card payment. Thank you!"
            )
        )
    if conversation_context.get("pending_clarification") == "burger_type":

        decision = resolve_burger_clarification(
            user_input,
            llm
        )

        if (decision.action== "clarification_answer"and decision.value == "veg"):

            conversation_context["burger_type"] = "veg"
            conversation_context["pending_clarification"] = None

            return handle_burger_selection(
                "veg",
                conversation_context
            )

        elif (decision.action == "clarification_answer"and decision.value == "non veg"):

            conversation_context["burger_type"] = "non veg"
            conversation_context["pending_clarification"] = None

            return handle_burger_selection(
                "non veg",
                conversation_context
            )

        elif (decision.action == "clarification_answer"and decision.value == "both"):

            conversation_context["pending_clarification"] = None

            veg_reply = handle_burger_selection(
                "veg",
                conversation_context
            )

            nonveg_reply = handle_burger_selection(
                "non veg",
                conversation_context
            )

            return (
                veg_reply
                + "\n\n"
                + nonveg_reply
            )

        elif (decision.action == "new_intent"):

            conversation_context["pending_clarification"] = None

        elif decision.action == "unclear":

         return KioskResponse(
           screen=ScreenTypes.BURGER_TYPE_SELECTION,
           message="Please choose veg, non veg, or both."
         )
        print(decision)

    # ==========================
    # INTENT EXTRACTION
    # ==========================

    intent = extract_intent(
        user_input,
        llm,
        conversation_context
    )

    print("Intent Result:", intent)

    # ==========================
    # ROUTING
    # ==========================

    if (
     intent.action == "show_category"
     and not intent.category
     ):
     return KioskResponse(
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
     print("Conversation:", conversation_context)
     print("Intent:", intent)
     print("Last Category:", conversation_context.get("last_category"))
     print("=" * 50)
    # If customer is browsing, open product page
     if conversation_context.get("last_category"):
        print("Opening Product Details")
        reply = handle_product(
            intent.item_name,
            conversation_context
        )

    # Otherwise customer is ordering directly
     else:
        print("Going to Handle Order")

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

    return reply