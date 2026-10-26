from pydantic import BaseModel
from typing import Literal, Optional


# ==========================================
# SCREEN INTENT
# ==========================================

class ScreenIntent(BaseModel):

    action: Literal[
        "screen_action",
        "global_intent"
    ]

    control: Optional[str] = None

    value: Optional[str] = None


# ==========================================
# SCREEN CAPABILITY DESCRIPTIONS
# ==========================================

SCREEN_CAPABILITIES = {

    "filter": (
        "Change which products are currently displayed "
        "according to the customer's food preference. "
        "The value must describe the requested preference."
    ),

    "select_product": (
        "Select a product that is currently visible "
        "on the screen."
    ),

    "view_more": (
        "Show additional products or open the complete "
        "menu for the current category."
    ),

    "open_cart": (
        "Open and display the customer's current cart."
    ),

    "go_back": (
        "Return to the previous screen."
    ),

    "add_to_cart": (
        "Add the currently selected product to the cart. "
        "Value can optionally specify the requested quantity to add (e.g. '3'). "
        "If omitted, adds the current on-screen quantity."
    ),

    "upgrade_to_meal": (
        "Open meal conversion options for the currently selected product on the product screen. "
        "Triggers the 'Upgrade to a Meal' button action."
    ),

    "accept_meal": (
        "Accept the meal conversion or meal suggestion "
        "currently being offered."
    ),

    "decline_meal": (
        "Decline the meal conversion or meal suggestion "
        "currently being offered."
    ),

    "set_quantity": (
        "Set the quantity of the currently selected product on the product screen "
        "or an item on the screen. The value must be the target quantity number."
    ),

    "increase_quantity": (
        "Increase the quantity of an item currently being managed on the screen. "
        "On the product page, increments the quantity selector (e.g. by 1 for 'add one more')."
    ),

    "decrease_quantity": (
        "Decrease the quantity of an item currently being managed on the screen. "
        "On the product page, decrements the quantity selector."
    ),

    "remove_item": (
        "Remove an item from the cart."
    ),

    "checkout": (
        "Direct the customer to the payment options (UPI, card, cash) on the cart screen."
    ),

    "swap_meal_item": (
        "Swap or upgrade the side or drink component of the meal "
        "currently being customized on the meal builder screen. "
        "Value is the requested item name."
    ),

    "add_recommended": (
        "Add a complementary recommendation displayed on the cart screen "
        "shelf to the cart. Value is the recommended item name."
    ),

    "select_payment": (
        "Select the customer's desired payment method on the cart screen. "
        "Value must be one of: upi, card, or cash."
    ),

    "confirm_order": (
        "Place and confirm the order after reviewing the cart and selecting "
        "a payment method."
    ),
}


# ==========================================
# PARSE LLM RESPONSE
# ==========================================

def parse_screen_intent(raw_response):

    if not raw_response:
        return ScreenIntent(
            action="global_intent"
        )

    text = raw_response.strip()

    action = None
    control = None
    value = None

    # ==========================================
    # READ EACH LINE
    # ==========================================

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        if "=" not in line:
            continue

        key, val = line.split("=", 1)

        key = key.strip().lower()
        val = val.strip()

        if val.lower() in [
            "none",
            "null",
            ""
        ]:
            val = None

        if key == "action":
            action = val.lower() if val else None

        elif key == "control":
            control = val.lower() if val else None

        elif key == "value":
            value = val.lower() if val else None

    # ==========================================
    # SAFETY
    # ==========================================

    if action not in [
        "screen_action",
        "global_intent"
    ]:
        return ScreenIntent(
            action="global_intent"
        )

    # ==========================================
    # GLOBAL INTENT
    # ==========================================

    if action == "global_intent":
        return ScreenIntent(
            action="global_intent",
            control=None,
            value=None
        )

    # ==========================================
    # SCREEN ACTION
    # ==========================================

    return ScreenIntent(
        action="screen_action",
        control=control,
        value=value
    )


# ==========================================
# SCREEN INTENT EXTRACTION
# ==========================================

def extract_screen_intent(
    user_input,
    current_screen,
    available_controls,
    llm
):

    capability_descriptions = {}

    for control in available_controls:

        capability_descriptions[control] = (
            SCREEN_CAPABILITIES.get(
                control,
                "Perform this action on the current screen."
            )
        )

    prompt = f"""
You are the screen-level understanding system
for an intelligent restaurant kiosk.

Your job is to determine whether the customer's
request can be performed by the capabilities
available on the current screen.

CURRENT SCREEN:
{current_screen}

AVAILABLE SCREEN CAPABILITIES:
{capability_descriptions}

CUSTOMER MESSAGE:
{user_input}


UNDERSTANDING RULES

Understand the customer's meaning naturally.

Do not require exact command words.

Do not rely on keyword matching.

Use the meaning of the customer's request,
the current screen, and the capability descriptions
to determine whether a screen action is appropriate.

If the request can be performed using one of the
AVAILABLE SCREEN CAPABILITIES:

ACTION=screen_action

and select the appropriate:

CONTROL=<capability>

If the request cannot be performed by any available
screen capability:

ACTION=global_intent

CONTROL=None
VALUE=None


VALUE RULE

Only provide a value when the selected capability
requires one.

For the "filter" capability, normalize the customer's
food preference to one of:

veg
non_veg
both

For capabilities that do not require a value:

VALUE=None


IMPORTANT

Only select a control that exists in:

{available_controls}

Never invent a control.

Do not force a request into a screen action simply
because the request is related to the current screen.

A request for a product, category, recommendation,
or other operation that the current screen cannot
perform should be classified as:

ACTION=global_intent


Return EXACTLY these three lines:

ACTION=<screen_action or global_intent>
CONTROL=<control or None>
VALUE=<value or None>

Do not write anything else.
"""

    # ==========================================
    # NORMAL LLM CALL
    # ==========================================

    try:

        response = llm.invoke(prompt)

        raw_response = response.content

        print(
            "RAW SCREEN LLM RESPONSE:",
            raw_response
        )

        result = parse_screen_intent(
            raw_response
        )

        # ======================================
        # VALIDATE CONTROL
        # ======================================

        if result.action == "screen_action":

            if result.control not in available_controls:

                print(
                    "INVALID SCREEN CONTROL:",
                    result.control
                )

                return ScreenIntent(
                    action="global_intent"
                )

        print(
            "Screen Intent Result:",
            result
        )

        return result

    except Exception as e:

        print(
            "SCREEN INTENT ERROR:",
            e
        )

        # ======================================
        # FAIL SAFE
        # ======================================

        return ScreenIntent(
            action="global_intent"
        )