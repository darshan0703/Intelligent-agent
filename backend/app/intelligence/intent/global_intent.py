"""
app/intelligence/intent/global_intent.py

Global intent extraction for TheAtom.

Uses STRUCTURED output via the LanguageModelPort protocol — zero string
parsing.  The LLM returns a validated Pydantic model directly; if the model
fails validation the call raises and is handled by the caller.

No LangChain imports.  No global state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from app.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class GlobalIntent(BaseModel):
    """
    Structured representation of the user''s global intent.

    Attributes:
        action:     High-level action the user wants to perform.
        item_name:  Specific item name when action involves a menu item.
        category:   Menu category referenced (e.g. ``"Burgers"``).
        quantity:   Number of items; defaults to 1.
        preference: Dietary or taste preference expressed (e.g. ``"vegetarian"``).
        reasoning:  Brief LLM explanation — for observability only, not shown to user.
    """

    action: Literal[
        "show_category",
        "add_item",
        "recommend",
        "remove_item",
        "expand_context",
        "decline_offer",
        "checkout",
        "correct_item",
        "greeting",
        "exit",
        "unknown",
    ]
    item_name: str | None = Field(
        default=None,
        description="Canonical menu item name if the user mentions one.",
    )
    category: str | None = Field(
        default=None,
        description="Menu category name if the user mentions a category.",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="How many units of the item the user wants.",
    )
    preference: str | None = Field(
        default=None,
        description="Dietary or taste preference expressed by the user.",
    )
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen.",
    )


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


async def extract_global_intent(
    user_input: str,
    session_state: Any,
    llm_port: Any,
    prompt_registry: Any,
) -> GlobalIntent:
    """
    Extract the global intent from *user_input* using structured LLM output.

    Args:
        user_input:      Raw utterance from the user.
        session_state:   Current session context (cart, conversation history,
                         food preference, etc.) — used to build the prompt.
        llm_port:        Concrete implementation of ``LanguageModelPort``
                         (injected; never imported directly).
        prompt_registry: Provides rendered prompt strings by key.

    Returns:
        :class:`GlobalIntent` — always a valid structured object.

    Raises:
        ValidationError: If the LLM returns a response that cannot be
                         coerced into :class:`GlobalIntent`.
        LLMError:        If the underlying LLM call fails (propagated).
    """
    log = logger.bind(user_input=user_input[:120])

    # Build prompt from registry — keeps prompts versioned and testable
    prompt = prompt_registry.render(
        key="intent/global_intent_v1",
        variables={
            "user_input": user_input,
            "cart_summary": _summarise_cart(session_state),
            "conversation_history": _last_n_turns(session_state, n=4),
            "food_preference": getattr(session_state, "food_preference", "any"),
            "current_category": getattr(session_state, "current_category", None),
        },
    )

    log.debug("global_intent.calling_llm", prompt_key="intent/global_intent_v1")

    intent: GlobalIntent = await llm_port.structured_complete(
        prompt=prompt,
        response_model=GlobalIntent,
    )

    log.info(
        "global_intent.extracted",
        action=intent.action,
        item_name=intent.item_name,
        category=intent.category,
        quantity=intent.quantity,
        reasoning=intent.reasoning,
    )

    return intent


# ---------------------------------------------------------------------------
# Private helpers — keep session serialisation local to this module
# ---------------------------------------------------------------------------


def _summarise_cart(session_state: Any) -> str:
    """Return a compact text description of the current cart."""
    try:
        items = session_state.cart.items  # list of CartItem
        if not items:
            return "Cart is empty."
        lines = [f"- {ci.quantity}x {ci.item.name}" for ci in items]
        return "\n".join(lines)
    except AttributeError:
        return "Cart is empty."


def _last_n_turns(session_state: Any, n: int = 4) -> str:
    """Return the last *n* conversation turns as plain text."""
    try:
        history = session_state.conversation_history[-n:]
        lines: list[str] = []
        for turn in history:
            role = getattr(turn, "role", "user")
            content = getattr(turn, "content", str(turn))
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines) if lines else "No prior conversation."
    except (AttributeError, TypeError):
        return "No prior conversation."
