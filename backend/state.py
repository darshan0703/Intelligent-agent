conversation_context = {}


def reset_conversation(session_id=None):
    conversation_context.clear()

    conversation_context.update({
        "session_id": session_id,

        # Navigation
        "last_category": None,

        # Cart
        "cart": [],
        "last_item": None,

        # Offers & Recommendations
        "last_offer": None,
        "pending_suggestion": None,
        "pending_clarification": None,

        # Burger Flow
        "burger_type": None,

        # Checkout
        "checkout_pending": False,
    })