conversation_context = {}


def create_conversation_state(session_id=None):
    return {
        "session_id": session_id,

        # Authoritative UI State
        "current_screen": "category_selection",
        "available_controls": ["open_cart"],
        "selected_product": None,
        "selected_product_id": None,
        "_screen_seq": 0,
        "displayed_products": [],
        "_last_action_rejected": None,

        # Navigation
        "last_category": None,
        "last_category_screen": None,

        # Cart
        "cart": [],
        "last_item": None,  # Historical conversational memory of previously discussed product

        # Offers & Recommendations
        "last_offer": None,
        "pending_suggestion": None,
        "pending_clarification": None,

        # Customer Preferences
        "food_preference": None,

        # Checkout
        "checkout_pending": False,
        "meal_flow": None,
        "meal_offer": None,
        "declined_meal_products": [],

        # Multi-Item Pending Intent & Idempotency Store
        "pending_items": [],
        "processed_idempotency_keys": {},
        "explicit_meal_intent": None,
        "current_user_message": None,

        # Agent conversation
        "conversation_history": [],
    }


def reset_conversation(session_id=None):
    conversation_context.clear()
    conversation_context.update(
        create_conversation_state(session_id)
    )