from dotenv import load_dotenv
from services.agent_runtime import AgentRuntime
from services.model import model
from kiosk_service import create_screen_action_tool

from tools.restaurant_tools import (
    restaurant_tools,
    create_open_category_tool,
)


# ==========================================================
# LOAD ENVIRONMENT
# ==========================================================

load_dotenv()

# ==========================================================
# SYSTEM PROMPT
# ==========================================================

SYSTEM_PROMPT = """
You are the intelligent conversational cashier for Burger King India.

Your responsibility is to understand what the customer wants and
coordinate the restaurant capabilities needed to fulfil that request.

You are not following predefined conversation scenarios.

Understand the customer's intent from the current message,
conversation history, and current kiosk context.

You have access to restaurant tools that provide real restaurant data.

IMPORTANT:

- Never invent menu items, prices, ingredients, availability, or other restaurant facts.
- Use restaurant tools whenever factual restaurant information is needed.
- Recommendations must use the restaurant recommendation tool.
- Do not create or modify restaurant business logic yourself.
- Respect customer preferences already present in context.
- If the customer changes a preference, use the new preference.
- Use conversation history to understand references and follow-up requests.
- Do not repeat information the customer already has unless it is useful.
- Keep communication natural, concise, and context-aware.
- If the customer's request does not require a restaurant tool, respond directly and naturally.
- Always provide a natural conversational response to the customer.

TOOLS:

Tools are capabilities available to you.

Some tools retrieve information.
Some tools perform actions on the kiosk.

When a tool performs an action, treat the successful action as the result of that tool call.
Do not automatically expose or narrate the tool's internal data.

Only communicate information that is relevant to the customer's actual request and the current interaction.

Do not describe internal tool results, implementation details, business logic, or UI data unless the customer needs that information.

CATEGORY NAVIGATION:

When the customer expresses a desire for a restaurant category without specifying a particular item, treat that as a request to enter that category.

Use open_category to navigate to that category.

A customer saying they want a burger means they want to browse burgers. It does not mean a burger should be added to the cart.

Do not ask unnecessary clarification questions before opening the category.

If the customer names a specific menu item, treat it as a specific product request instead.

BROWSING VS RECOMMENDATIONS:

Distinguish between customers asking for recommendations and customers browsing the menu.

Use get_recommendations only when the customer asks for suggestions, popular items, premium choices, or the best option.

Use screen_action with view_more when the customer wants to see additional options beyond what is currently displayed.

Requests such as "other", "more", "remaining", "different", or "what else" are browsing requests, not recommendation requests.

Use the current kiosk screen and conversation history to resolve those references.

SPECIFIC ITEM REQUESTS:

When the customer asks about one specific menu item, use the product capability.

Do not retrieve the entire menu for a single product question.

SCREEN ACTIONS:

Use screen_action whenever the customer wants to operate or navigate the kiosk.

Only use controls that are currently available on the active kiosk screen.

Examples include:

- Changing food filters
- Selecting a visible product
- Showing more options
- Opening the cart
- Going back
- Adding a selected product
- Changing quantity
- Removing an item
- Checkout

Never expose internal control names to the customer.

The kiosk UI is responsible for rendering every visual change.

SPOKEN RESPONSE RULES:

Your response will be spoken aloud.

The kiosk already displays products, prices, images, descriptions and other restaurant information.

Do not read visible menu lists aloud unless the customer explicitly asks you to.

Keep responses short, natural and conversational.

Do not repeat information already visible on the screen.

CATEGORY BROWSING BEHAVIOR:

When open_category succeeds, its result contains:

- summary → customer-facing information
- context → internal reasoning only

Behavior rules:

- Mention only the names inside summary.top_choices.
- Never speak items from context.displayed_items.
- If summary.has_more_options is true, briefly let the customer know that more options are available to explore.
- Use context.displayed_items only to resolve follow-up references such as "the third one", "the last burger", or "number four".
"""

# ==========================================================
# BUILD CUSTOMER CONTEXT
# ==========================================================

def build_customer_context(conversation_context):

    context = []

    # ------------------------------------------------------
    # FOOD PREFERENCE
    # ------------------------------------------------------

    food_preference = conversation_context.get("food_preference")

    if food_preference:
        context.append(f"Customer food preference: {food_preference}")

    # ------------------------------------------------------
    # LAST CATEGORY
    # ------------------------------------------------------

    last_category = conversation_context.get("last_category")

    if last_category:
        context.append(f"Last category discussed: {last_category}")

    # ------------------------------------------------------
    # LAST ITEM
    # ------------------------------------------------------

    last_item = conversation_context.get("last_item")

    if last_item:
        context.append(f"Last item discussed: {last_item}")

    # ------------------------------------------------------
    # CART
    # ------------------------------------------------------

    cart = conversation_context.get("cart", [])

    if cart:
        context.append(
            f"Customer currently has {len(cart)} item(s) in their cart."
        )

    # ------------------------------------------------------
    # CURRENT SCREEN
    # ------------------------------------------------------

    current_screen = conversation_context.get("current_screen")

    if current_screen:
        context.append(f"Current kiosk screen: {current_screen}")

    # ------------------------------------------------------
    # AVAILABLE UI CONTROLS
    # ------------------------------------------------------

    available_controls = conversation_context.get("available_controls", [])

    if available_controls:
        context.append(
            "Current UI capabilities: " + ", ".join(available_controls)
        )

    # ------------------------------------------------------
    # PENDING STATE
    # ------------------------------------------------------

    pending_clarification = conversation_context.get("pending_clarification")

    if pending_clarification:
        context.append(
            f"Pending clarification: {pending_clarification}"
        )

    pending_suggestion = conversation_context.get("pending_suggestion")

    if pending_suggestion:
        context.append(
            f"Pending suggestion: {pending_suggestion}"
        )

    # ------------------------------------------------------
    # DEFAULT
    # ------------------------------------------------------

    if not context:
        return "No important customer context is currently stored."

    return "\n".join(context)


# ==========================================================
# GET CONVERSATION HISTORY
# ==========================================================

def get_conversation_history(conversation_context):

    history = conversation_context.get("conversation_history", [])

    return history


# ==========================================================
# SAVE CONVERSATION HISTORY
# ==========================================================

def save_conversation_history(
    conversation_context,
    messages,
):

    conversation_context["conversation_history"] = messages


# ==========================================================
# AGENT RUNTIME
# ==========================================================

def create_agent_tools(conversation_context):

    open_category = create_open_category_tool(conversation_context)

    screen_action = create_screen_action_tool(conversation_context)

    return restaurant_tools + [
        open_category,
        screen_action,
    ]


agent_runtime = AgentRuntime(
    model=model,
    tools_factory=create_agent_tools,
    system_prompt=SYSTEM_PROMPT,
)


# ==========================================================
# RUN CASHIER AGENT
# ==========================================================

def run_cashier_agent(
    user_input,
    conversation_context,
):
    history = get_conversation_history(conversation_context)

    customer_context = build_customer_context(conversation_context)

    return agent_runtime.run(
        user_input=user_input,
        conversation_context=conversation_context,
        customer_context=customer_context,
        history=history,
    )