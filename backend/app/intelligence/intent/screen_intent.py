"""
app/intelligence/intent/screen_intent.py

Screen-level intent extraction for TheAtom.

Determines whether a user utterance maps to a UI control action on the
current screen, or should bubble up as a global intent.  Uses STRUCTURED
output — no free-text parsing.

No LangChain imports.  No global state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Screen capabilities registry
# ---------------------------------------------------------------------------

#: Maps control identifiers to human-readable descriptions.
#: This is the single authoritative list of what controls exist per screen
#: type.  Downstream code should read from this dict rather than hard-coding
#: control names.
SCREEN_CAPABILITIES: dict[str, dict[str, str]] = {
    "main_menu": {
        "btn_burgers": "View the Burgers category",
        "btn_sides": "View the Sides & Fries category",
        "btn_drinks": "View the Drinks & Beverages category",
        "btn_desserts": "View the Desserts category",
        "btn_value_meals": "View Value Meals / Combos",
        "btn_view_cart": "Open the cart / basket",
        "btn_checkout": "Proceed to checkout",
        "btn_promotions": "View current promotions and offers",
    },
    "item_detail": {
        "btn_add_to_cart": "Add the currently displayed item to the cart",
        "btn_customise": "Open item customisation / modifications panel",
        "btn_back": "Go back to the previous screen",
        "btn_make_it_a_meal": "Upgrade item to a meal combo",
        "btn_size_small": "Select small size",
        "btn_size_medium": "Select medium size",
        "btn_size_large": "Select large size",
    },
    "cart": {
        "btn_remove_item": "Remove the selected item from cart",
        "btn_increase_qty": "Increase item quantity by 1",
        "btn_decrease_qty": "Decrease item quantity by 1",
        "btn_checkout": "Proceed to checkout",
        "btn_clear_cart": "Remove all items from the cart",
        "btn_back": "Continue shopping / go back",
    },
    "checkout": {
        "btn_confirm_order": "Confirm and submit the order",
        "btn_cancel": "Cancel checkout and return to cart",
        "btn_edit_order": "Go back to cart to edit the order",
    },
    "category": {
        "btn_back": "Go back to main menu",
        "btn_filter_veg": "Filter to vegetarian items only",
        "btn_filter_nonveg": "Show all (remove vegetarian filter)",
        "btn_sort_price_asc": "Sort items by price low to high",
        "btn_sort_price_desc": "Sort items by price high to low",
        "btn_view_cart": "Open the cart",
    },
}


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class ScreenIntent(BaseModel):
    """
    Structured representation of a screen-level intent.

    Attributes:
        action:    Either a screen-specific control action or escalation to
                   global intent handling.
        control:   The UI control identifier to activate (e.g. ``"btn_checkout"``).
        value:     Optional value associated with the control (e.g. item ID).
        reasoning: Brief explanation for observability.
    """

    action: Literal["screen_action", "global_intent"]
    control: str | None = Field(
        default=None,
        description="UI control identifier from SCREEN_CAPABILITIES.",
    )
    value: str | None = Field(
        default=None,
        description="Optional value for the control (e.g. item size, item id).",
    )
    reasoning: str = Field(
        description="Brief explanation of why this screen action was chosen.",
    )

    @model_validator(mode="after")
    def _validate_control_present_for_screen_action(self) -> "ScreenIntent":
        if self.action == "screen_action" and not self.control:
            raise ValueError(
                "control must be set when action is ''screen_action''"
            )
        return self


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


async def extract_screen_intent(
    user_input: str,
    screen: str,
    available_controls: list[str],
    llm_port: Any,
    prompt_registry: Any,
) -> ScreenIntent:
    """
    Determine whether *user_input* maps to a UI control on *screen*.

    Decision flow:
    1. If there are no available controls, immediately return ``global_intent``.
    2. Build a prompt that describes the controls.
    3. Call the LLM for structured output.
    4. Validate the returned control is in *available_controls*.
    5. If the control is invalid, downgrade to ``global_intent``.

    Args:
        user_input:         Raw utterance from the user.
        screen:             Current screen identifier (key in SCREEN_CAPABILITIES).
        available_controls: List of control IDs currently visible/enabled.
        llm_port:           Concrete LanguageModelPort (injected).
        prompt_registry:    Prompt template registry.

    Returns:
        :class:`ScreenIntent`
    """
    log = logger.bind(screen=screen, user_input=user_input[:120])

    # Gate: skip LLM call if no controls available
    if not available_controls:
        log.debug("screen_intent.no_controls_skip_llm")
        return ScreenIntent(
            action="global_intent",
            control=None,
            value=None,
            reasoning="No screen controls available; escalating to global intent.",
        )

    # Build description of available controls
    screen_caps = SCREEN_CAPABILITIES.get(screen, {})
    control_descriptions = {
        ctrl: screen_caps.get(ctrl, ctrl)
        for ctrl in available_controls
        if ctrl in screen_caps
    }

    prompt = prompt_registry.render(
        key="intent/screen_intent_v1",
        variables={
            "user_input": user_input,
            "screen": screen,
            "controls": "\n".join(
                f"  {k}: {v}" for k, v in control_descriptions.items()
            ),
        },
    )

    log.debug("screen_intent.calling_llm", prompt_key="intent/screen_intent_v1")

    intent: ScreenIntent = await llm_port.structured_complete(
        prompt=prompt,
        response_model=ScreenIntent,
    )

    # Validate the returned control against what is actually available
    if (
        intent.action == "screen_action"
        and intent.control not in available_controls
    ):
        log.warning(
            "screen_intent.invalid_control_downgrade",
            returned_control=intent.control,
            available=available_controls,
        )
        return ScreenIntent(
            action="global_intent",
            control=None,
            value=None,
            reasoning=(
                f"LLM returned control ''{intent.control}'' which is not "
                f"available on screen ''{screen}''; escalating to global intent."
            ),
        )

    log.info(
        "screen_intent.extracted",
        action=intent.action,
        control=intent.control,
        value=intent.value,
        reasoning=intent.reasoning,
    )

    return intent
