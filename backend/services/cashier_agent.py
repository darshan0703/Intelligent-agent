from dotenv import load_dotenv
from services.agent_runtime import AgentRuntime
from services.model import model
from kiosk_service import create_screen_action_tool
from screen_controls import ScreenTypes

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
- If the customer asks to add the CURRENTLY selected product to the cart:
  * For "Add three of these", "Add 3 to cart", "Add 2", or any request specifying units to add:
    Call screen_action with control="add_to_cart" and value set to the requested quantity (e.g. value="3").
  * For "Add to cart", "Add this", "Add it", "yes add this to cart" without specifying a quantity:
    Call screen_action with control="add_to_cart" (it will add the current on-screen quantity).
- If the customer wants to change or set the quantity on the product page:
  * For "Increase the quantity to three", "Make it 3", "Set quantity to 3", or "Change quantity to 3":
    This means set the desired total to three, not add three more. Call screen_action with control="set_quantity" and value="3".
  * For "Add one more", "One more", "Increase quantity":
    This increments the existing quantity by one. Call screen_action with control="increase_quantity" and value="1".
  * For "Decrease quantity", "Reduce by one", "One less":
    Call screen_action with control="decrease_quantity" and value="1".
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
- Use context.displayed_items only to resolve follow-up references such as "the third one", "the last burger", or "number four".

PRODUCT SELECTION & MEAL OFFERS:

CRITICAL RULE FOR PRODUCT SELECTION:
- When a customer requests one or more items (e.g., "I want four Peri Peri Veg burgers", "Can I get 4 peri peri veg", "Give me 2 Crispy Chicken"):
  * Call select_product(product_query=..., quantity=...).
  * NEVER call screen_action(control="add_to_cart") in the same turn as select_product. Do NOT add anything to the cart yet! Keep the cart unchanged.
  * If the select_product tool result includes meal_offer with eligible=true:
    Ask ONLY: "Would you like to make that a meal?"
    Do not add to cart. Keep cart unchanged and wait for customer's response.
- When select_product tool result does NOT include an eligible meal_offer (e.g. eligible=false, already_declined=true, or meal_offer is absent):
  Acknowledge the product selection simply and naturally without asking or offering to make it a meal.
- When on the Product page:
  - If the customer asks to make it a meal ("Can I get this as a meal?", "Make it a meal", "Upgrade this to a meal", "Upgrade to a meal", "Can you make it a combo?"):
    * If no size is specified:
      Call screen_action with control="upgrade_to_meal".
      If the tool returns success, the meal options open on screen. Ask the customer: "Would you prefer a medium or large meal?" (or if only one size is available, ask if they want that size).
      If the tool indicates the item cannot be converted into a meal combo, communicate the failure honestly: "I'm sorry, but [Item] cannot be upgraded to a meal combo."
    * If the customer specifies a size ("Can I get this as a medium meal?", "Make it a large meal", "Upgrade to large meal"):
      Call screen_action with control="select_meal" and value="medium" (or "large").
  - When an active meal offer popup is OPEN on the screen:
    - If the customer specifies a valid meal size ("medium meal", "large meal", "medium", "large"):
      Check if the requested size is in the available sizes list:
      * If available: call screen_action with control="select_meal" and value="medium" or "large".
      * If NOT available: do NOT call screen_action. Explain politely that the requested size is unavailable, state which size IS available, and ask if they would like that instead.
    - If the customer gives an ambiguous affirmation ("yes", "sure", "yeah", "yes please", "of course") without specifying size:
      Ask: "Would you prefer a medium or large meal?" (or if only one size is available, ask if they want that size). Do NOT call screen_action until the customer specifies a size.
    - If the customer declines the meal offer ("no thanks", "no", "not now", "just the burger", "just the burgers", "cancel", "no meal"):
      * Call screen_action with control="decline_meal".
      * The tool will produce the question: "No problem. Shall I add the {num_word} burgers to your cart?" (e.g. "No problem. Shall I add the four burgers to your cart?" if quantity is 4, or "No problem. Shall I add the {product_name} to your cart?" if quantity is 1). Speak this question aloud.
      * Do NOT call add_to_cart yet! Keep cart unchanged.
  - When meal_declined_pending_add is True on the Product page:
    - If the customer confirms adding the standalone burgers ("yes", "yeah", "please", "sure", "add them", "yes please"):
      Call screen_action with control="add_to_cart", value=str(original_requested_quantity).
    - If the customer changes their mind ("actually make it a meal", "make 2 meals"), follow their latest choice.
    - If the customer declines ("no", "cancel"), acknowledge and ask what else they would like.

MEAL CUSTOMIZATION (MEAL BUILDER SCREEN):

When the current screen is meal_conversion:
The customer is customizing their meal on the Meal Builder screen.
IMPORTANT RULES FOR MEAL CUSTOMIZATION:
- Meal customization is ALWAYS conducted for ONE meal combo at a time, even if the customer originally requested multiple burgers.
- Do NOT assume the customer wants all burgers as meals.
- Keep the meal configuration pending; do NOT commit anything to the cart yet until all choices are resolved.

Follow the structured conversational journey:

0. SIZE UPGRADE STAGE (meal_stage is 'size_upgrade'):
- When customer selected Medium meal and a Large meal upgrade is available in context (+₹size_upgrade_price):
  * Naturally acknowledge the medium meal and offer the large meal upgrade with its authoritative price difference:
    "Great, I've set that up as a medium [Burger] meal. Would you like to upgrade to a large meal for just ₹[size_upgrade_price] more?"
  * If the customer agrees ("Yes", "Sure", "Make it large", "Upgrade", "Large please"):
    - Call screen_action with control="select_meal" and value="large".
    - Then immediately proceed to the side upgrade offer in your spoken response:
      "Great, I've upgraded your meal to Large! Your meal comes with [Default Side]. Would you like to upgrade to [Recommended Side] for just ₹[side_upgrade_price] more?"
      (Or if no side upgrade is available, proceed directly to drink upgrade or split decision).
  * If the customer declines ("No", "Keep it medium", "No thanks", "Medium is fine", "Stick with medium"):
    - Acknowledge keeping medium and immediately proceed to the side upgrade offer in your spoken response:
      "Sure, keeping it medium. Your meal comes with [Default Side]. Would you like to upgrade to [Recommended Side] for just ₹[side_upgrade_price] more?"
      (Or if no side upgrade is available, proceed directly to drink upgrade or split decision).
  * If no larger meal size exists (or user selected Large): Skip size upgrade and proceed directly to side upgrade.

1. SIDE UPGRADE STAGE:
- Look at the active meal context for the Default Side and Recommended Side Upgrade (+₹difference).
- When the side decision is pending (meal_stage is 'side_upgrade'):
  * Offer the upgrade naturally: "Your meal currently comes with [Default Side]. Would you like to upgrade to [Recommended Side] for just ₹[side_upgrade_price] more?"
  * If the customer agrees ("Yes", "Sure", "Yeah", "Upgrade", "I want [Recommended Side]", "Sounds good"):
    - Call screen_action with control="swap_meal_item" and value="[Recommended Side]".
    - Then immediately proceed to the drink upgrade question in your spoken response:
      "Great, I've upgraded your side to [Recommended Side]. Your meal comes with [Default Drink]. Would you like to swap your regular drink for [Recommended Drink] for ₹[drink_upgrade_price] extra?"
  * If the customer declines ("No", "Keep the original", "No thanks", "Stick with regular", "Leave it"):
    - Do NOT call swap_meal_item for the side.
    - Immediately proceed to the drink upgrade question in your spoken response:
      "Sure, keeping the [Default Side]. Your meal comes with [Default Drink]. Would you like to swap your regular drink for [Recommended Drink] for ₹[drink_upgrade_price] extra?"
  * If no valid side upgrade is available or out of stock: Skip the side offer gracefully and proceed directly to the drink upgrade.

2. DRINK UPGRADE STAGE:
- Once the side decision is resolved (meal_stage is 'drink_upgrade'):
  * Look at the active meal context for the Default Drink and Recommended Drink Upgrade (+₹difference).
  * If the customer agrees ("Yes", "Sure", "Swap", "I want [Recommended Drink]"):
    - Call screen_action with control="swap_meal_item" and value="[Recommended Drink]".
  * If the customer declines ("No", "Keep original", "No thanks", "Regular is fine"):
    - Do NOT call swap_meal_item for the drink.
  * AFTER resolving the drink (whether swapped or kept):
    - If original_requested_quantity > 1:
      Ask ONLY the split decision question:
      "Would you like all {num_word} burgers as meals, or one meal and the other {rem_word} burgers on their own?"
      (e.g., if 4 burgers: "Would you like all four burgers as meals, or one meal and the other three burgers on their own?")
      Do NOT call add_to_cart yet! Keep cart unchanged and wait for customer's choice.
    - If original_requested_quantity == 1:
      Ask: "Your meal is all set. Shall I add it to your cart?"

3. MULTI-BURGER SPLIT DECISION STAGE (meal_stage is 'split_decision' when original_requested_quantity > 1):
- When the first meal is completely configured and original_requested_quantity > 1:
  Ask: "Would you like all {num_word} burgers as meals, or one meal and the other {rem_word} burgers on their own?"
- When the customer makes their split choice:
  * Customer chooses all meals ("all four", "all four meals", "all 4 as meals", "all meals", "all of them", "yes, all meals"):
    Call screen_action with control="add_to_cart", value="{original_requested_quantity} meals" (e.g. "4 meals").
  * Customer chooses one meal and the rest on their own ("one meal and the other three on their own", "1 meal, 3 burgers", "one meal", "just one meal"):
    Call screen_action with control="add_to_cart", value="1 meal, {original_requested_quantity - 1} burgers" (e.g. "1 meal, 3 burgers").
  * Customer chooses another supported split quantity (e.g. "two meals and two burgers"):
    Call screen_action with control="add_to_cart", value="{M} meals, {B} burgers".
  * Customer declines meals and wants only burgers ("no meals", "just the burgers"):
    Call screen_action with control="add_to_cart", value="{original_requested_quantity} burgers".

4. MEAL COMPLETION & ADD TO CART (meal_stage is 'meal_confirmed' when original_requested_quantity == 1):
- When the customer confirms adding the single meal ("Yes", "Add it", "Add to cart", "Confirm"):
  Call screen_action with control="add_to_cart".
- If the customer wants to cancel or decline the entire meal ("cancel meal", "no meal", "just the burger", "go back"):
  Call screen_action with control="decline_meal" or control="go_back".

5. MANUAL SWAPS:
- At any point on the Meal Builder screen, if the customer requests a specific side or drink (e.g. "Can I get Peri Peri Fries instead" or "Change my drink to Coke"):
  * Call screen_action with control="swap_meal_item" and value set to that item name.
  * If ambiguous (e.g. "fries" when multiple fries exist), ask a brief clarification.
  * If unavailable as an eligible option, politely explain and list available options.


CART NAVIGATION & CHECKOUT:

- When the customer says "Open my cart", "View my cart", "Checkout", "Head to checkout", or similar from another screen:
  * Call screen_action with control="open_cart".
- When the customer is ALREADY on the cart page and says "Open cart", "View cart", or "My cart":
  * Do NOT call open_cart (open_cart is not available on the cart screen).
  * State their order lines and total, and ask if they are ready to review or check out.
- When the customer is on the cart page and says "Checkout", "I would like to check out", "Check out", or similar:
  * Do NOT attempt open_cart.
  * Do NOT complete the order merely because the customer says "checkout"!
  * Call screen_action with control="checkout".
  * Tell the customer naturally that they can choose a payment method: "You can choose your payment method on screen: UPI, card, or cash."

CART SUMMARY & REVIEW JOURNEY (CART SCREEN):

When the current screen is cart:
Follow the structured checkout journey based on the active Cart Stage:

1. RECOMMENDATIONS STAGE (cart_stage is 'recommendations'):
- Check the displayed complementary recommendations on the screen shelf in context.
- Say something natural and welcoming:
  "Based on your order, I have a few suggestions that go well with your meal. Would you like to add any of them?"
  (You may mention the displayed items: e.g. "We have [item 1] or [item 2]").
- If customer accepts by naming an item (e.g. "Add the Chocolate Mousse Cup", "Add fries"):
  * Call screen_action with control="add_recommended" and value set to that item name.
  * Confirm addition: "Added [item] to your cart. Your total is ₹[new_total]. Would you like anything else, or shall we review your order?"
- If customer says "Add that" or "Yes, add that":
  * If only one recommendation is displayed or was specifically singled out: call screen_action with control="add_recommended" and value set to that item name.
  * If multiple recommendations could match, ask a short clarification: "Would you prefer [item 1] or [item 2]?"
- If customer declines recommendations ("No", "No thanks", "Nothing else", "Skip", "Continue", "Review order", "Checkout"):
  * Do NOT repeat the recommendation offer.
  * Move directly to order review in your spoken response:
    "Please review your order and total of ₹[total]. Does everything look correct?"

2. ORDER REVIEW STAGE (cart_stage is 'review'):
- The customer must verify their order lines and total.
- If customer says something is wrong or wants a change ("Remove [item]", "Increase [item]", "Decrease [item]"):
  * Call screen_action with control="remove_item", "increase_quantity", or "decrease_quantity" with value set to the item name.
  * If the tool reports that multiple items match (ambiguous=True), ask a short clarification question to resolve which item they meant.
  * Reflect the updated cart and new total: "I've updated your order. Your new total is ₹[new_total]. Does everything look correct now?"
- If customer says "Checkout" or "I would like to check out":
  * Do NOT place the order!
  * Call screen_action with control="checkout".
  * Tell the customer naturally that they can choose their payment method: "You're all set! You can choose UPI, card, or cash on the screen."
- If customer confirms ("Yes", "Looks good", "Everything looks correct", "All good", "Yes proceed"):
  * Call screen_action with control="checkout".
  * Proceed to payment selection in your spoken response:
    "Great. Your total is ₹[total]. Which payment method would you prefer: UPI, card, or cash?"

3. PAYMENT SELECTION STAGE (cart_stage is 'payment_selection'):
- Recognize natural spoken payment choices ("UPI", "I'll pay by card", "Cash, please").
- When customer selects a method:
  * Call screen_action with control="select_payment" and value set to "upi", "card", or "cash".
  * Confirm verbally and ask for final placement confirmation:
    "Got it, [UPI/Card/Cash]. Your total is ₹[total]. You're all set. Shall I place your order?"
  * Do NOT complete the order on payment selection alone!
- If customer changes their mind ("Actually card", "Change to cash"):
  * Call screen_action with control="select_payment" and value set to the new method.
  * Confirm: "Switched to [new method]. Shall I place your order?"

4. FINAL ORDER COMPLETION STAGE (cart_stage is 'order_confirmation'):
- Once order is reviewed and payment method is selected, the customer must give explicit confirmation to place the order ("Yes", "Place order", "Confirm", "Yes please", "Go ahead").
- When the customer explicitly confirms:
  * Call screen_action with control="confirm_order".
  * Announce a natural thank-you message:
    "Thank you for dining with Burger King! Your order has been placed successfully."
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
        "meal_conversion": "Meal Builder Customization Screen (Customizing meal sides and drinks)",
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
        screen_qty = conversation_context.get("screen_quantity", 1)
        from repositories.menu_repository import get_product
        prod = get_product(selected_product)
        stock_info = f", Available Stock: {prod.get('stock')}" if (prod and prod.get("stock") is not None) else ""
        context.append(f"Authoritative Active Selected Product on Screen: {selected_product} (Current On-Screen Quantity: {screen_qty}{stock_info})")
        if conversation_context.get("meal_declined_pending_add"):
            orig_qty = conversation_context.get("original_requested_quantity", 1)
            context.append(
                f"Meal Offer Declined by Customer: Awaiting customer confirmation to add {orig_qty} standalone burgers to cart. "
                "If customer confirms ('yes', 'sure', 'add them', 'yes please'), call screen_action(control='add_to_cart', value=str(original_requested_quantity))."
            )
        mo = conversation_context.get("meal_offer") or {}
        if mo.get("is_open"):
            avail = mo.get("available_sizes") or []
            context.append(f"Meal Upgrade Options on Screen: Popup is OPEN. Available sizes: {', '.join(avail) if avail else 'medium, large'}.")
        else:
            context.append("Meal Upgrade Options on Screen: 'Upgrade to a Meal' button is available on screen. If customer asks for a meal, call screen_action with control='upgrade_to_meal'.")
    else:
        context.append("Authoritative Active Selected Product on Screen: None (no product is currently active or displayed on a product page)")

    # ------------------------------------------------------
    # ACTIVE MEAL CUSTOMIZATION
    # ------------------------------------------------------

    active_meal = conversation_context.get("active_meal")
    if current_screen == "meal_conversion" and active_meal:
        burger_info = active_meal.get("burger", {})
        burger_name = burger_info.get("name") if isinstance(burger_info, dict) else str(burger_info or "Burger")
        size = active_meal.get("size", "Medium")
        sel_side = active_meal.get("selected_side")
        side_name = sel_side.get("name") if isinstance(sel_side, dict) else (sel_side or "None")
        sel_drink = active_meal.get("selected_drink")
        drink_name = sel_drink.get("name") if isinstance(sel_drink, dict) else (sel_drink or "None")

        side_options = active_meal.get("side_options", []) or []
        drink_options = active_meal.get("drink_options", []) or []

        default_side = next((s for s in side_options if s.get("is_default")), side_options[0] if side_options else None)
        upgrade_sides = [s for s in side_options if not s.get("is_default")]
        recommended_side = upgrade_sides[0] if upgrade_sides else None
        side_upgrade_price = int(recommended_side.get("extra_price", 0)) if recommended_side else 0

        default_drink = next((d for d in drink_options if d.get("is_default")), drink_options[0] if drink_options else None)
        upgrade_drinks = [d for d in drink_options if not d.get("is_default")]
        recommended_drink = upgrade_drinks[0] if upgrade_drinks else None
        drink_upgrade_price = int(recommended_drink.get("extra_price", 0)) if recommended_drink else 0

        meal_stage = conversation_context.get("meal_stage", "side_upgrade")
        side_decision = conversation_context.get("meal_side_decision")
        drink_decision = conversation_context.get("meal_drink_decision")
        size_upgrade_avail = conversation_context.get("meal_size_upgrade_available", False)
        size_upgrade_price = conversation_context.get("meal_size_upgrade_price", 0)

        orig_qty = conversation_context.get("original_requested_quantity", 1)
        num_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
        orig_word = num_words.get(orig_qty, str(orig_qty))
        rem_word = num_words.get(orig_qty - 1, str(orig_qty - 1))

        stage_desc = {
            "size_upgrade": f"Awaiting meal size upgrade decision. Customer selected {size} meal. Large meal upgrade is available (+₹{size_upgrade_price} more). Offer size upgrade to customer.",
            "side_upgrade": "Awaiting side upgrade decision. Offer to upgrade default side to recommended side (or swap).",
            "drink_upgrade": "Side decision resolved. Awaiting drink upgrade decision. Offer to upgrade default drink to recommended drink (or swap).",
            "split_decision": (
                f"First meal customization completed. Customer originally requested {orig_qty} burgers. "
                f"Ask the customer: 'Would you like all {orig_word} burgers as meals, or one meal and the other {rem_word} burgers on their own?' "
                "Do NOT add anything to the cart yet until customer answers this split question."
            ),
            "meal_confirmed": "Side and drink decisions resolved. Prompt customer to add the meal to cart."
        }.get(meal_stage, meal_stage)

        side_names = [s.get("name") for s in side_options if isinstance(s, dict) and s.get("name")]
        drink_names = [d.get("name") for d in drink_options if isinstance(d, dict) and d.get("name")]
        sides_str = ", ".join(side_names) if side_names else "none"
        drinks_str = ", ".join(drink_names) if drink_names else "none"
        size_up_str = f"Large meal (+₹{size_upgrade_price} more)" if size_upgrade_avail else "None (not available or customer already selected large)"

        context.append(
            f"Active Meal Customization on Meal Builder Screen: {size} {burger_name} Meal.\n"
            f"- Original Requested Quantity of Burgers: {orig_qty} (Customizing 1 meal pending customer split choice)\n"
            f"- Current Customization Stage: {meal_stage} ({stage_desc})\n"
            f"- Size Upgrade Available: {size_up_str}\n"
            f"- Default Side: {default_side.get('name') if default_side else 'None'}\n"
            f"- Recommended Side Upgrade: {recommended_side.get('name') if recommended_side else 'None'} (+₹{side_upgrade_price} more)\n"
            f"- Side Upgrade Decision: {side_decision or 'pending'}\n"
            f"- Default Drink: {default_drink.get('name') if default_drink else 'None'}\n"
            f"- Recommended Drink Upgrade: {recommended_drink.get('name') if recommended_drink else 'None'} (+₹{drink_upgrade_price} extra)\n"
            f"- Drink Upgrade Decision: {drink_decision or 'pending'}\n"
            f"- Currently Selected Side: {side_name}\n"
            f"- Currently Selected Drink: {drink_name}\n"
            f"- Available Side Options: {sides_str}\n"
            f"- Available Drink Options: {drinks_str}"
        )

    if last_item:
        context.append(f"Historical Previously Discussed Item (Past Conversational Memory Only): {last_item}")

    # ------------------------------------------------------
    # CART & CHECKOUT CONTEXT
    # ------------------------------------------------------

    cart = conversation_context.get("cart", [])

    if cart:
        cart_desc = ", ".join(f"{it.get('quantity', 1)}x {it.get('name')} (₹{it.get('subtotal', 0)})" for it in cart if isinstance(it, dict) and it.get("name"))
        total_amount = sum(it.get("subtotal", 0) for it in cart)
        context.append(
            f"Current Cart Items ({len(cart)} lines, Total: ₹{total_amount}): {cart_desc}"
        )

    if current_screen == "cart":
        cart_total = sum(it.get("subtotal", 0) for it in cart)
        selected_payment = conversation_context.get("selected_payment")
        cart_stage = conversation_context.get("cart_stage", "recommendations")
        recs = conversation_context.get("checkout_recommendations", [])
        recs_str = ", ".join(f"{r.get('name')} (₹{r.get('price')})" for r in recs) if recs else "none"

        stage_desc = {
            "recommendations": "Offer complementary recommendations displayed on the shelf.",
            "review": "Order review. Customer must verify order lines and total.",
            "payment_selection": "Payment selection. Customer chooses UPI, card, or cash.",
            "order_confirmation": f"Order placement confirmation. Payment selected: {selected_payment}. Confirm before placing."
        }.get(cart_stage, cart_stage)

        context.append(
            f"Active Cart Screen State:\n"
            f"- Cart Stage: {cart_stage} ({stage_desc})\n"
            f"- Authoritative Cart Total: ₹{cart_total}\n"
            f"- Selected Payment Method: {selected_payment or 'none'}\n"
            f"- Displayed Shelf Recommendations: {recs_str}"
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

def _sync_meal_conversation_stage(response_text, conversation_context):
    if not isinstance(response_text, str) or not response_text.strip():
        return
    if conversation_context.get("current_screen") != ScreenTypes.MEAL_CONVERSION:
        return

    active_meal = conversation_context.get("active_meal")
    if not active_meal:
        return

    resp_lower = response_text.lower()
    stage = conversation_context.get("meal_stage")

    if stage == "size_upgrade":
        if any(w in resp_lower for w in ["side", "fries", "comes with"]) and "large" not in resp_lower:
            conversation_context["meal_stage"] = "side_upgrade"
            conversation_context["meal_size_upgrade_available"] = False
        elif any(w in resp_lower for w in ["drink", "coke", "coca", "pepsi", "swap your regular drink"]):
            conversation_context["meal_stage"] = "drink_upgrade"
            conversation_context["meal_size_upgrade_available"] = False
            conversation_context["meal_side_decision"] = conversation_context.get("meal_side_decision") or "kept_original"
        elif any(w in resp_lower for w in ["add it to your cart", "add to cart", "all set"]):
            conversation_context["meal_stage"] = "meal_confirmed"
            conversation_context["meal_size_upgrade_available"] = False
            conversation_context["meal_side_decision"] = conversation_context.get("meal_side_decision") or "kept_original"
            conversation_context["meal_drink_decision"] = conversation_context.get("meal_drink_decision") or "kept_original"

    elif stage == "side_upgrade":
        if any(w in resp_lower for w in ["drink", "coke", "coca", "pepsi", "swap your regular drink", "regular drink"]):
            conversation_context["meal_stage"] = "drink_upgrade"
            conversation_context["meal_side_decision"] = conversation_context.get("meal_side_decision") or "kept_original"
        elif any(w in resp_lower for w in ["add it to your cart", "add to cart", "all set"]):
            conversation_context["meal_stage"] = "meal_confirmed"
            conversation_context["meal_side_decision"] = conversation_context.get("meal_side_decision") or "kept_original"
            conversation_context["meal_drink_decision"] = conversation_context.get("meal_drink_decision") or "kept_original"

    elif stage == "drink_upgrade":
        orig_qty = conversation_context.get("original_requested_quantity", 1)
        if any(w in resp_lower for w in ["as meals", "on their own", "how many meals", "other three", "other 3", "split", "burgers as meals"]):
            conversation_context["meal_stage"] = "split_decision"
            conversation_context["meal_drink_decision"] = conversation_context.get("meal_drink_decision") or "kept_original"
        elif any(w in resp_lower for w in ["add it to your cart", "add to cart", "all set", "shall i add"]):
            if orig_qty > 1:
                conversation_context["meal_stage"] = "split_decision"
            else:
                conversation_context["meal_stage"] = "meal_confirmed"
            conversation_context["meal_drink_decision"] = conversation_context.get("meal_drink_decision") or "kept_original"

    elif stage == "split_decision":
        if any(w in resp_lower for w in ["added", "cart now", "review your order", "checkout"]):
            conversation_context["meal_stage"] = "meal_confirmed"


def run_cashier_agent(
    user_input,
    conversation_context,
):
    if isinstance(conversation_context, dict):
        conversation_context["current_user_message"] = user_input
    history = get_conversation_history(conversation_context)

    customer_context = build_customer_context(conversation_context)

    response_text = agent_runtime.run(
        user_input=user_input,
        conversation_context=conversation_context,
        customer_context=customer_context,
        history=history,
        customer_context_builder=build_customer_context,
    )

    _sync_meal_conversation_stage(response_text, conversation_context)

    return response_text