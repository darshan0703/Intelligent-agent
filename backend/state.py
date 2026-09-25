conversation_context = {}


def create_conversation_state(session_id=None):
    return {
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

        # Customer Preferences
        "food_preference": None,

        # Checkout
        "checkout_pending": False,
        "meal_flow": None,

        # Agent conversation
        "conversation_history": [],
    }


def reset_conversation(session_id=None):
    conversation_context.clear()
    conversation_context.update(
        create_conversation_state(session_id)
    )