from conversation import (
    handle_correction,
    handle_decline,
    handle_checkout
)

from intent import extract_intent
from screen_intent import extract_screen_intent
from state import conversation_context
from typing import Optional

from services.menuservice import (
    handle_menu,
    handle_category,
    handle_more_options,
    handle_full_menu
)

from orderservice import (
    handle_order,
    handle_remove
)

from itemclassifiers import resolve_burger_clarification

from schemas import (
    KioskResponse,
    ScreenTypes
)

from services.productservice import handle_product
from screen_controls import get_screen_controls
from services.cashier_response import generate_cashier_response

from langchain_core.tools import tool


# ==========================================
# SCREEN TRACKING
# ==========================================

def track_screen(screen_or_response, extra=None):
    """
    Authoritative central synchronization point for kiosk UI state.
    Handles KioskResponse objects, direct screen strings, controls,
    active product selection, meal offers, and monotonic sequence validation.
    """
    if isinstance(screen_or_response, KioskResponse):
        screen = screen_or_response.screen
        data = screen_or_response.data or {}
    elif isinstance(screen_or_response, str):
        screen = screen_or_response
        data = extra or {}
    else:
        return screen_or_response

    # Verify that screen is a recognized kiosk screen identifier
    valid_screens = {
        ScreenTypes.HOME, ScreenTypes.CATEGORY_SELECTION,
        ScreenTypes.BURGER_TYPE_SELECTION,
        ScreenTypes.RECOMMENDED_BURGERS, ScreenTypes.FULL_BURGER_MENU, ScreenTypes.BURGER_MENU,
        ScreenTypes.RECOMMENDED_DRINKS, ScreenTypes.FULL_DRINK_MENU, ScreenTypes.DRINK_MENU,
        ScreenTypes.RECOMMENDED_SIDES, ScreenTypes.FULL_SIDE_MENU, ScreenTypes.SIDE_MENU,
        ScreenTypes.RECOMMENDED_DESSERTS, ScreenTypes.FULL_DESSERT_MENU, ScreenTypes.DESSERT_MENU,
        ScreenTypes.PRODUCT, ScreenTypes.MEAL_CONVERSION,
        ScreenTypes.UPSELL, ScreenTypes.CART, ScreenTypes.CHECKOUT,
        ScreenTypes.PAYMENT, ScreenTypes.ORDER_COMPLETE,
    }
    if screen not in valid_screens:
        if isinstance(screen_or_response, KioskResponse):
            return screen_or_response
        return screen_or_response, True

    # 1. Session & Monotonic sequence validation to prevent stale overwrites
    incoming_session_id = data.get("session_id")
    current_session_id = conversation_context.get("session_id")

    # If incoming session is specified and current session is active,
    # reject updates belonging to a different/previous session.
    # For client screen syncs (screen_or_response is str), if an active session exists,
    # reject updates lacking or mismatching the active session.
    if isinstance(screen_or_response, str) and current_session_id:
        if not incoming_session_id or incoming_session_id != current_session_id:
            print(
                f"[track_screen] Stale/mismatched session update ignored: {incoming_session_id} != {current_session_id}"
            )
            return screen_or_response, False
    elif incoming_session_id and current_session_id and incoming_session_id != current_session_id:
        print(
            f"[track_screen] Stale/mismatched session update ignored: {incoming_session_id} != {current_session_id}"
        )
        if isinstance(screen_or_response, KioskResponse):
            return screen_or_response
        return screen_or_response, False

    if incoming_session_id and not current_session_id:
        conversation_context["session_id"] = incoming_session_id

    incoming_seq = data.get("seq")
    if incoming_seq is not None:
        current_seq = conversation_context.get("_screen_seq", 0)
        if incoming_seq <= current_seq:
            print(
                f"[track_screen] Stale screen sync ignored: incoming seq {incoming_seq} <= current {current_seq} (screen: {screen})"
            )
            if isinstance(screen_or_response, KioskResponse):
                return screen_or_response
            return screen_or_response, False
        conversation_context["_screen_seq"] = incoming_seq

    # 2. Update Current Screen & Available Controls
    conversation_context["current_screen"] = screen
    controls = list(get_screen_controls(screen))

    # Track last category screen for smart back navigation
    if screen in [
        ScreenTypes.RECOMMENDED_BURGERS,
        ScreenTypes.FULL_BURGER_MENU,
        ScreenTypes.RECOMMENDED_DRINKS,
        ScreenTypes.FULL_DRINK_MENU,
        ScreenTypes.RECOMMENDED_SIDES,
        ScreenTypes.FULL_SIDE_MENU,
        ScreenTypes.RECOMMENDED_DESSERTS,
        ScreenTypes.FULL_DESSERT_MENU,
    ]:
        conversation_context["last_category_screen"] = screen

    # 3. Authoritative Active Product Selection
    if screen in [ScreenTypes.PRODUCT, ScreenTypes.MEAL_CONVERSION]:
        prod = data.get("product")
        if not prod and data.get("meal_offer"):
            mo = data.get("meal_offer")
            if mo.get("product_name") or mo.get("product_id"):
                prod = {"id": mo.get("product_id"), "name": mo.get("product_name")}
        if not prod and data.get("meal") and isinstance(data.get("meal"), dict):
            prod = data.get("meal", {}).get("burger")
        if prod:
            if isinstance(prod, dict):
                p_name = prod.get("name")
                p_id = prod.get("id")
            else:
                p_name = str(prod)
            product_changed = False
            if p_id is not None and conversation_context.get("selected_product_id") is not None and conversation_context.get("selected_product_id") != p_id:
                product_changed = True
            elif p_name and conversation_context.get("selected_product") and p_name != conversation_context.get("selected_product"):
                product_changed = True

            if product_changed:
                conversation_context["screen_quantity"] = 1
            conversation_context["selected_product"] = p_name
            if p_id is not None:
                conversation_context["selected_product_id"] = p_id
            conversation_context["last_item"] = p_name
        else:
            conversation_context["selected_product"] = None
            conversation_context["selected_product_id"] = None
            conversation_context["screen_quantity"] = 1

        if "quantity" in data and data.get("quantity") is not None:
            try:
                conversation_context["screen_quantity"] = max(1, int(data["quantity"]))
            except (ValueError, TypeError):
                pass
    else:
        conversation_context["selected_product"] = None
        conversation_context["selected_product_id"] = None
        conversation_context["screen_quantity"] = 1

    # 4. Meal Offer Synchronization
    if screen == ScreenTypes.PRODUCT:
        meal_offer = data.get("meal_offer")
        declined_ids = [str(x) for x in conversation_context.get("declined_meal_products", [])]
        if meal_offer is not None:
            conversation_context["meal_offer"] = meal_offer
            prod_id = meal_offer.get("product_id")
            if meal_offer.get("is_dismissed"):
                if prod_id is not None:
                    if "declined_meal_products" not in conversation_context:
                        conversation_context["declined_meal_products"] = []
                    if str(prod_id) not in [str(x) for x in conversation_context["declined_meal_products"]]:
                        conversation_context["declined_meal_products"].append(prod_id)
                meal_offer["is_open"] = False
            elif prod_id is not None and str(prod_id) in declined_ids:
                meal_offer["is_open"] = False

            if meal_offer.get("is_open"):
                for mc in ["select_meal", "decline_meal"]:
                    if mc not in controls:
                        controls.append(mc)
            else:
                controls = [c for c in controls if c not in ["select_meal", "decline_meal", "accept_meal"]]
        elif "meal_offer" in conversation_context and conversation_context["meal_offer"]:
            mo = conversation_context["meal_offer"]
            if mo.get("is_open"):
                for mc in ["select_meal", "decline_meal"]:
                    if mc not in controls:
                        controls.append(mc)
            else:
                controls = [c for c in controls if c not in ["select_meal", "decline_meal", "accept_meal"]]
    elif screen == ScreenTypes.MEAL_CONVERSION:
        if extra and isinstance(extra, dict) and "meal_customization" in extra:
            conversation_context["active_meal"] = extra.get("meal_customization")
        if "meal_stage" not in conversation_context:
            act_meal = conversation_context.get("active_meal") or {}
            size = (act_meal.get("size") or "").lower()
            burger_info = act_meal.get("burger") or {}
            burger_id = burger_info.get("id") if isinstance(burger_info, dict) else None
            size_upgrade_avail = False
            size_upgrade_price = 0
            if size == "medium" and burger_id:
                try:
                    from services.meal_service import build_meal
                    pref = conversation_context.get("food_preference")
                    cart = conversation_context.get("cart", [])
                    large_m = build_meal(burger_id, "large", food_preference=pref, cart=cart)
                    if large_m:
                        diff = large_m.get("meal_price", 0) - act_meal.get("meal_price", 0)
                        if diff > 0:
                            size_upgrade_avail = True
                            diff_f = float(diff)
                            size_upgrade_price = int(diff_f) if diff_f.is_integer() else round(diff_f, 2)
                except Exception as e:
                    print(f"Error checking large meal in track_screen: {e}")

            if size_upgrade_avail:
                conversation_context["meal_stage"] = "size_upgrade"
                conversation_context["meal_size_upgrade_available"] = True
                conversation_context["meal_size_upgrade_price"] = size_upgrade_price
            else:
                side_opts = act_meal.get("side_options", []) or []
                up_sides = [s for s in side_opts if not s.get("is_default")]
                drink_opts = act_meal.get("drink_options", []) or []
                up_drinks = [d for d in drink_opts if not d.get("is_default")]
                if up_sides:
                    conversation_context["meal_stage"] = "side_upgrade"
                elif up_drinks:
                    conversation_context["meal_stage"] = "drink_upgrade"
                else:
                    conversation_context["meal_stage"] = "meal_confirmed"
                conversation_context["meal_size_upgrade_available"] = False
                conversation_context["meal_size_upgrade_price"] = 0

            conversation_context["meal_side_decision"] = None
            conversation_context["meal_drink_decision"] = None
    elif screen == ScreenTypes.CART:
        if "cart_stage" not in conversation_context:
            conversation_context["cart_stage"] = "recommendations"
        if not conversation_context.get("checkout_recommendations"):
            try:
                from api import _build_checkout_recommendations
                conversation_context["checkout_recommendations"] = _build_checkout_recommendations(
                    conversation_context.get("cart", [])
                )
            except Exception as e:
                print(f"[track_screen] Note: could not pre-load recommendations: {e}")
    else:
        conversation_context.pop("meal_offer", None)
        conversation_context.pop("active_meal", None)
        conversation_context.pop("meal_stage", None)
        conversation_context.pop("meal_size_upgrade_available", None)
        conversation_context.pop("meal_size_upgrade_price", None)
        conversation_context.pop("meal_side_decision", None)
        conversation_context.pop("meal_drink_decision", None)
        controls = [c for c in controls if c not in ["select_meal", "decline_meal", "accept_meal"]]

    if screen != ScreenTypes.MEAL_CONVERSION:
        conversation_context.pop("meal_stage", None)
        conversation_context.pop("meal_size_upgrade_available", None)
        conversation_context.pop("meal_size_upgrade_price", None)
        conversation_context.pop("meal_side_decision", None)
        conversation_context.pop("meal_drink_decision", None)

    if screen != ScreenTypes.CART:
        conversation_context.pop("cart_stage", None)
        conversation_context.pop("checkout_recommendations", None)
        conversation_context.pop("selected_payment", None)

    conversation_context["available_controls"] = controls

    print(
        f"[track_screen] Screen: {screen} (seq: {conversation_context.get('_screen_seq')}), "
        f"Active Product: {conversation_context.get('selected_product')}, Controls: {controls}"
    )

    if isinstance(screen_or_response, KioskResponse):
        return screen_or_response
    return screen_or_response, True


# ==========================================
# RESOLVE MEAL SWAP ITEM
# ==========================================

def resolve_meal_swap_item(query, active_meal: dict) -> dict:
    """
    Validate requested swap against the active meal's actual side and drink options.
    Supports:
    - Stable item ID (int or numeric string)
    - Item dict (e.g. {"id": 102} or {"name": "Cheesy Fries", "role": "side"})
    - Ordinals / option indices (e.g. "first", "second", "2nd", "option 2", "second side")
    - Item name (exact, substring, or alias)
    Returns:
    - {"success": True, "role": "drink"|"side", "item": item_dict} if valid and unambiguous.
    - {"success": False, "status": "ambiguous", "error": "..."} if multiple match.
    - {"success": False, "status": "unavailable", "error": "..."} if no match.
    """
    if query is None or query == "":
        return {"success": False, "status": "unavailable", "error": "No item specified for swap."}

    side_options = (active_meal or {}).get("side_options", []) or []
    drink_options = (active_meal or {}).get("drink_options", []) or []

    target_role = None
    target_id = None
    target_index = None

    # Handle dictionary query
    if isinstance(query, dict):
        target_role = query.get("role")
        target_id = query.get("id") or query.get("item_id")
        idx_val = query.get("index") or query.get("option_index")
        if idx_val is not None:
            try:
                target_index = int(idx_val)
            except (ValueError, TypeError):
                pass
        name_val = query.get("name") or query.get("item")
        q = str(name_val or (target_id if target_id is not None else "")).lower().strip()
    elif isinstance(query, int):
        target_id = query
        q = str(query)
    elif isinstance(query, str):
        q = query.lower().strip()
    else:
        q = str(query).lower().strip()

    # If target_id is provided, try exact ID match first
    if target_id is not None:
        target_id_str = str(target_id)
        id_sides = [s for s in side_options if str(s.get("id")) == target_id_str]
        id_drinks = [d for d in drink_options if str(d.get("id")) == target_id_str]
        if target_role == "side" and id_sides:
            return {"success": True, "role": "side", "item": id_sides[0]}
        if target_role == "drink" and id_drinks:
            return {"success": True, "role": "drink", "item": id_drinks[0]}
        if id_sides and not id_drinks:
            return {"success": True, "role": "side", "item": id_sides[0]}
        if id_drinks and not id_sides:
            return {"success": True, "role": "drink", "item": id_drinks[0]}
        if id_sides and id_drinks:
            return {
                "success": False,
                "status": "ambiguous",
                "error": f"Item ID {target_id} matches both a side and a drink. Please specify side or drink.",
            }

    # Extract explicit role prefixes from string
    if q.startswith("drink:"):
        target_role = "drink"
        q = q[len("drink:"):].strip()
    elif q.startswith("side:"):
        target_role = "side"
        q = q[len("side:"):].strip()
    elif "drink" in q and any(w in q for w in ["change", "swap", "switch", "replace"]):
        target_role = "drink"
    elif "side" in q and any(w in q for w in ["change", "swap", "switch", "replace"]):
        target_role = "side"

    # Also detect role keywords
    if "side" in q.split() or "sides" in q.split():
        target_role = "side"
    elif "drink" in q.split() or "drinks" in q.split() or "beverage" in q.split():
        target_role = "drink"

    # Check if string query is purely an item ID
    if q.isdigit():
        id_sides = [s for s in side_options if str(s.get("id")) == q]
        id_drinks = [d for d in drink_options if str(d.get("id")) == q]
        if target_role == "side" and id_sides:
            return {"success": True, "role": "side", "item": id_sides[0]}
        if target_role == "drink" and id_drinks:
            return {"success": True, "role": "drink", "item": id_drinks[0]}
        if id_sides and not id_drinks:
            return {"success": True, "role": "side", "item": id_sides[0]}
        if id_drinks and not id_sides:
            return {"success": True, "role": "drink", "item": id_drinks[0]}

    # Check ordinals and positional references
    ord_map = {
        "first": 0, "1st": 0, "#1": 0,
        "second": 1, "2nd": 1, "#2": 1,
        "third": 2, "3rd": 2, "#3": 2,
        "fourth": 3, "4th": 3, "#4": 3,
        "fifth": 4, "5th": 4, "#5": 4,
        "sixth": 5, "6th": 5, "#6": 5,
        "seventh": 6, "7th": 6, "#7": 6,
        "eighth": 7, "8th": 7, "#8": 7,
    }

    import re
    detected_idx = target_index
    if detected_idx is None:
        for ord_word, ord_idx in ord_map.items():
            if re.search(r"\b" + re.escape(ord_word) + r"\b", q):
                detected_idx = ord_idx
                break
        if detected_idx is None:
            m = re.search(r"\b(?:option|item|number|choice)\s+(\d+)\b", q)
            if m:
                detected_idx = int(m.group(1)) - 1

    if detected_idx is not None:
        role_to_check = target_role
        if not role_to_check:
            meal_stage = conversation_context.get("meal_stage")
            if meal_stage == "side_upgrade":
                role_to_check = "side"
            elif meal_stage == "drink_upgrade":
                role_to_check = "drink"

        if role_to_check == "side":
            if 0 <= detected_idx < len(side_options):
                return {"success": True, "role": "side", "item": side_options[detected_idx]}
            else:
                return {
                    "success": False,
                    "status": "unavailable",
                    "error": f"Side option {detected_idx + 1} is out of range. There are {len(side_options)} side options.",
                }
        elif role_to_check == "drink":
            if 0 <= detected_idx < len(drink_options):
                return {"success": True, "role": "drink", "item": drink_options[detected_idx]}
            else:
                return {
                    "success": False,
                    "status": "unavailable",
                    "error": f"Drink option {detected_idx + 1} is out of range. There are {len(drink_options)} drink options.",
                }
        else:
            side_valid = 0 <= detected_idx < len(side_options)
            drink_valid = 0 <= detected_idx < len(drink_options)
            if side_valid and not drink_valid:
                return {"success": True, "role": "side", "item": side_options[detected_idx]}
            if drink_valid and not side_valid:
                return {"success": True, "role": "drink", "item": drink_options[detected_idx]}
            if side_valid and drink_valid:
                return {
                    "success": False,
                    "status": "ambiguous",
                    "error": f"Option {detected_idx + 1} could refer to either a side ({side_options[detected_idx].get('name')}) or a drink ({drink_options[detected_idx].get('name')}). Please clarify whether you'd like the side or drink.",
                }

    for phrase in [
        "change drink to", "change side to", "swap drink to", "swap side to",
        "switch drink to", "switch side to", "replace drink with", "replace side with",
        "change to", "swap to", "switch to", "swap for", "switch for", "replace with",
        "i want a ", "i want an ", "i want some ", "i want ",
        "can i get a ", "can i get an ", "can i get some ", "can i get ",
        "give me a ", "give me an ", "give me some ", "give me ",
        "instead of ", "instead", "please",
    ]:
        q = q.replace(phrase, " ").strip()
    q = " ".join(q.split())

    def _matches_item(opt, search_str):
        opt_name = (opt.get("name") or "").lower().strip()
        if not opt_name or not search_str:
            return False
        if opt_name == search_str:
            return True
        opt_tokens = set(opt_name.split())
        search_tokens = set(search_str.split())
        if search_tokens.issubset(opt_tokens):
            return True
        if len(search_str) >= 4 and search_str in opt_name:
            return True
        if search_str == "coke" and "coca cola" in opt_name:
            return True
        return False

    matched_drinks = [opt for opt in drink_options if _matches_item(opt, q)] if target_role != "side" else []
    matched_sides = [opt for opt in side_options if _matches_item(opt, q)] if target_role != "drink" else []

    # If only matched drinks
    if matched_drinks and not matched_sides:
        if len(matched_drinks) == 1:
            return {"success": True, "role": "drink", "item": matched_drinks[0]}
        exact = [d for d in matched_drinks if (d.get("name") or "").lower().strip() == q]
        if len(exact) == 1:
            return {"success": True, "role": "drink", "item": exact[0]}
        names = ", ".join([d.get("name", "") for d in matched_drinks])
        return {
            "success": False,
            "status": "ambiguous",
            "error": f"Multiple drink options match '{query}': {names}. Please ask the customer which one they prefer.",
        }

    # If only matched sides
    if matched_sides and not matched_drinks:
        if len(matched_sides) == 1:
            return {"success": True, "role": "side", "item": matched_sides[0]}
        exact = [s for s in matched_sides if (s.get("name") or "").lower().strip() == q]
        if len(exact) == 1:
            return {"success": True, "role": "side", "item": exact[0]}
        names = ", ".join([s.get("name", "") for s in matched_sides])
        return {
            "success": False,
            "status": "ambiguous",
            "error": f"Multiple side options match '{query}': {names}. Please ask the customer which one they prefer.",
        }

    # If matched both
    if matched_drinks and matched_sides:
        names = ", ".join([d.get("name", "") for d in matched_drinks] + [s.get("name", "") for s in matched_sides])
        return {
            "success": False,
            "status": "ambiguous",
            "error": f"'{query}' could refer to either a side or a drink: {names}. Please ask the customer to clarify.",
        }

    # If matched neither
    avail_sides = ", ".join([s.get("name", "") for s in side_options]) or "none"
    avail_drinks = ", ".join([d.get("name", "") for d in drink_options]) or "none"
    return {
        "success": False,
        "status": "unavailable",
        "error": f"'{query}' is not an available option for this meal. Available sides: {avail_sides}. Available drinks: {avail_drinks}.",
    }


def resolve_cart_target(query, cart):
    """
    Deterministically resolves a target item query against the active cart.
    Returns (matched_item, matched_index, all_matching_items).
    - If exactly one item matches: returns (item, index, [item]).
    - If multiple items match: returns (None, None, [items...]) (ambiguous).
    - If no items match: returns (None, None, []).
    """
    if not cart:
        return None, None, []

    val_str = str(query or "").strip().lower()

    # 1. Fallback for null/none/it/empty query
    if not val_str or val_str in ("null", "none", "it", "this", "that", "the item"):
        if len(cart) == 1:
            return cart[0], 0, [cart[0]]
        return None, None, list(cart)

    # 2. Ordinals and numerical indices
    ordinals = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
    for idx, ord_word in enumerate(ordinals):
        if val_str == ord_word or val_str == f"{ord_word} item" or val_str == f"the {ord_word}" or val_str == f"the {ord_word} item":
            if idx < len(cart):
                return cart[idx], idx, [cart[idx]]
            return None, None, []

    # Numeric "1", "2", "#1", "item 1", etc.
    import re
    num_match = re.search(r"\b(\d+)\b", val_str)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(cart):
            return cart[idx], idx, [cart[idx]]

    # 3. Exact name match (case-insensitive)
    exact_matches = [(it, i) for i, it in enumerate(cart) if (it.get("name") or "").lower().strip() == val_str]
    if len(exact_matches) == 1:
        return exact_matches[0][0], exact_matches[0][1], [exact_matches[0][0]]
    elif len(exact_matches) > 1:
        return None, None, [m[0] for m in exact_matches]

    # 4. Normalized substring / containment match
    sub_matches = []
    for i, it in enumerate(cart):
        it_name = (it.get("name") or "").lower().strip()
        if val_str in it_name or it_name in val_str:
            sub_matches.append((it, i))

    if len(sub_matches) == 1:
        return sub_matches[0][0], sub_matches[0][1], [sub_matches[0][0]]
    elif len(sub_matches) > 1:
        return None, None, [m[0] for m in sub_matches]

    # 5. Token matching (tokens > 2 characters)
    tokens = [t for t in re.sub(r"[^a-z0-9\s]", "", val_str).split() if len(t) > 2]
    if tokens:
        token_matches = []
        for i, it in enumerate(cart):
            it_name = (it.get("name") or "").lower().strip()
            if any(t in it_name for t in tokens):
                token_matches.append((it, i))
        if len(token_matches) == 1:
            return token_matches[0][0], token_matches[0][1], [token_matches[0][0]]
        elif len(token_matches) > 1:
            return None, None, [m[0] for m in token_matches]

    return None, None, []


# ==========================================
# CREATE UI ACTION RESPONSE
# ==========================================

def create_ui_action(
    control,
    value=None,
    user_input=None,
    llm=None
):

    current_screen = conversation_context.get(
        "current_screen",
        ScreenTypes.CATEGORY_SELECTION
    )

    available_controls = conversation_context.get(
        "available_controls",
        []
    )

    ui_action = control

    # Target screen calculation
    target_screen = current_screen
    if control == "go_back":
        target_screen = ScreenTypes.CATEGORY_SELECTION
    elif control == "open_cart":
        target_screen = ScreenTypes.CART
    elif control == "select_product":
        target_screen = ScreenTypes.PRODUCT
        if value:
            conversation_context["selected_product"] = value
            conversation_context["last_item"] = value
            conversation_context["screen_quantity"] = 1
    elif control in ["select_meal", "accept_meal", "swap_meal_item"]:
        target_screen = ScreenTypes.MEAL_CONVERSION
    elif control in ["upgrade_to_meal", "set_quantity"]:
        target_screen = ScreenTypes.PRODUCT
    elif control in ["increase_quantity", "decrease_quantity"]:
        if current_screen == ScreenTypes.PRODUCT:
            target_screen = ScreenTypes.PRODUCT
        else:
            target_screen = ScreenTypes.CART
    elif control == "add_to_cart" and current_screen == ScreenTypes.MEAL_CONVERSION:
        target_screen = conversation_context.get("last_category_screen") or ScreenTypes.RECOMMENDED_BURGERS
    elif control in ["add_recommended", "select_payment", "confirm_order", "remove_item", "checkout"]:
        target_screen = ScreenTypes.CART

    # ==========================================
    # SEMANTIC FILTER → FRONTEND ACTION
    # ==========================================

    if control == "filter":

        if value == "veg":

            ui_action = "filter_veg"

        elif value == "non_veg":

            ui_action = "filter_non_veg"

        elif value == "both":

            ui_action = "filter_both"

        else:

            print(
                "UNKNOWN FILTER VALUE:",
                value
            )

            return None

    # ==========================================
    # NATURAL CASHIER RESPONSE
    # ==========================================

    message = None

    if user_input and llm:

        message = generate_cashier_response(
            user_input=user_input,
            screen_intent=type(
                "ScreenAction",
                (),
                {
                    "control": control,
                    "value": value
                }
            )(),
            current_screen=current_screen,
            available_controls=available_controls,
            llm=llm
        )

    # ==========================================
    # RETURN UI ACTION + SPOKEN RESPONSE
    # ==========================================

    data = {
        "ui_action": ui_action
    }
    if value is not None:
        data["value"] = value
    if control in ["select_meal", "accept_meal"] and conversation_context.get("active_meal"):
        data["meal"] = conversation_context.get("active_meal")
    elif control == "upgrade_to_meal":
        if conversation_context.get("meal_offer"):
            data["meal_offer"] = conversation_context.get("meal_offer")
        if conversation_context.get("meals"):
            data["meals"] = conversation_context.get("meals")
    elif control == "select_product" and value is not None:
        data["product"] = {"name": value}
    elif target_screen == ScreenTypes.PRODUCT and conversation_context.get("selected_product"):
        data["product"] = {"name": conversation_context.get("selected_product")}

    reply = KioskResponse(
        screen=target_screen,
        message=message,
        data=data
    )
    track_screen(reply)
    return reply


# ==========================================
# PARSE QUANTITY HELPER
# ==========================================

def parse_quantity(val, default=1):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return max(1, int(val))
    val_str = str(val).lower().strip()
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    import re
    match = re.search(r'\b(?:to\s+)?(\d+)\b', val_str)
    if match:
        try:
            return max(1, int(match.group(1)))
        except (ValueError, IndexError):
            pass
    for w, n in word_map.items():
        if re.search(rf'\b{w}\b', val_str):
            return n
    try:
        return max(1, int(val_str))
    except (ValueError, TypeError):
        return default


def parse_meal_split(value: str | None, original_quantity: int = 1) -> tuple[int, int]:
    """
    Parse the customer's split decision into (meals_count, burgers_count).
    Ensures total reflects customer's requested distribution.
    """
    if not value or str(value).strip().lower() in ["none", ""]:
        return (1, max(0, original_quantity - 1)) if original_quantity > 1 else (1, 0)

    val_str = str(value).lower().strip()
    import re

    word_to_num = {
        "zero": 0, "no": 0, "none": 0,
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "both": 2, "all": original_quantity
    }

    if "all" in val_str or val_str in ["both", "yes, all", "yes all", "all of them", "all meals", "all burgers"]:
        return (original_quantity, 0)

    meal_match = re.search(r"\b(\d+|zero|no|none|one|two|three|four|five|six|seven|eight|nine|ten|all)\s+(?:as\s+)?(?:meals?|combos?)\b", val_str)
    burger_match = re.search(r"\b(\d+|zero|no|none|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:as\s+|on\s+their\s+|other\s+|remaining\s+)*(?:burgers?|items?|standalone|regular|on\s+their\s+own)\b", val_str)

    meals_qty = None
    burgers_qty = None

    if meal_match:
        m_raw = meal_match.group(1)
        meals_qty = word_to_num.get(m_raw, int(m_raw) if m_raw.isdigit() else 1)

    if burger_match:
        b_raw = burger_match.group(1)
        burgers_qty = word_to_num.get(b_raw, int(b_raw) if b_raw.isdigit() else 0)

    if meals_qty is not None and burgers_qty is not None:
        return (meals_qty, burgers_qty)

    if meals_qty is not None and burgers_qty is None:
        rem = max(0, original_quantity - meals_qty)
        return (meals_qty, rem)

    if burgers_qty is not None and meals_qty is None:
        rem_meals = max(0, original_quantity - burgers_qty)
        return (rem_meals, burgers_qty)

    digits = re.findall(r"\b\d+\b", val_str)
    if digits:
        n = int(digits[0])
        if n == original_quantity:
            return (original_quantity, 0)
        elif n < original_quantity:
            return (n, original_quantity - n)
        else:
            return (n, 0)

    for word, num in word_to_num.items():
        if word in ["all", "both", "no", "none", "zero"]:
            continue
        if re.search(rf"\b{word}\b", val_str):
            if num <= original_quantity:
                return (num, original_quantity - num)

    return (1, max(0, original_quantity - 1)) if original_quantity > 1 else (1, 0)


def _resolve_context_product_id(prod_id, prod_name, conversation_context):
    if prod_id:
        return prod_id
    if not prod_name:
        return None
    try:
        from services.product_selector import resolve_product
        p_res = resolve_product(prod_name, conversation_context)
        if isinstance(p_res, dict) and p_res.get("status") == "selected" and p_res.get("product"):
            return p_res["product"].get("id")
    except Exception as ex:
        print(f"Error resolving product id for '{prod_name}': {ex}")
    return None


# ==========================================
# AGENT SCREEN ACTION TOOL
# ==========================================

def create_screen_action_tool(conversation_context):

    @tool
    def screen_action(
        control: str,
        value: str | None = None
    ):
        """
        Perform an action on the current kiosk screen.

        Use this when the customer's request can be fulfilled
        by one of the capabilities available on the current
        screen.

        The control must be one of the current screen's available
        UI capabilities.

        For the filter capability, value must be:
        veg, non_veg, or both.

        This tool operates the kiosk UI. It does not retrieve
        the menu or database contents.

        Args:
            control:
                The UI capability to perform.

            value:
                Optional value required by the capability.

        Returns:
            A small action result for the agent.
            The complete KioskResponse remains inside the
            application for the frontend.
        """

        current_screen = conversation_context.get(
            "current_screen",
            ScreenTypes.CATEGORY_SELECTION
        )

        available_controls = conversation_context.get(
            "available_controls",
            []
        )

        # ==========================================
        # VALIDATE CURRENT SCREEN
        # ==========================================

        if not current_screen:
            err = "No current kiosk screen is available."
            conversation_context["_last_action_rejected"] = {
                "control": control,
                "error": err
            }
            return {
                "success": False,
                "error": err
            }

        # Normalize accept_meal with size to select_meal
        if control == "accept_meal":
            control = "select_meal"
            if not value:
                value = "medium"

        # Normalize checkout request from non-cart screen with active cart items to open_cart
        if control == "checkout" and current_screen != ScreenTypes.CART:
            if conversation_context.get("cart"):
                control = "open_cart"

        # ==========================================
        # VALIDATE ADD TO CART
        # ==========================================
        if control == "add_to_cart":
            active_product = conversation_context.get("selected_product")
            if current_screen == ScreenTypes.MEAL_CONVERSION:
                pass
            elif current_screen != ScreenTypes.PRODUCT or not active_product:
                err = (
                    f"Action 'add_to_cart' cannot be performed because current screen is '{current_screen}' "
                    f"and no active meal or product is actively selected on screen. The action was NOT executed. "
                    "Do NOT tell the customer an item was added to the cart."
                )
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                    "available_controls": available_controls,
                }

        # ==========================================
        # VALIDATE CONTROL
        # ==========================================

        if control not in available_controls:
            err = (
                f"Control '{control}' is not available on the current screen '{current_screen}'. "
                f"Available controls on this screen: {available_controls}. "
                "The action was NOT executed. Do NOT tell the customer this action was completed or to tap an unavailable button."
            )
            conversation_context["_last_action_rejected"] = {
                "control": control,
                "error": err,
            }
            return {
                "success": False,
                "error": err,
                "available_controls": available_controls
            }

        # ==========================================
        # NORMALIZE FILTER VALUE
        # ==========================================

        if control == "filter":

            if value:

                value = (
                    value
                    .lower()
                    .replace(" ", "_")
                    .strip()
                )

            if value not in [
                "veg",
                "non_veg",
                "both"
            ]:
                err = "Filter value must be veg, non_veg, or both."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err
                }

        # ==========================================
        # VALIDATE UPGRADE TO MEAL (PRODUCT SCREEN)
        # ==========================================

        if control == "upgrade_to_meal":
            if current_screen != ScreenTypes.PRODUCT:
                err = f"Control 'upgrade_to_meal' is only available on the Product page (current screen: '{current_screen}')."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            prod_name = conversation_context.get("selected_product")
            prod_id = _resolve_context_product_id(
                conversation_context.get("selected_product_id"),
                prod_name,
                conversation_context,
            )

            if not prod_id:
                err = "No product is actively selected on screen."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            from services.meal_service import get_meal_options
            pref = conversation_context.get("food_preference")
            cart = conversation_context.get("cart", [])
            offer = get_meal_options(prod_id, food_preference=pref, cart=cart)

            if not offer or not offer.get("is_meal_available"):
                err = f"'{prod_name or 'This item'}' cannot be converted into a meal combo."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            meals = offer.get("meals") or {}
            avail_sizes = []
            if meals.get("medium"):
                avail_sizes.append("medium")
            if meals.get("large"):
                avail_sizes.append("large")

            if not avail_sizes:
                err = f"No meal sizes are available for '{prod_name or 'this item'}'."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            meal_offer = {
                "is_open": True,
                "product_id": prod_id,
                "product_name": prod_name,
                "available_sizes": avail_sizes,
            }
            conversation_context["meal_offer"] = meal_offer
            conversation_context["meal_flow"] = {"item_id": prod_id, "status": "pending"}
            conversation_context["meals"] = meals

            avail_ctrls = conversation_context.get("available_controls", [])
            for mc in ["select_meal", "decline_meal"]:
                if mc not in avail_ctrls:
                    avail_ctrls.append(mc)
            conversation_context["available_controls"] = avail_ctrls

            response = create_ui_action(control="upgrade_to_meal")
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response

            return {
                "success": True,
                "control": "upgrade_to_meal",
                "product_name": prod_name,
                "available_sizes": avail_sizes,
                "message": f"Opened meal options for {prod_name}. Available sizes: {', '.join(avail_sizes)}.",
            }

        # ==========================================
        # VALIDATE MEAL CONTROLS
        # ==========================================

        if control == "select_meal":
            if not value:
                err = "Customer must choose between 'medium' or 'large' meal size."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }

            val_norm = value.lower().replace(" meal", "").strip()
            if val_norm not in ["medium", "large"]:
                err = f"Invalid meal size '{value}'. Must be 'medium' or 'large'."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }
            value = val_norm

            meal_offer = conversation_context.get("meal_offer") or {}
            if current_screen == ScreenTypes.PRODUCT:
                if not meal_offer.get("is_open"):
                    prod_name = conversation_context.get("selected_product")
                    prod_id = _resolve_context_product_id(
                        conversation_context.get("selected_product_id"),
                        prod_name,
                        conversation_context,
                    )
                    from services.meal_service import get_meal_options
                    pref = conversation_context.get("food_preference")
                    cart = conversation_context.get("cart", [])
                    offer = get_meal_options(prod_id, food_preference=pref, cart=cart) if prod_id else None
                    if not offer or not offer.get("is_meal_available"):
                        err = f"'{prod_name or 'This item'}' cannot be converted into a meal combo."
                        conversation_context["_last_action_rejected"] = {
                            "control": control,
                            "error": err,
                        }
                        return {
                            "success": False,
                            "error": err,
                        }
                    meals = offer.get("meals") or {}
                    avail = [s for s in ["medium", "large"] if meals.get(s)]
                    if value not in avail:
                        err = f"Size '{value}' is not available. Available sizes: {', '.join(avail)}."
                        conversation_context["_last_action_rejected"] = {
                            "control": control,
                            "error": err,
                        }
                        return {
                            "success": False,
                            "error": err,
                            "available_sizes": avail,
                        }
                    conversation_context["meal_offer"] = {
                        "is_open": True,
                        "product_id": prod_id,
                        "product_name": prod_name,
                        "available_sizes": avail,
                    }
                else:
                    avail = [s.lower() for s in meal_offer.get("available_sizes", [])]
                    if avail and value not in avail:
                        err = f"Size '{value}' is not available. Available sizes: {', '.join(avail)}."
                        conversation_context["_last_action_rejected"] = {
                            "control": control,
                            "error": err,
                        }
                        return {
                            "success": False,
                            "error": err,
                            "available_sizes": avail,
                        }
            elif current_screen == ScreenTypes.MEAL_CONVERSION:
                pass
            else:
                err = f"Control 'select_meal' is not available on current screen '{current_screen}'."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            active_meal_raw = conversation_context.get("active_meal") or {}
            burger_dict = active_meal_raw.get("burger") or {} if isinstance(active_meal_raw, dict) else {}
            if not isinstance(burger_dict, dict):
                burger_dict = {}

            prod_name = (
                meal_offer.get("product_name")
                or conversation_context.get("selected_product")
                or burger_dict.get("name")
            )
            raw_id = (
                meal_offer.get("product_id")
                or conversation_context.get("selected_product_id")
                or burger_dict.get("id")
            )
            prod_id = _resolve_context_product_id(raw_id, prod_name, conversation_context)

            from services.meal_service import build_meal
            pref = conversation_context.get("food_preference")
            cart = conversation_context.get("cart", [])
            meal_data = build_meal(prod_id, value, food_preference=pref, cart=cart) if prod_id else None

            if not meal_data:
                if conversation_context.get("active_meal"):
                    meal_data = dict(conversation_context["active_meal"])
                    meal_data["size"] = value
                else:
                    err = f"Could not build {value} meal for product."
                    conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                    return {"success": False, "error": err}

            size_upgrade_available = False
            size_upgrade_price = 0
            larger_size = None

            is_keeping_medium = (
                current_screen == ScreenTypes.MEAL_CONVERSION
                and value == "medium"
                and conversation_context.get("meal_stage") == "size_upgrade"
            )

            if value == "medium" and not is_keeping_medium and prod_id:
                try:
                    larger_meal = build_meal(prod_id, "large", food_preference=pref, cart=cart)
                    if larger_meal:
                        diff = larger_meal.get("meal_price", 0) - meal_data.get("meal_price", 0)
                        if diff > 0:
                            size_upgrade_available = True
                            diff_f = float(diff)
                            size_upgrade_price = int(diff_f) if diff_f.is_integer() else round(diff_f, 2)
                            larger_size = "large"
                except Exception as ex:
                    print(f"Error checking large meal upgrade: {ex}")

            side_options = meal_data.get("side_options", []) or []
            drink_options = meal_data.get("drink_options", []) or []
            upgrade_sides = [s for s in side_options if not s.get("is_default")]
            upgrade_drinks = [d for d in drink_options if not d.get("is_default")]

            default_side = next((s for s in side_options if s.get("is_default")), side_options[0] if side_options else meal_data.get("side"))
            default_drink = next((d for d in drink_options if d.get("is_default")), drink_options[0] if drink_options else meal_data.get("drink"))

            rec_side = upgrade_sides[0] if upgrade_sides else None
            rec_drink = upgrade_drinks[0] if upgrade_drinks else None

            existing_side = conversation_context.get("active_meal", {}).get("selected_side")
            existing_drink = conversation_context.get("active_meal", {}).get("selected_drink")
            selected_side = existing_side if existing_side else default_side
            selected_drink = existing_drink if existing_drink else default_drink
            meal_data["selected_side"] = selected_side
            meal_data["selected_drink"] = selected_drink

            if size_upgrade_available:
                stage = "size_upgrade"
            elif upgrade_sides and not conversation_context.get("meal_side_decision"):
                stage = "side_upgrade"
            elif upgrade_drinks and not conversation_context.get("meal_drink_decision"):
                stage = "drink_upgrade"
            else:
                stage = "meal_confirmed"

            conversation_context["active_meal"] = meal_data
            conversation_context["meal_stage"] = stage
            conversation_context["meal_size_upgrade_available"] = size_upgrade_available
            conversation_context["meal_size_upgrade_price"] = size_upgrade_price
            conversation_context["current_screen"] = ScreenTypes.MEAL_CONVERSION
            conversation_context["available_controls"] = get_screen_controls(ScreenTypes.MEAL_CONVERSION)

            if "meal_offer" in conversation_context and isinstance(conversation_context["meal_offer"], dict):
                conversation_context["meal_offer"]["is_open"] = False

            response = create_ui_action(
                control="select_meal",
                value={
                    "size": value,
                    "meal": meal_data,
                    "seq": conversation_context.get("_screen_seq", 0),
                    "session_id": conversation_context.get("session_id", "default"),
                },
            )
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response

            return {
                "success": True,
                "screen": ScreenTypes.MEAL_CONVERSION,
                "control": "select_meal",
                "value": value,
                "burger": meal_data.get("burger", {}).get("name") if isinstance(meal_data.get("burger"), dict) else str(meal_data.get("burger") or ""),
                "meal_size": value,
                "meal_price": meal_data.get("meal_price"),
                "size_upgrade_available": size_upgrade_available,
                "size_upgrade_price": size_upgrade_price,
                "larger_size": larger_size,
                "default_side": default_side.get("name") if isinstance(default_side, dict) else (str(default_side) if default_side else None),
                "recommended_side": rec_side.get("name") if isinstance(rec_side, dict) else None,
                "side_upgrade_price": int(rec_side.get("extra_price", 0)) if isinstance(rec_side, dict) and rec_side.get("extra_price") else 0,
                "default_drink": default_drink.get("name") if isinstance(default_drink, dict) else (str(default_drink) if default_drink else None),
                "recommended_drink": rec_drink.get("name") if isinstance(rec_drink, dict) else None,
                "drink_upgrade_price": int(rec_drink.get("extra_price", 0)) if isinstance(rec_drink, dict) and rec_drink.get("extra_price") else 0,
                "meal_stage": stage,
            }

        if control == "decline_meal":
            meal_offer = conversation_context.get("meal_offer", {})
            meal_flow = conversation_context.get("meal_flow")
            prod_id = value or meal_offer.get("product_id") or (meal_flow.get("item_id") if meal_flow else None)
            if prod_id is not None:
                if "declined_meal_products" not in conversation_context:
                    conversation_context["declined_meal_products"] = []
                if str(prod_id) not in [str(x) for x in conversation_context["declined_meal_products"]]:
                    conversation_context["declined_meal_products"].append(prod_id)
            if meal_offer and (prod_id is None or meal_offer.get("product_id") is None or str(meal_offer.get("product_id")) == str(prod_id)):
                meal_offer["is_open"] = False
                if "available_controls" in conversation_context:
                    conversation_context["available_controls"] = [
                        c for c in conversation_context["available_controls"]
                        if c not in ["select_meal", "decline_meal", "accept_meal"]
                    ]
            if meal_flow and (prod_id is None or meal_flow.get("item_id") is None or str(meal_flow.get("item_id")) == str(prod_id)):
                meal_flow["status"] = "declined"
            if current_screen == ScreenTypes.PRODUCT:
                conversation_context["meal_declined_pending_add"] = True

            response = create_ui_action(control="decline_meal", value=value)
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response

            if current_screen == ScreenTypes.PRODUCT:
                orig_qty = conversation_context.get("original_requested_quantity", 1)
                num_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
                qty_word = num_words.get(orig_qty, str(orig_qty))
                prod_name = conversation_context.get("selected_product", "burger")
                msg = (
                    f"No problem. Shall I add the {qty_word} burgers to your cart?"
                    if orig_qty > 1
                    else f"No problem. Shall I add the {prod_name} to your cart?"
                )
                return {
                    "success": True,
                    "screen": response.screen,
                    "control": "decline_meal",
                    "product_name": prod_name,
                    "quantity": orig_qty,
                    "meal_declined_pending_add": True,
                    "message": msg,
                }
            elif current_screen == ScreenTypes.MEAL_CONVERSION:
                conversation_context["active_meal"] = None
                conversation_context.pop("meal_stage", None)
                conversation_context.pop("meal_side_decision", None)
                conversation_context.pop("meal_drink_decision", None)
                return {
                    "success": True,
                    "screen": response.screen,
                    "control": "decline_meal",
                    "message": "Meal cancelled.",
                }

        # ==========================================
        # VALIDATE SWAP MEAL ITEM
        # ==========================================
        if control == "swap_meal_item":
            active_meal = conversation_context.get("active_meal")
            if current_screen != ScreenTypes.MEAL_CONVERSION or not active_meal:
                err = (
                    f"Action 'swap_meal_item' cannot be performed because current screen is '{current_screen}' "
                    "and no active meal customization is in progress. The action was NOT executed."
                )
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                    "available_controls": available_controls,
                }

            if not value:
                err = "Please specify which side or drink you would like to swap."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }

            match_res = resolve_meal_swap_item(value, active_meal)
            if not match_res.get("success"):
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": match_res.get("error"),
                }
                return match_res

            role = match_res["role"]
            target_item = match_res["item"]
            screen_seq = conversation_context.get("_screen_seq", 0)
            session_id = conversation_context.get("session_id", "default")

            target_payload = {
                "role": role,
                "item": target_item,
                "seq": screen_seq,
                "session_id": session_id,
            }

            response = create_ui_action(
                control="swap_meal_item",
                value=target_payload,
            )

            if response is None:
                err = "The kiosk could not perform this action."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {
                    "success": False,
                    "error": err,
                }

            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response

            if role == "side":
                conversation_context["meal_side_decision"] = target_item.get("name")
                conversation_context["meal_stage"] = "drink_upgrade"
            elif role == "drink":
                conversation_context["meal_drink_decision"] = target_item.get("name")
                orig_qty = conversation_context.get("original_requested_quantity", 1)
                if orig_qty > 1:
                    conversation_context["meal_stage"] = "split_decision"
                else:
                    conversation_context["meal_stage"] = "meal_confirmed"

            return {
                "success": True,
                "control": "swap_meal_item",
                "role": role,
                "item": target_item.get("name"),
                "item_id": target_item.get("id"),
                "extra_price": target_item.get("extra_price", 0),
            }

        # ==========================================
        # VALIDATE ADD RECOMMENDED (CART SCREEN)
        # ==========================================
        if control == "add_recommended":
            if current_screen != ScreenTypes.CART:
                err = f"Action 'add_recommended' is only available on the Cart screen (current screen: '{current_screen}')."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            if not value:
                err = "Please specify which recommended item you would like to add."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            recs = conversation_context.get("checkout_recommendations", [])
            val_clean = str(value).lower().strip()
            matched_rec = None
            for r in recs:
                r_name = (r.get("name") or "").lower().strip()
                if r_name == val_clean or val_clean in r_name or r_name in val_clean:
                    matched_rec = r
                    break

            item_to_add = matched_rec.get("name") if matched_rec else value
            from services.cart_service import add_item as cart_add_item
            cart_res = cart_add_item(item_to_add, quantity=1)
            if not cart_res.get("success"):
                err = cart_res.get("message", f"Failed to add {item_to_add} to cart.")
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            conversation_context["last_added_recommendation"] = item_to_add
            conversation_context["cart_stage"] = "review"

            response = create_ui_action(
                control="add_recommended",
                value={"name": item_to_add, "cart": cart_res},
            )
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            return {
                "success": True,
                "item": item_to_add,
                "subtotal": cart_res.get("subtotal"),
                "total": cart_res.get("total"),
                "itemCount": cart_res.get("itemCount"),
            }

        # ==========================================
        # VALIDATE SELECT PAYMENT (CART SCREEN)
        # ==========================================
        if control == "select_payment":
            if current_screen != ScreenTypes.CART:
                err = f"Action 'select_payment' is only available on the Cart screen (current screen: '{current_screen}')."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            val_norm = str(value or "").lower().strip()
            payment_method = None
            if "upi" in val_norm:
                payment_method = "upi"
            elif "card" in val_norm:
                payment_method = "card"
            elif "cash" in val_norm:
                payment_method = "cash"

            if not payment_method:
                err = f"Invalid payment method '{value}'. Please choose UPI, Card, or Cash."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            conversation_context["selected_payment"] = payment_method
            conversation_context["cart_stage"] = "order_confirmation"

            response = create_ui_action(
                control="select_payment",
                value=payment_method,
            )
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            return {
                "success": True,
                "payment_method": payment_method,
                "total": sum(it.get("subtotal", 0) for it in conversation_context.get("cart", [])),
                "message": f"{payment_method.upper()} payment method selected.",
            }

        # ==========================================
        # VALIDATE CONFIRM ORDER (CART SCREEN)
        # ==========================================
        if control == "confirm_order":
            if current_screen != ScreenTypes.CART:
                err = f"Action 'confirm_order' is only available on the Cart screen (current screen: '{current_screen}')."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            cart = conversation_context.get("cart", [])
            if not cart:
                err = "Cannot place order: Cart is empty."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            payment_method = conversation_context.get("selected_payment")
            if not payment_method:
                err = "Please select a payment method (UPI, Card, or Cash) before placing the order."
                conversation_context["_last_action_rejected"] = {
                    "control": control,
                    "error": err,
                }
                return {"success": False, "error": err}

            response = create_ui_action(
                control="confirm_order",
                value={"payment_method": payment_method},
            )
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            return {
                "success": True,
                "status": "order_confirmed",
                "payment_method": payment_method,
                "total": sum(it.get("subtotal", 0) for it in cart),
                "message": "Order confirmed and placement initiated.",
            }

        # ==========================================
        # PRODUCT SCREEN QUANTITY CONTROLS
        # ==========================================
        if control in ["set_quantity", "increase_quantity", "decrease_quantity"] and current_screen == ScreenTypes.PRODUCT:
            active_product = conversation_context.get("selected_product")
            if not active_product:
                err = f"No product is actively selected on screen to perform '{control}'."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            from repositories.menu_repository import get_product
            prod = get_product(active_product)
            stock = prod.get("stock") if prod else None

            if control == "set_quantity":
                target_qty = parse_quantity(value, default=1)
                capped = False
                if stock is not None:
                    stock_int = int(stock)
                    if target_qty > stock_int:
                        target_qty = stock_int
                        capped = True
                conversation_context["screen_quantity"] = target_qty
                response = create_ui_action(control="set_quantity", value=str(target_qty))
                response.data["quantity"] = target_qty
                response.data["available_stock"] = stock
                response.data["capped"] = capped
                conversation_context["_last_action_rejected"] = None
                conversation_context["_last_kiosk_response"] = response
                return {
                    "success": True,
                    "screen": response.screen,
                    "control": "set_quantity",
                    "quantity": target_qty,
                    "available_stock": stock,
                    "capped": capped,
                    "product_name": active_product,
                    "message": (
                        f"Set quantity to {target_qty}."
                        if not capped
                        else f"Only {stock} available in stock. Set quantity to {target_qty}."
                    ),
                }

            elif control == "increase_quantity":
                val_str = str(value or "").lower().strip()
                if "to " in val_str or val_str.startswith("to"):
                    target_qty = parse_quantity(value, default=1)
                    capped = False
                    if stock is not None:
                        stock_int = int(stock)
                        if target_qty > stock_int:
                            target_qty = stock_int
                            capped = True
                    conversation_context["screen_quantity"] = target_qty
                    response = create_ui_action(control="set_quantity", value=str(target_qty))
                    response.data["quantity"] = target_qty
                    response.data["available_stock"] = stock
                    response.data["capped"] = capped
                    conversation_context["_last_action_rejected"] = None
                    conversation_context["_last_kiosk_response"] = response
                    return {
                        "success": True,
                        "screen": response.screen,
                        "control": "set_quantity",
                        "quantity": target_qty,
                        "available_stock": stock,
                        "capped": capped,
                        "product_name": active_product,
                        "message": (
                            f"Set quantity to {target_qty}."
                            if not capped
                            else f"Only {stock} available in stock. Set quantity to {target_qty}."
                        ),
                    }
                else:
                    current_qty = conversation_context.get("screen_quantity", 1)
                    delta = parse_quantity(value, default=1)
                    target_qty = current_qty + delta
                    capped = False
                    if stock is not None:
                        stock_int = int(stock)
                        if target_qty > stock_int:
                            target_qty = stock_int
                            capped = True
                    conversation_context["screen_quantity"] = target_qty
                    response = create_ui_action(control="increase_quantity", value=str(delta))
                    response.data["quantity"] = target_qty
                    response.data["delta"] = delta
                    response.data["available_stock"] = stock
                    response.data["capped"] = capped
                    conversation_context["_last_action_rejected"] = None
                    conversation_context["_last_kiosk_response"] = response
                    return {
                        "success": True,
                        "screen": response.screen,
                        "control": "increase_quantity",
                        "quantity": target_qty,
                        "delta": delta,
                        "available_stock": stock,
                        "capped": capped,
                        "product_name": active_product,
                        "message": (
                            f"Increased quantity to {target_qty}."
                            if not capped
                            else f"Only {stock} available in stock. Quantity is at the maximum of {target_qty}."
                        ),
                    }

            elif control == "decrease_quantity":
                current_qty = conversation_context.get("screen_quantity", 1)
                delta = parse_quantity(value, default=1)
                target_qty = max(1, current_qty - delta)
                conversation_context["screen_quantity"] = target_qty
                response = create_ui_action(control="decrease_quantity", value=str(delta))
                response.data["quantity"] = target_qty
                response.data["delta"] = delta
                conversation_context["_last_action_rejected"] = None
                conversation_context["_last_kiosk_response"] = response
                return {
                    "success": True,
                    "screen": response.screen,
                    "control": "decrease_quantity",
                    "quantity": target_qty,
                    "delta": delta,
                    "product_name": active_product,
                    "message": f"Decreased quantity to {target_qty}.",
                }

        # ==========================================
        # PRODUCT SCREEN ADD TO CART (AUTHORITATIVE MUTATION)
        # ==========================================
        if control == "add_to_cart" and current_screen == ScreenTypes.PRODUCT:
            active_product = conversation_context.get("selected_product")
            if not active_product:
                err = "No product is actively selected on screen."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            # Guard: Never add originally requested burgers to the cart before the meal-upgrade
            # decision and customization flow is complete.
            meal_offer = conversation_context.get("meal_offer")
            if (
                isinstance(meal_offer, dict)
                and meal_offer.get("is_open")
                and not conversation_context.get("meal_declined_pending_add")
            ):
                err = (
                    "A meal upgrade offer is currently open on screen. "
                    "Cannot add burgers to cart before the customer decides on the meal offer. "
                    "Ask: 'Would you like to make that a meal?'"
                )
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {
                    "success": False,
                    "error": err,
                    "pending_meal_offer": True,
                    "available_controls": available_controls,
                }

            req_qty = parse_quantity(value, default=conversation_context.get("screen_quantity", 1))

            from services.cart_service import add_item as cart_add_item
            idempotency_key = conversation_context.get("current_interaction_id") or conversation_context.get("current_idempotency_key")
            cart_res = cart_add_item(active_product, quantity=req_qty, idempotency_key=idempotency_key)

            if not cart_res.get("success"):
                err = cart_res.get("message") or f"Could not add {active_product} to cart."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {
                    "success": False,
                    "error": err,
                    "available_stock": cart_res.get("available_stock"),
                    "quantity_added": 0,
                    "available_controls": available_controls,
                }

            qty_added = cart_res.get("quantity_added", req_qty)
            partially_added = cart_res.get("partially_added", False)
            avail_stock = cart_res.get("available_stock")

            response = create_ui_action(control="add_to_cart", value=str(qty_added))
            response.data["quantity_added"] = qty_added
            response.data["requested_quantity"] = req_qty
            response.data["partially_added"] = partially_added
            response.data["available_stock"] = avail_stock
            response.data["cart"] = cart_res.get("cart", [])
            response.data["total"] = cart_res.get("total", 0)
            response.data["itemCount"] = cart_res.get("itemCount", 0)

            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            conversation_context["screen_quantity"] = 1
            conversation_context.pop("meal_declined_pending_add", None)
            conversation_context.pop("pending_quantity", None)
            conversation_context.pop("pending_product", None)
            conversation_context.pop("pending_product_id", None)
            conversation_context["original_requested_quantity"] = 1

            # Fulfill matching pending items
            pending_items = conversation_context.get("pending_items")
            committed_item = cart_res.get("item") or {}
            committed_name = (committed_item.get("name") or active_product or "").lower()
            committed_id = committed_item.get("id")
            if isinstance(pending_items, list):
                for p in pending_items:
                    p_name = (p.get("name") or "").lower()
                    name_matches = bool(p_name and (p_name == committed_name))
                    id_matches = bool(committed_id is not None and str(p.get("product_id")) == str(committed_id))
                    if (name_matches or id_matches) and not p.get("fulfilled"):
                        p["fulfilled_quantity"] = p.get("fulfilled_quantity", 0) + qty_added
                        if p["fulfilled_quantity"] >= p.get("quantity", 1):
                            p["fulfilled"] = True

            return {
                "success": True,
                "screen": response.screen,
                "control": "add_to_cart",
                "item": active_product,
                "is_meal": False,
                "quantity_added": qty_added,
                "requested_quantity": req_qty,
                "partially_added": partially_added,
                "available_stock": avail_stock,
                "cart": cart_res.get("cart", []),
                "total": cart_res.get("total", 0),
                "itemCount": cart_res.get("itemCount", 0),
                "message": (
                    f"Added {qty_added} {active_product} to cart."
                    if not partially_added
                    else f"Only {qty_added} in stock. Added {qty_added} {active_product} to cart."
                ),
            }

        # ==========================================
        # MEAL CONVERSION ADD TO CART (AUTHORITATIVE MUTATION)
        # ==========================================
        if control == "add_to_cart" and current_screen == ScreenTypes.MEAL_CONVERSION:
            active_meal = conversation_context.get("active_meal")
            if not active_meal:
                err = "No active meal is being customized."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            orig_qty = conversation_context.get("original_requested_quantity", 1)
            meal_stage = conversation_context.get("meal_stage")
            if orig_qty > 1 and meal_stage in ["size_upgrade", "side_upgrade", "drink_upgrade"]:
                err = (
                    "Meal customization is not yet complete. Please complete the side and drink "
                    "customization before resolving the remaining burgers."
                )
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {
                    "success": False,
                    "error": err,
                    "available_controls": available_controls,
                }

            meals_qty, burgers_qty = parse_meal_split(value, orig_qty)

            burger_info = active_meal.get("burger", {})
            burger_name = burger_info.get("name") if isinstance(burger_info, dict) else str(burger_info or "")

            from repositories.menu_repository import get_product
            burger_prod = get_product(burger_name) if burger_name else None
            burger_stock = burger_prod.get("stock") if burger_prod else None

            total_burgers_needed = meals_qty + burgers_qty
            if burger_stock is not None and total_burgers_needed > burger_stock:
                err = f"Only {burger_stock} {burger_name} available in stock. Cannot add {total_burgers_needed}."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {
                    "success": False,
                    "error": err,
                    "available_stock": burger_stock,
                    "quantity_added": 0,
                    "available_controls": available_controls,
                }

            from services.cart_service import commit_cart_transaction
            ops = []
            if meals_qty > 0:
                meal_to_add = dict(active_meal)
                sel_side = active_meal.get("selected_side") or active_meal.get("side")
                side_dec = conversation_context.get("meal_side_decision")
                if side_dec and isinstance(active_meal.get("side_options"), list):
                    for s_opt in active_meal["side_options"]:
                        if s_opt.get("name", "").lower() == side_dec.lower():
                            sel_side = s_opt
                            break
                meal_to_add["side"] = sel_side

                sel_drink = active_meal.get("selected_drink") or active_meal.get("drink")
                drink_dec = conversation_context.get("meal_drink_decision")
                if drink_dec and isinstance(active_meal.get("drink_options"), list):
                    for d_opt in active_meal["drink_options"]:
                        if d_opt.get("name", "").lower() == drink_dec.lower():
                            sel_drink = d_opt
                            break
                meal_to_add["drink"] = sel_drink
                ops.append({"type": "meal", "meal": meal_to_add, "quantity": meals_qty})

            if burgers_qty > 0:
                ops.append({"type": "item", "item_name": burger_name, "quantity": burgers_qty})

            idempotency_key = conversation_context.get("current_interaction_id") or conversation_context.get("current_idempotency_key")
            cart_res = commit_cart_transaction(ops, idempotency_key=idempotency_key)

            if not cart_res.get("success"):
                err = cart_res.get("error") or cart_res.get("message") or "Failed to add meal items to cart."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {
                    "success": False,
                    "error": err,
                    "available_stock": cart_res.get("available_stock"),
                    "quantity_added": 0,
                    "available_controls": available_controls,
                }

            response = create_ui_action(control="add_to_cart", value=value)
            response.data["meals_added"] = meals_qty
            response.data["burgers_added"] = burgers_qty
            response.data["cart"] = cart_res.get("cart", [])
            response.data["total"] = cart_res.get("total", 0)
            response.data["itemCount"] = cart_res.get("itemCount", 0)

            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            conversation_context["active_meal"] = None
            conversation_context.pop("meal_stage", None)
            conversation_context.pop("meal_side_decision", None)
            conversation_context.pop("meal_drink_decision", None)
            conversation_context.pop("meal_size_upgrade_available", None)
            conversation_context.pop("meal_size_upgrade_price", None)
            conversation_context.pop("meal_offer", None)
            conversation_context.pop("pending_quantity", None)
            conversation_context.pop("pending_product", None)
            conversation_context.pop("pending_product_id", None)
            conversation_context["original_requested_quantity"] = 1
            conversation_context["screen_quantity"] = 1

            # Fulfill matching pending items
            pending_items = conversation_context.get("pending_items")
            if isinstance(pending_items, list):
                total_fulfilled = meals_qty + burgers_qty
                for p in pending_items:
                    if (
                        p.get("name") == burger_name
                        or str(p.get("product_id")) == str((burger_info.get("id") if isinstance(burger_info, dict) else None))
                    ) and not p.get("fulfilled"):
                        p["fulfilled_quantity"] = p.get("fulfilled_quantity", 0) + total_fulfilled
                        if p["fulfilled_quantity"] >= p.get("quantity", 1):
                            p["fulfilled"] = True

            size = active_meal.get("size", "Medium")
            sel_side = active_meal.get("selected_side") or active_meal.get("side", {})
            side_name = sel_side.get("name") if isinstance(sel_side, dict) else str(sel_side or "")
            sel_drink = active_meal.get("selected_drink") or active_meal.get("drink", {})
            drink_name = sel_drink.get("name") if isinstance(sel_drink, dict) else str(sel_drink or "")

            if meals_qty > 0 and burgers_qty > 0:
                msg = f"Added {meals_qty} {size} {burger_name} meal{'s' if meals_qty > 1 else ''} and {burgers_qty} {burger_name} burger{'s' if burgers_qty > 1 else ''} to cart."
            elif meals_qty > 0:
                msg = f"Added {meals_qty} {size} {burger_name} meal{'s' if meals_qty > 1 else ''} to cart."
            else:
                msg = f"Added {burgers_qty} {burger_name} burger{'s' if burgers_qty > 1 else ''} to cart."

            return {
                "success": True,
                "screen": response.screen,
                "control": "add_to_cart",
                "item": burger_name,
                "is_meal": meals_qty > 0,
                "meals_added": meals_qty,
                "burgers_added": burgers_qty,
                "size": size,
                "side": side_name,
                "drink": drink_name,
                "cart": cart_res.get("cart", []),
                "total": cart_res.get("total", 0),
                "itemCount": cart_res.get("itemCount", 0),
                "message": msg,
            }

        # ==========================================
        # VALIDATE CART ITEM UPDATES (CART SCREEN)
        # ==========================================
        if control in ["increase_quantity", "decrease_quantity", "remove_item"]:
            if current_screen != ScreenTypes.CART:
                err = f"Control '{control}' is only available on the Cart screen."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            cart = conversation_context.get("cart", [])
            if not cart:
                err = "Cannot update cart: Cart is currently empty."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            target_item, target_idx, matching_items = resolve_cart_target(value, cart)

            if len(matching_items) > 1:
                item_names = [it.get("name", "Unknown") for it in matching_items]
                act_word = "update" if control == "increase_quantity" else ("decrease" if control == "decrease_quantity" else "remove")
                err = f"Multiple items match '{value}': {', '.join(item_names)}. Please ask the customer to clarify which item they would like to {act_word}."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {
                    "success": False,
                    "ambiguous": True,
                    "matching_items": item_names,
                    "error": err,
                }

            if target_item is None or target_idx is None:
                cart_items = [it.get("name", "Unknown") for it in cart]
                err = f"Could not find '{value}' in the cart. Current cart items: {', '.join(cart_items)}."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            from services.cart_service import update_cart_item
            act_map = {
                "increase_quantity": "increase",
                "decrease_quantity": "decrease",
                "remove_item": "remove",
            }
            cart_res = update_cart_item(target_idx, act_map[control])

            response = create_ui_action(
                control,
                value={
                    "item_name": target_item.get("name"),
                    "action": act_map[control],
                    "cart": cart_res,
                }
            )
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            return {
                "success": True,
                "action": control,
                "item": target_item.get("name"),
                "total": cart_res.get("total", 0),
                "itemCount": cart_res.get("itemCount", 0),
                "cart": cart_res.get("cart", []),
            }

        # ==========================================
        # VALIDATE CHECKOUT (CART SCREEN)
        # ==========================================
        if control == "checkout":
            if current_screen != ScreenTypes.CART:
                err = f"Control 'checkout' is only available on the Cart screen."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            cart = conversation_context.get("cart", [])
            if not cart:
                err = "Cannot checkout: Cart is empty."
                conversation_context["_last_action_rejected"] = {"control": control, "error": err}
                return {"success": False, "error": err}

            conversation_context["cart_stage"] = "payment_selection"
            response = create_ui_action("checkout", value)
            conversation_context["_last_action_rejected"] = None
            conversation_context["_last_kiosk_response"] = response
            return {
                "success": True,
                "status": "directed_to_payment_options",
                "total": sum(it.get("subtotal", 0) for it in cart),
                "message": "Directing customer to choose a payment method (UPI, Card, or Cash).",
            }

        # ==========================================
        # EXECUTE EXISTING UI BRIDGE
        # ==========================================

        response = create_ui_action(
            control,
            value
        )

        if response is None:
            err = "The kiosk could not perform this action."
            conversation_context["_last_action_rejected"] = {
                "control": control,
                "error": err,
            }
            return {
                "success": False,
                "error": err
            }

        # Clear rejected flag on successful execution
        conversation_context["_last_action_rejected"] = None

        # ==========================================
        # KEEP FULL RESPONSE INSIDE APPLICATION
        # ==========================================

        conversation_context[
            "_last_kiosk_response"
        ] = response

        # ==========================================
        # RETURN ONLY AGENT-RELEVANT INFORMATION
        # ==========================================

        result = {
            "success": True,
            "screen": response.screen,
            "control": control,
            "value": value
        }
        if control == "add_to_cart":
            if current_screen == ScreenTypes.MEAL_CONVERSION:
                active_meal = conversation_context.get("active_meal") or {}
                burger_info = active_meal.get("burger", {})
                b_name = burger_info.get("name") if isinstance(burger_info, dict) else str(burger_info or "")
                result["item"] = b_name
                result["is_meal"] = True
                result["size"] = active_meal.get("size")
                sel_side = active_meal.get("selected_side")
                result["side"] = sel_side.get("name") if isinstance(sel_side, dict) else (sel_side if sel_side else None)
                sel_drink = active_meal.get("selected_drink")
                result["drink"] = sel_drink.get("name") if isinstance(sel_drink, dict) else (sel_drink if sel_drink else None)
            elif current_screen == ScreenTypes.PRODUCT:
                result["item"] = active_product or conversation_context.get("selected_product")
                result["is_meal"] = False

        return result

    return screen_action


# ==========================================
# MAIN MESSAGE PROCESSOR
# ==========================================

def process_message(user_input, llm):

    # ==========================================
    # 1. CHECKOUT PAYMENT FLOW
    # ==========================================

    if conversation_context.get(
        "checkout_pending",
        False
    ):

        lower = user_input.lower()

        if "cash" in lower or "card" in lower:

            from repositories.order_repository import complete_order

            result = complete_order(
                conversation_context["cart"]
            )

            if not result["success"]:

                conversation_context[
                    "checkout_pending"
                ] = False

                return result["message"]

            conversation_context["cart"] = []

            conversation_context[
                "checkout_pending"
            ] = False

            if "cash" in lower:

                reply = KioskResponse(
                    screen=ScreenTypes.ORDER_COMPLETE,
                    message=(
                        "Your order has been placed successfully. "
                        "Please pay at the counter. Thank you!"
                    )
                )

                return track_screen(reply)

            reply = KioskResponse(
                screen=ScreenTypes.PAYMENT,
                message=(
                    "Your order has been placed successfully. "
                    "Please proceed with card payment. Thank you!"
                )
            )

            return track_screen(reply)


    # ==========================================
    # 2. PENDING BURGER CLARIFICATION
    # ==========================================

    if conversation_context.get(
        "pending_clarification"
    ) == "burger_type":

        decision = resolve_burger_clarification(
            user_input,
            llm
        )

        print(
            "Clarification Decision:",
            decision
        )


        # --------------------------------------
        # VEG
        # --------------------------------------

        if (
            decision.action == "clarification_answer"
            and decision.value == "veg"
        ):

            conversation_context[
                "burger_type"
            ] = "veg"

            conversation_context[
                "pending_clarification"
            ] = None

            reply = create_ui_action(
                "filter",
                "veg"
            )

            if reply:

                return track_screen(reply)


        # --------------------------------------
        # NON VEG
        # --------------------------------------

        elif (
            decision.action == "clarification_answer"
            and decision.value == "non veg"
        ):

            conversation_context[
                "burger_type"
            ] = "non veg"

            conversation_context[
                "pending_clarification"
            ] = None

            reply = create_ui_action(
                "filter",
                "non_veg"
            )

            if reply:

                return track_screen(reply)


        # --------------------------------------
        # BOTH
        # --------------------------------------

        elif (
            decision.action == "clarification_answer"
            and decision.value == "both"
        ):

            conversation_context[
                "pending_clarification"
            ] = None

            reply = create_ui_action(
                "filter",
                "both"
            )

            if reply:

                return track_screen(reply)


        # --------------------------------------
        # NEW INTENT
        # --------------------------------------

        elif decision.action == "new_intent":

            conversation_context[
                "pending_clarification"
            ] = None


        # --------------------------------------
        # UNCLEAR
        # --------------------------------------

        elif decision.action == "unclear":

            reply = KioskResponse(
                screen=conversation_context.get(
                    "current_screen",
                    ScreenTypes.BURGER_TYPE_SELECTION
                ),
                message=(
                    "Please choose veg, non veg, or both."
                )
            )

            return track_screen(reply)


    # ==========================================
    # 3. SCREEN-SPECIFIC UNDERSTANDING
    # ==========================================

    current_screen = conversation_context.get(
        "current_screen"
    )

    available_controls = conversation_context.get(
        "available_controls",
        []
    )


    if current_screen and available_controls:

        screen_intent = extract_screen_intent(
            user_input,
            current_screen,
            available_controls,
            llm
        )

        print(
            "Screen Intent Result:",
            screen_intent
        )


        # ======================================
        # CURRENT SCREEN CAN HANDLE REQUEST
        # ======================================

        if screen_intent.action == "screen_action":

            print(
                "Screen Control:",
                screen_intent.control
            )

            print(
                "Screen Value:",
                screen_intent.value
            )


            # ----------------------------------
            # IMPORTANT
            # ----------------------------------
            #
            # We DO NOT:
            #
            # - query the database
            # - fetch the menu
            # - call recommendation logic
            # - call handle_burger_selection()
            #
            # The recommendation data already exists
            # in the frontend.
            #
            # We simply tell the frontend:
            #
            # "Perform this UI action."
            # ----------------------------------

            reply = create_ui_action(
                screen_intent.control,
                screen_intent.value,
                user_input,
                llm
            )


            if reply:

                return track_screen(reply)


    # ==========================================
    # 4. GLOBAL INTENT EXTRACTION
    # ==========================================

    intent = extract_intent(
        user_input,
        llm,
        conversation_context
    )

    print(
        "Intent Result:",
        intent
    )


    # ==========================================
    # 5. GLOBAL INTENT ROUTING
    # ==========================================

    if (
        intent.action == "show_category"
        and not intent.category
    ):

        reply = KioskResponse(
            screen=ScreenTypes.HOME,
            message=(
                "Which category would you like — "
                "burgers, beverages, desserts, or sides?"
            )
        )


    elif intent.action == "unknown":

        reply = (
            "Could you tell me a little more "
            "about what you'd like?"
        )


    elif intent.action == "expand_context":

        reply = handle_more_options()


    elif intent.action == "decline_offer":

        reply = handle_decline(
            conversation_context,
            llm
        )


    elif intent.action == "show_priority_menu":

        reply = handle_menu(
            user_input,
            conversation_context,
            llm
        )


    elif intent.action == "show_full_menu":

        reply = handle_full_menu(
            conversation_context
        )


    elif intent.action == "show_category":

        reply = handle_category(
            intent.category,
            conversation_context
        )


    elif intent.action == "correct_item":

        reply = handle_correction(
            intent.item_name,
            conversation_context
        )


    elif intent.action == "add_item":

        print("=" * 50)

        print(
            "Conversation:",
            conversation_context
        )

        print(
            "Intent:",
            intent
        )

        print(
            "Last Category:",
            conversation_context.get(
                "last_category"
            )
        )

        print("=" * 50)


        # --------------------------------------
        # Customer is browsing
        # → open product details
        # --------------------------------------

        if conversation_context.get(
            "last_category"
        ):

            print(
                "Opening Product Details"
            )

            reply = handle_product(
                intent.item_name,
                conversation_context
            )


        # --------------------------------------
        # Customer directly ordered an item
        # --------------------------------------

        else:

            print(
                "Going to Handle Order"
            )

            reply = handle_order(
                intent.item_name,
                intent.quantity,
                intent.category,
                conversation_context,
                llm
            )


    elif intent.action == "remove_item":

        reply = handle_remove(
            intent.item_name,
            conversation_context
        )


    elif intent.action == "checkout":

        reply = handle_checkout(
            conversation_context,
            llm
        )


    else:

        reply = (
            "I'm sorry, I didn't understand that."
        )


    # ==========================================
    # 6. SAVE NEW SCREEN
    # ==========================================

    print(
        "FINAL BACKEND RESPONSE:",
        reply
    )

    if isinstance(reply, KioskResponse):
        return track_screen(reply)

    return reply