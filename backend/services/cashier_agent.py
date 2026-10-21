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

When the customer expresses a desire for a restaurant category without specifying a particular item (e.g. "I want a burger", "Have in a burger", "Can I have a burger", "I'll have a burger", "Have a burger", "Get me a burger", "A burger", "Drink", "Sides", "Desserts"), treat that as a request to enter that category.

Use open_category to navigate to that category.

A customer saying they want a burger or have a burger means they want to browse burgers. It does NOT mean a burger should be added to the cart, even if an item was discussed previously.

Never call screen_action(add_to_cart) from category_selection or any non-product screen.

Do not ask unnecessary clarification questions before opening the category.

If the customer names a specific menu item, treat it as a specific product request instead.

BROWSING VS RECOMMENDATIONS:

Distinguish between customers asking for recommendations and customers browsing the menu.

Use get_recommendations only when the customer asks for suggestions, popular items, premium choices, or the best option.

Use screen_action with view_more when the customer wants to see additional options beyond what is currently displayed.

Requests such as "other", "more", "remaining", "different", or "what else" are browsing requests, not recommendation requests.

Use the current kiosk screen and conversation history to resolve those references.

SPECIFIC ITEM REQUESTS & PRODUCT SELECTION:

Use the select_product tool whenever the customer requests, asks for, or names a specific menu item (e.g. "Can I get a Chicken Makhani", "I want Crispy Veg Double Patty", "show me Chicken Makhani", "switch to Chicken Makhani").

When the customer is currently on a product page:
- If the customer requests or names a DIFFERENT specific product, call select_product to select and display that product on the kiosk. Do not merely talk about it or ask if they want to add it to the cart.
- If the customer asks to add the CURRENTLY selected product to the cart (e.g. "add to cart", "add this", "add it", "yes add this to cart"):
  Only use screen_action with control="add_to_cart" if you are currently on a product page AND there is an Authoritative Active Selected Product.
- If the customer says "add it to my cart" when NOT on a product page, do NOT attempt screen_action(add_to_cart). Instead, inform the customer that no item is currently active or offer to open the item they discussed previously.

Do not retrieve the entire menu for a single product question.

SCREEN ACTIONS:

Use screen_action whenever the customer wants to operate or navigate the kiosk using available screen controls.

Only use controls that are currently available in the Current Available UI Capabilities on the active kiosk screen.

If a tool returns success=False or an error, the action FAILED and was NOT executed.
- NEVER tell the customer that the action succeeded or that an item was added when the tool failed.
- NEVER instruct the customer to tap a button or control that is not present on the current screen.

Examples include:

- Changing food filters
- Showing more options
- Opening the cart
- Going back
- Adding the currently selected product to the cart
- Selecting a meal size
- Declining a meal offer
- Changing quantity
- Removing an item
- Checkout

Never expose internal control names to the customer.

The kiosk UI is responsible for rendering every visual change.

ANSWERING QUESTIONS ABOUT SCREEN OR PRODUCT SELECTION:

When the customer asks about the current screen, page, where they are, or what product is selected:
- Speak naturally and conversationally, choosing varied phrasing suited to the dialog. Do not repeat a fixed robotic template.
- Ground your answer strictly in the Authoritative Current Kiosk Screen and Authoritative Active Selected Product provided in context.
- If asked "What screen am I on?" / "Where am I?":
  Answer naturally based on the Authoritative Current Kiosk Screen (e.g., if category_selection, tell them they are at the main menu / category selection screen; if on product, tell them they are viewing product details). Never guess from conversation history or claim they are on a product page when the current screen is category_selection.
- If asked "What product did I select?" or what is currently selected:
  Answer based on the Authoritative Active Selected Product. If it is None, clarify naturally that no product is currently active or selected on screen, while you may mention the Previously Discussed Item if relevant.
- If asked what product was discussed earlier or previously:
  Use the Historical Previously Discussed Item.

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

PRODUCT SELECTION & MEAL OFFERS:

- When select_product tool result includes meal_offer with suggested_cashier_prompt or eligible=true:
  Acknowledge the product selection and ask the customer if they would like to make it a meal:
  "Good choice! Would you like to make that a meal with a side and a drink?"
- When select_product tool result does NOT include an eligible meal_offer (e.g. eligible=false, already_declined=true, or meal_offer is absent):
  Acknowledge the product selection simply and naturally without asking or offering to make it a meal.
- When an active meal offer popup is OPEN on the screen:
  - If the customer specifies a valid meal size ("medium meal", "large meal", "medium", "large"):
    Check if the requested size is in the available sizes list:
    * If available: call screen_action with control="select_meal" and value="medium" or "large".
    * If NOT available: do NOT call screen_action. Explain politely that the requested size is unavailable, state which size IS available, and ask if they would like that instead.
  - If the customer gives an ambiguous affirmation ("yes", "sure", "yeah", "make it a meal", "yes please", "of course") without specifying size:
    Ask: "Would you prefer a medium or large meal?" (or if only one size is available, ask if they want that size). Do NOT call screen_action until the customer specifies a size.
  - If the customer declines ("no thanks", "no", "not now", "just the burger", "cancel", "no meal"):
    Call screen_action with control="decline_meal". Do NOT call add_to_cart unless the customer explicitly instructs "add to cart". Declining the meal only closes the meal popup and keeps the customer on the product page.
  - If the meal offer popup is NOT open:
    Do NOT execute meal screen actions. If the customer asks for a meal when popup is closed, let them know they can tap 'Upgrade to a Meal' on screen.
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
    # AUTHORITATIVE SCREEN & PRODUCT STATE
    # ------------------------------------------------------

    current_screen = conversation_context.get("current_screen", "category_selection")
    selected_product = conversation_context.get("selected_product")
    last_item = conversation_context.get("last_item")

    screen_friendly_names = {
        "category_selection": "Category Selection (Main Welcome Menu)",
        "product": f"Product Details Page for {selected_product}" if selected_product else "Product Details Page",
        "recommended_burgers": "Recommended Burgers menu",
        "burger_menu": "Full Burger Menu",
        "recommended_drinks": "Recommended Drinks menu",
        "full_drink_menu": "Full Drinks Menu",
        "recommended_sides": "Recommended Sides menu",
        "full_side_menu": "Full Sides Menu",
        "recommended_desserts": "Recommended Desserts menu",
        "full_dessert_menu": "Full Desserts Menu",
        "cart": "Cart page",
        "payment": "Payment screen",
        "order_complete": "Order Confirmation screen",
    }
    screen_desc = screen_friendly_names.get(current_screen, current_screen)
    context.append(f"Authoritative Current Kiosk Screen: {current_screen} ({screen_desc})")

    if current_screen == "product" and selected_product:
        context.append(f"Authoritative Active Selected Product on Screen: {selected_product}")
    else:
        context.append("Authoritative Active Selected Product on Screen: None (no product is currently active or displayed on a product page)")

    if last_item:
        context.append(f"Historical Previously Discussed Item (Past Conversational Memory Only): {last_item}")

    # ------------------------------------------------------
    # CART
    # ------------------------------------------------------

    cart = conversation_context.get("cart", [])

    if cart:
        context.append(
            f"Customer currently has {len(cart)} item(s) in their cart."
        )

    # ------------------------------------------------------
    # AVAILABLE UI CONTROLS
    # ------------------------------------------------------

    available_controls = conversation_context.get("available_controls", [])

    if available_controls:
        context.append(
            "Current Available UI Capabilities: " + ", ".join(available_controls)
        )

    # ------------------------------------------------------
    # ACTIVE MEAL OFFER
    # ------------------------------------------------------

    meal_offer = conversation_context.get("meal_offer")
    declined_ids = [str(x) for x in conversation_context.get("declined_meal_products", [])]
    if meal_offer and meal_offer.get("is_open"):
        product_name = meal_offer.get("product_name", "the selected item")
        sizes = meal_offer.get("available_sizes", [])
        sizes_str = ", ".join(sizes) if sizes else "none"
        context.append(
            f"Active meal offer popup is OPEN on the screen for {product_name}. "
            f"Available meal sizes: {sizes_str}."
        )
    elif meal_offer and not meal_offer.get("is_open"):
        prod_id = str(meal_offer.get("product_id") or "")
        if prod_id and prod_id in declined_ids:
            context.append(
                f"Meal offer for {meal_offer.get('product_name', 'this product')} was previously declined by the customer. "
                "Do NOT offer to make it a meal."
            )
        else:
            context.append("Meal offer popup is currently CLOSED.")

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