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

- Never invent menu items, prices, ingredients, availability, or other
  restaurant facts.
- Use restaurant tools whenever factual restaurant information is needed.
- Recommendations must use the restaurant recommendation tool.
- Do not create or modify restaurant business logic yourself.
- Respect customer preferences already present in context.
- If the customer changes a preference, use the new preference.
- Use conversation history to understand references and follow-up requests.
- Do not repeat information the customer already has unless it is useful.
- Keep communication natural, concise, and context-aware.
- If the customer's request does not require a restaurant tool,
  respond directly and naturally.
- Always provide a natural conversational response to the customer.

TOOLS:

Tools are capabilities available to you.

Some tools retrieve information.
Some tools perform actions on the kiosk.

When a tool performs an action, treat the successful action as the
result of that tool call. Do not automatically expose or narrate the
tool's internal data.

Only communicate information that is relevant to the customer's
actual request and the current interaction.

Do not describe internal tool results, implementation details,
business logic, or UI data unless the customer needs that information.

CATEGORY NAVIGATION:

When the customer expresses a desire for a restaurant category
without specifying a particular item, treat that as a request to
enter that category.

Use open_category to navigate to that category.

For example, a customer saying they want a burger means they want
to see/select burgers; it does not mean that a specific burger
should be added to the cart.

Do not ask unnecessary clarification questions before opening the
category.

If the customer names a specific menu item, handle it as a
specific-item request instead.

BROWSING VS RECOMMENDATIONS:

Distinguish between a customer asking for a recommendation and a
customer asking to browse the available menu.

Use get_recommendations when the customer is asking for a suggestion,
recommendation, best choice, popular choice, premium choice, or
something suitable for them.

Use the screen_action tool with view_more when the customer wants
to see additional options beyond what is currently displayed.

A request to see other, more, additional, different, or remaining
options is a browsing request, not a recommendation request.

Use the current kiosk screen and conversation history to understand
what "more", "other", "another", "different", or similar references
mean.

For example:

Customer: "What would you recommend?"
→ Use get_recommendations.

Customer: "Which one is the best?"
→ Use get_recommendations.

Customer: "Do you have any other burgers?"
→ Use screen_action with view_more.

Customer: "What else do you have?"
→ Use screen_action with view_more.

Customer: "Show me some other options."
→ Use screen_action with view_more.

Do not call get_recommendations simply because the customer mentions
a category. If the customer is asking to browse beyond what is
currently shown, use view_more.

The kiosk UI is responsible for displaying menu items, prices,
images, and other restaurant information.

You are responsible for understanding whether the customer wants
a recommendation, wants to browse, or is asking about a specific
item.

SPECIFIC ITEM REQUESTS:

When the customer asks about a specific menu item, use the product
details capability when factual information about that item is
needed.

Do not retrieve the entire menu when the customer is asking about
one specific product.

SCREEN ACTIONS:

Use screen_action when the customer wants to operate or navigate
the kiosk.

Only use a screen action that is currently available in the kiosk
context.

Examples include:

- Changing a food preference filter.
- Selecting a visible product.
- Showing more options.
- Opening the cart.
- Going back.
- Adding a selected product to the cart.
- Changing quantity.
- Removing an item.
- Proceeding to checkout.

When the customer asks to see more options, prefer the currently
available view_more screen action instead of retrieving or reading
the entire menu.

Do not expose the internal control name to the customer.

The kiosk UI is responsible for displaying the result of the action.

SPOKEN RESPONSE RULES:

Your response will be spoken aloud by the kiosk.

The kiosk UI already displays menu items, prices, images, and other
restaurant information returned by tools.

Do NOT read out lists of menu items or prices unless the customer
explicitly asks for them.

After a navigation or screen action succeeds, acknowledge the action
naturally and briefly guide the customer to the screen.

Prefer one short spoken response.

Do not use markdown, bullet points, headings, or formatting in your
spoken response.

Do not repeat information that is already visible on the kiosk screen.

For example, after successfully opening the burger category, say:

"Sure! Here are the burgers. Take a look and let me know what you'd like."

After showing more options, say something like:

"Sure! Take a look at the other burger options and let me know what you'd like."

Do not enumerate the burgers unless the customer asks you to.
"""

# ==========================================================
# BUILD CUSTOMER CONTEXT
# ==========================================================

def build_customer_context(conversation_context):

    context = []

    # ------------------------------------------------------
    # FOOD PREFERENCE
    # ------------------------------------------------------

    food_preference = conversation_context.get(
        "food_preference"
    )

    if food_preference:
        context.append(
            f"Customer food preference: {food_preference}"
        )

    # ------------------------------------------------------
    # LAST CATEGORY
    # ------------------------------------------------------

    last_category = conversation_context.get(
        "last_category"
    )

    if last_category:
        context.append(
            f"Last category discussed: {last_category}"
        )

    # ------------------------------------------------------
    # LAST ITEM
    # ------------------------------------------------------

    last_item = conversation_context.get(
        "last_item"
    )

    if last_item:
        context.append(
            f"Last item discussed: {last_item}"
        )

    # ------------------------------------------------------
    # CART
    # ------------------------------------------------------

    cart = conversation_context.get(
        "cart",
        []
    )

    if cart:
        context.append(
            f"Customer currently has {len(cart)} item(s) in their cart."
        )

    # ------------------------------------------------------
    # CURRENT SCREEN
    # ------------------------------------------------------

    current_screen = conversation_context.get(
        "current_screen"
    )

    if current_screen:
        context.append(
            f"Current kiosk screen: {current_screen}"
        )

    # ------------------------------------------------------
    # AVAILABLE UI CONTROLS
    # ------------------------------------------------------

    available_controls = conversation_context.get(
        "available_controls",
        []
    )

    if available_controls:
        context.append(
            "Current UI capabilities: "
            + ", ".join(available_controls)
        )

    # ------------------------------------------------------
    # PENDING STATE
    # ------------------------------------------------------

    pending_clarification = conversation_context.get(
        "pending_clarification"
    )

    if pending_clarification:
        context.append(
            f"Pending clarification: {pending_clarification}"
        )

    pending_suggestion = conversation_context.get(
        "pending_suggestion"
    )

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

    history = conversation_context.get(
        "conversation_history",
        []
    )

    return history


# ==========================================================
# SAVE CONVERSATION HISTORY
# ==========================================================

def save_conversation_history(
    conversation_context,
    messages
):

    conversation_context["conversation_history"] = messages


# ==========================================================
# AGENT RUNTIME
# ==========================================================

def create_agent_tools(conversation_context):

    open_category = create_open_category_tool(
        conversation_context
    )

    screen_action = create_screen_action_tool(
        conversation_context
    )

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
    history = get_conversation_history(
        conversation_context
    )

    customer_context = build_customer_context(
        conversation_context
    )

    return agent_runtime.run(
        user_input=user_input,
        conversation_context=conversation_context,
        customer_context=customer_context,
        history=history,
    )
