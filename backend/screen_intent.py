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
        "Change the currently displayed items based on "
        "a customer's preference such as vegetarian, "
        "non-vegetarian, or all."
    ),

    "select_product": (
        "Select a product that is currently displayed "
        "on the screen."
    ),

    "view_more": (
        "Open the complete menu for the current category."
    ),

    "open_cart": (
        "Open and display the customer's current cart."
    ),

    "go_back": (
        "Return to the previous screen."
    ),

    "add_to_cart": (
        "Add the currently selected product to the cart."
    ),

    "accept_meal": (
        "Accept the meal conversion or meal suggestion."
    ),

    "decline_meal": (
        "Decline the meal conversion or meal suggestion."
    ),

    "increase_quantity": (
        "Increase the quantity of an item in the cart."
    ),

    "decrease_quantity": (
        "Decrease the quantity of an item in the cart."
    ),

    "remove_item": (
        "Remove an item from the cart."
    ),

    "checkout": (
        "Proceed from the cart to checkout."
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


        key, val = line.split(
            "=",
            1
        )

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

        description = SCREEN_CAPABILITIES.get(
            control,
            "Perform this action on the current screen."
        )

        capability_descriptions[
            control
        ] = description


    prompt = f"""
You are the screen-level understanding system
for an intelligent restaurant kiosk.

The customer is currently looking at:

CURRENT SCREEN:
{current_screen}

The current screen can perform these actions:

{capability_descriptions}

CUSTOMER MESSAGE:
{user_input}


YOUR JOB

Understand what the customer means in the context
of the current screen.

The customer will speak naturally.

Do NOT require exact command words.

If the customer's request can be performed by
one of the CURRENT SCREEN CAPABILITIES, classify it
as a screen_action.

If it cannot be performed by the current screen,
classify it as a global_intent.


------------------------------------------
FILTER
------------------------------------------

If the current screen has the capability:

filter

Then understand the customer's preference.

Examples:

"Show me vegetarian burgers"

ACTION=screen_action
CONTROL=filter
VALUE=veg

"Can I see non vegetarian options?"

ACTION=screen_action
CONTROL=filter
VALUE=non_veg

"Show me everything"

ACTION=screen_action
CONTROL=filter
VALUE=both


------------------------------------------
GO BACK
------------------------------------------

If the current screen has:

go_back

Then:

"Go back"

ACTION=screen_action
CONTROL=go_back
VALUE=None

"Take me to the previous screen"

ACTION=screen_action
CONTROL=go_back
VALUE=None

"Can I go back?"

ACTION=screen_action
CONTROL=go_back
VALUE=None


------------------------------------------
VIEW MORE
------------------------------------------

If the current screen has:

view_more

Then:

"Show me more options"

ACTION=screen_action
CONTROL=view_more
VALUE=None

"I want to see all the burgers"

ACTION=screen_action
CONTROL=view_more
VALUE=None


------------------------------------------
OPEN CART
------------------------------------------

If the current screen has:

open_cart

Then:

"Show my cart"

ACTION=screen_action
CONTROL=open_cart
VALUE=None


------------------------------------------
GLOBAL REQUESTS
------------------------------------------

If the current screen cannot perform the
requested operation, use global_intent.

Examples:

"I want desserts"

ACTION=global_intent
CONTROL=None
VALUE=None

"Can I get a drink?"

ACTION=global_intent
CONTROL=None
VALUE=None

"I want a chicken burger"

ACTION=global_intent
CONTROL=None
VALUE=None


------------------------------------------
IMPORTANT
------------------------------------------

Only choose a control that exists in:

{available_controls}

Do not invent controls.

Do not force a request into a screen action
if the current screen cannot perform it.

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

        # --------------------------------------
        # IMPORTANT:
        #
        # An unintelligible screen request should
        # NOT crash the kiosk.
        #
        # Let global intent handle it.
        # --------------------------------------

        return ScreenIntent(
            action="global_intent"
        )