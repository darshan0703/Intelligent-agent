import io
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from services.cashier_agent import run_cashier_agent
import json
import numpy as np
import soundfile as sf
try:
    import whisper
except Exception:
    whisper = None
import time
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from perf import extract_or_create_tracer, current_perf_tracer, get_current_tracer
try:
    from kokoro import KPipeline
except Exception:
    KPipeline = None
from langchain_groq import ChatGroq
from debugging.context_capture import wrap_llm_for_capture
from pydantic import BaseModel
from kiosk_service import process_message, track_screen
from schemas import KioskResponse, ScreenTypes

from screen_controls import get_screen_controls
from services.cart_service import (
    add_item as cart_add_item,
    add_meal,
    clear_cart,
    complete_order,
    get_cart,
    update_cart_item,
    cart_lock,
)
from services.meal_service import get_meal_options
from services.menu_service import (
    add_item,
    get_available,
    get_category,
    get_menu,
    get_product,
)
from services.product_selector import resolve_product
from services.productservice import get_product_recommendations
from services.modules.m06_condiment_gating import get_checkout_dip_suggestions
from state import conversation_context, reset_conversation
load_dotenv()
print("INITIALIZING KOKORO TTS...")
try:
    if KPipeline is not None:
        tts_pipeline = KPipeline(
            lang_code="a"
        )
        print("KOKORO TTS READY")
    else:
        tts_pipeline = None
        print("KOKORO TTS NOT LOADED")
except Exception as e:
    tts_pipeline = None
    print("KOKORO TTS INIT FAILED:", repr(e))
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
llm = wrap_llm_for_capture(
    ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0,
    )
)

class MessageRequest(BaseModel):
    message: str
    interaction_id: Optional[str] = None
class AddToCartRequest(BaseModel):
    item_name: str
    quantity: int = 1
    idempotency_key: Optional[str] = None
@app.get("/health")
def health():
    return {
        "status": "running"
    }
@app.post("/session/start")
def start_session():
    session_id = str(uuid.uuid4())
    reset_conversation(session_id)
    conversation_context["session_start_time"] = time.perf_counter()
    print("SESSION STARTED")
    print(conversation_context)
    return {
        "success": True,
        "session_id": session_id,
        "message": "Welcome to Burger King",
        "voice_enabled": True,
    }
@app.post("/screen")
def update_screen(request: dict):
    screen = request.get("screen")
    if not screen:
        return {
            "success": False,
            "message": "screen is required",
        }
    tracked_res, is_valid = track_screen(screen, extra=request)
    if not is_valid:
        return {
            "success": True,
            "screen": conversation_context.get("current_screen"),
            "available_controls": conversation_context.get("available_controls", []),
            "stale_ignored": True,
        }
    return {
        "success": True,
        "screen": conversation_context.get("current_screen"),
        "available_controls": (
            conversation_context.get("available_controls", [])
        ),
        "meal_offer": conversation_context.get("meal_offer"),
        "selected_product": conversation_context.get("selected_product"),
    }
@app.post("/session/preference")
def set_preference(request: dict):
    preference = request.get("preference")
    if preference:
        normalized = preference.lower().replace("-", " ").replace("_", " ").strip()
        conversation_context["food_preference"] = normalized
    return {
        "success": True,
        "food_preference": conversation_context.get("food_preference")
    }
@app.get("/category/{category_name}/recommendations")
def category_recommendations(category_name: str, preference: str | None = None):
    from services.menuservice import build_burger_recommendation_data, build_category_response
    cart = conversation_context.get("cart", [])
    pref = preference or conversation_context.get("food_preference")
    cat_norm = category_name.strip().lower()

    if cat_norm in ("burger", "burgers"):
        items = get_category("burger")
        rec_data = build_burger_recommendation_data(items, cart=cart)
        return {
            "success": True,
            "data": rec_data
        }
    elif cat_norm in ("drink", "drinks"):
        resp = build_category_response(
            category="drink",
            title="Drinks",
            screen="recommended_drinks",
            conversation_context=conversation_context,
            filter_field="type",
            filter_values=["hot", "cold"],
            all_items_key="all_drinks"
        )
        return {"success": True, "data": resp.data}
    elif cat_norm in ("side", "sides"):
        resp = build_category_response(
            category="side",
            title="Sides",
            screen="recommended_sides",
            conversation_context=conversation_context,
            filter_field="foodType",
            filter_values=["veg", "non veg"],
            all_items_key="all_sides"
        )
        return {"success": True, "data": resp.data}
    elif cat_norm in ("dessert", "desserts"):
        resp = build_category_response(
            category="dessert",
            title="Desserts",
            screen="recommended_desserts",
            conversation_context=conversation_context,
            all_items_key="all_desserts"
        )
        return {"success": True, "data": resp.data}
    else:
        items = get_category(cat_norm)
        from services.recommendation import build_recommendations
        p, pr, a = build_recommendations(items, food_type=pref or "both", cart=cart)
        return {"success": True, "data": {"priority": p, "premium": pr, "additional": a}}


class MenuRequest(BaseModel):
    cart: list[dict] | None = None


@app.get("/menu/burgers")
def burgers_get(preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    return get_menu("burger", preference=pref, cart=conversation_context.get("cart", []))


@app.post("/menu/burgers")
def burgers_post(body: MenuRequest | None = None, preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    cart = body.cart if (body and body.cart is not None) else conversation_context.get("cart", [])
    return get_menu("burger", preference=pref, cart=cart)


@app.get("/menu/drinks")
def drinks_get(preference: str | None = None):
    return get_menu("drink", preference=preference, cart=conversation_context.get("cart", []))


@app.post("/menu/drinks")
def drinks_post(body: MenuRequest | None = None, preference: str | None = None):
    cart = body.cart if (body and body.cart is not None) else conversation_context.get("cart", [])
    return get_menu("drink", preference=preference, cart=cart)


@app.get("/menu/sides")
def sides_get(preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    return get_menu("side", preference=pref, cart=conversation_context.get("cart", []))


@app.post("/menu/sides")
def sides_post(body: MenuRequest | None = None, preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    cart = body.cart if (body and body.cart is not None) else conversation_context.get("cart", [])
    return get_menu("side", preference=pref, cart=cart)


@app.get("/menu/desserts")
def desserts_get(preference: str | None = None):
    return get_menu("dessert", preference=preference, cart=conversation_context.get("cart", []))


@app.post("/menu/desserts")
def desserts_post(body: MenuRequest | None = None, preference: str | None = None):
    cart = body.cart if (body and body.cart is not None) else conversation_context.get("cart", [])
    return get_menu("dessert", preference=preference, cart=cart)
@app.get("/cart")
def cart():
    return get_cart()


@app.get("/product/{item_name}/recommendations")
@app.get("/menu/product/{item_name}/recommendations")
def product_recommendations(item_name: str, preference: str | None = None):
    product = get_product(item_name)
    if not product:
        return {"recommendations": []}
    cart = conversation_context.get("cart", [])
    pref = preference or conversation_context.get("food_preference")
    recs = get_product_recommendations(product, cart=cart, preference=pref)
    return {"recommendations": recs}


@app.post("/product/recommendations")
@app.post("/menu/product/recommendations")
def product_recommendations_post(request: dict):
    item_name = request.get("item_name")
    if not item_name:
        return {"recommendations": []}
    product = get_product(item_name)
    if not product:
        return {"recommendations": []}
    cart = request.get("cart") if request.get("cart") is not None else conversation_context.get("cart", [])
    pref = request.get("preference") or conversation_context.get("food_preference")
    recs = get_product_recommendations(product, cart=cart, preference=pref)
    return {"recommendations": recs}


def resolve_category_request(message: str) -> Optional[str]:
    """
    Deterministically detects whether a message is requesting a menu category
    (e.g., 'I want a burger', 'Have in a burger', 'Can I have a burger', 'I'll have a burger', 'Have a burger', 'Get me a burger')
    without naming a specific product, item modifier, customization, or cart action.
    """
    clean = message.strip().lower()
    for ch in [".", ",", "!", "?", "'", '"', "-", "_", "/", "\\"]:
        clean = clean.replace(ch, " ")
    tokens = clean.split()
    clean_joined = " ".join(tokens)

    # Guard: Do not treat requests containing modifiers, ingredients, specific product descriptors,
    # quantities, or cart actions as category browsing.
    GUARD_TOKENS = {
        # Modifiers & Prepositions
        "with", "without", "no", "not", "extra", "add", "adding", "remove", "removing",
        "less", "more", "plus", "minus", "only", "plain", "custom", "customize",
        "customized", "substitute", "replace",
        # Ingredients & Customizations
        "cheese", "cheesy", "bacon", "onion", "onions", "pickle", "pickles", "tomato",
        "tomatoes", "lettuce", "mayo", "mayonnaise", "sauce", "sauces", "ketchup",
        "mustard", "jalapeno", "jalapenos", "patty", "patties", "bun", "buns", "salt",
        "ice", "sugar", "egg", "eggs", "sesame",
        # Product Descriptors & Specific Menu Items
        "veg", "nonveg", "crispy", "whopper", "makhani", "paneer", "chicken", "peri",
        "fiery", "spicy", "double", "triple", "coke", "pepsi", "sprite", "fanta", "shake",
        "fries", "dip", "dips", "sundae", "cone", "cup", "chocolate", "choco", "mango",
        "vanilla", "latte", "coffee", "tea", "water", "king", "combo", "meal", "grill",
        "grilled", "fried", "royale", "wrap", "wraps", "taco", "tacos", "puff", "puffs",
        "softie", "waffle", "nugget", "nuggets", "wing", "wings", "boneless", "strip",
        "strips", "hashbrown", "hashbrowns", "frappe", "espresso", "americano", "cappuccino",
        "pie", "lava", "mousse", "currant", "kitkat", "float", "thums", "up", "fizz",
        "saucy", "chilli", "oregano", "fish", "beef", "mutton", "tandoori", "bbq",
        "avocado", "truffle", "mushroom", "garlic",
        # Sizes & Quantities
        "medium", "large", "small", "regular", "single", "size", "upsize", "one", "two",
        "three", "four", "1", "2", "3", "4",
        # Cart & Ordering Actions
        "cart", "checkout", "pay", "payment", "bill", "order", "ordering", "cancel",
        "clear", "delete", "buy",
    }
    if any(t in GUARD_TOKENS for t in tokens):
        return None

    # Strip trailing polite expressions
    for polite in ["please", "thanks", "thank you"]:
        if clean_joined.endswith(f" {polite}"):
            clean_joined = clean_joined[:-len(polite) - 1].strip()

    category_targets = {
        "burger": {"burger", "burgers", "burger menu", "burgers menu"},
        "drink": {"drink", "drinks", "beverage", "beverages", "something to drink", "drink menu", "drinks menu"},
        "side": {"side", "sides", "side menu", "sides menu"},
        "dessert": {"dessert", "desserts", "sweet", "sweets", "dessert menu", "desserts menu"},
    }

    # Direct match on standalone category expressions
    for cat, targets in category_targets.items():
        if clean_joined in targets:
            return cat
        if clean_joined in {f"a {t}" for t in targets} or clean_joined in {f"some {t}" for t in targets} or clean_joined in {f"the {t}" for t in targets}:
            return cat

    # Common request phrasing prefixes
    prefixes = [
        "have in a ", "have in an ", "have in some ", "have in the ", "have in ",
        "have a ", "have an ", "have some ", "have the ", "have ",
        "ill have a ", "ill have an ", "ill have some ", "ill have the ", "ill have ",
        "i will have a ", "i will have an ", "i will have some ", "i will have the ", "i will have ",
        "can i have a ", "can i have an ", "can i have some ", "can i have the ", "can i have ",
        "can i get a ", "can i get an ", "can i get some ", "can i get the ", "can i get ",
        "can i see the ", "can i see a ", "can i see some ", "can i see ",
        "could i have a ", "could i have an ", "could i have some ", "could i have the ", "could i have ",
        "could i get a ", "could i get an ", "could i get some ", "could i get the ", "could i get ",
        "could i see the ", "could i see a ", "could i see some ", "could i see ",
        "get me a ", "get me an ", "get me some ", "get me the ", "get me ",
        "give me a ", "give me an ", "give me some ", "give me the ", "give me ",
        "i want a ", "i want an ", "i want some ", "i want the ", "i want ",
        "show me the ", "show me some ", "show me a ", "show me ", "show ",
        "show the ",
        "lets have a ", "lets have an ", "lets have some ", "lets have ",
        "browse the ", "browse a ", "browse some ", "browse ",
        "explore the ", "explore a ", "explore some ", "explore ",
        "open the ", "open a ", "open ",
        "take me to the ", "take me to ",
    ]

    for p in prefixes:
        if clean_joined.startswith(p):
            rem = clean_joined[len(p):].strip()
            for cat, targets in category_targets.items():
                if rem in targets:
                    return cat

    return None


@app.post("/message")
def message(request: MessageRequest, raw_req: Request = None, response: Response = None):
    tracer = extract_or_create_tracer(request=raw_req, interaction_id=request.interaction_id)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_message_started", endpoint="/message")
    if response is not None:
        response.headers["X-Interaction-ID"] = tracer.interaction_id

    def finish(res):
        duration_ms = (time.perf_counter() - t0) * 1000.0
        tracer.log("backend_message_completed", duration_ms=duration_ms, endpoint="/message")
        return res

    try:
        print("USER MESSAGE:", request.message)
        conversation_context["current_user_message"] = request.message
        conversation_context["current_interaction_id"] = tracer.interaction_id
        conversation_context["current_idempotency_key"] = (
            request.interaction_id
            or (raw_req.headers.get("X-Idempotency-Key") if raw_req else None)
            or tracer.interaction_id
        )
        # Clear any response left by a previous agent turn.
        conversation_context.pop(
            "_last_kiosk_response",
            None,
        )
        conversation_context.pop(
            "_last_action_rejected",
            None,
        )

        # ==========================================================
        # FAST-PATH FOR DIRECT CATEGORY REQUESTS
        # ==========================================================
        # Only route as a generic category request if it does NOT match
        # a specific menu item (selected or ambiguous), and the current
        # screen is not actively customizing a meal.
        current_screen = conversation_context.get("current_screen", "category_selection")
        if current_screen == ScreenTypes.ORDER_COMPLETE:
            return finish({
                "screen": ScreenTypes.ORDER_COMPLETE,
                "message": "Your order has been placed successfully! Please collect your receipt. Tap Start on the welcome screen to begin a new order.",
                "cart": [],
            })
        if current_screen != ScreenTypes.MEAL_CONVERSION:
            prod_resolution = resolve_product(request.message, conversation_context)
            if prod_resolution.get("status") not in ["selected", "ambiguous"]:
                target_cat = resolve_category_request(request.message)
                if target_cat:
                    from services.menuservice import handle_category
                    with tracer.measure("backend_category_resolution", category=target_cat):
                        kiosk_response = handle_category(target_cat, conversation_context)
                    if kiosk_response is not None:
                        track_screen(kiosk_response)
                        return finish(kiosk_response.model_dump())

        # ==========================================================
        # CASHIER AGENT (with resilient error handling)
        # ==========================================================
        try:
            with tracer.measure("backend_agent_execution"):
                agent_response = run_cashier_agent(
                    request.message,
                    conversation_context,
                )
        except Exception as e:
            print(f"Agent execution error (falling back to processor): {e}")
            agent_response = None

        # ==========================================================
        # CHECK WHETHER THE AGENT PERFORMED A KIOSK ACTION
        # ==========================================================
        kiosk_response = conversation_context.pop(
            "_last_kiosk_response",
            None,
        )
        last_rejected = conversation_context.pop(
            "_last_action_rejected",
            None,
        )

        if kiosk_response is not None:
            track_screen(kiosk_response)
            ui_act = (kiosk_response.data or {}).get("ui_action")
            if ui_act not in ["add_to_cart", "add_recommended"]:
                if agent_response and any(w in agent_response.lower() for w in ["added to your cart", "added to the cart", "now in your cart", "has been added to your cart"]):
                    curr = conversation_context.get("current_screen", "category_selection")
                    if curr == ScreenTypes.PRODUCT and conversation_context.get("meal_offer", {}).get("is_open"):
                        agent_response = "Would you like to make that a meal?"
                    elif curr == ScreenTypes.PRODUCT and conversation_context.get("meal_declined_pending_add"):
                        orig_q = conversation_context.get("original_requested_quantity", 1)
                        w_map = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
                        q_word = w_map.get(orig_q, str(orig_q))
                        agent_response = f"No problem. Shall I add the {q_word} burgers to your cart?"
                    elif curr == ScreenTypes.MEAL_CONVERSION:
                        agent_response = (
                            "Would you like all four burgers as meals, or one meal and the other three burgers on their own?"
                            if conversation_context.get("original_requested_quantity", 1) > 1 and conversation_context.get("meal_stage") == "split_decision"
                            else "What side or drink would you like with your meal?"
                        )
            kiosk_response.message = agent_response
            frontend_response = kiosk_response.model_dump()
            frontend_response["cart"] = conversation_context.get("cart", [])
            return finish(frontend_response)

        # ==========================================================
        # SAFEGUARDS: ACTION REJECTION & FACTUAL GROUNDING
        # ==========================================================
        if last_rejected is not None and agent_response:
            resp_lower = agent_response.lower()
            if last_rejected.get("control") == "add_to_cart":
                if any(w in resp_lower for w in ["added", "add to cart", "tap add", "cart now"]):
                    curr = conversation_context.get("current_screen", "category_selection")
                    if last_rejected.get("pending_meal_offer"):
                        agent_response = "Would you like to make that a meal?"
                    elif curr == "category_selection":
                        agent_response = "We're currently at the main menu. Would you like to explore our burgers or select an item first?"
                    else:
                        agent_response = "To add an item to your cart, please select the product first."
            elif last_rejected.get("control") in ["select_meal", "decline_meal"]:
                if "meal" in resp_lower and "added" in resp_lower:
                    agent_response = "The meal option is not currently open. Would you like to browse our menu?"

        # Guard: Factual consistency on screen queries
        current_screen = conversation_context.get("current_screen", "category_selection")
        msg_clean = request.message.strip().lower()
        is_asking_screen = any(q in msg_clean for q in ["what screen", "which screen", "where am i", "what page"])
        if is_asking_screen and agent_response:
            resp_lower = agent_response.lower()
            if current_screen == "category_selection" and ("product page" in resp_lower or "product screen" in resp_lower or "product details" in resp_lower):
                agent_response = "We're currently on the category selection screen—the main menu. What can I get for you today?"
            elif current_screen == "product" and ("category" in resp_lower or "main menu" in resp_lower):
                active_p = conversation_context.get("selected_product") or "this item"
                agent_response = f"You are currently on the product details page for {active_p}."

        # ==========================================================
        # AGENT-ONLY CONVERSATION
        # ==========================================================
        if agent_response and agent_response.strip():
            return finish({
                "screen": conversation_context.get("current_screen"),
                "message": agent_response,
                "cart": conversation_context.get(
                    "cart",
                    [],
                ),
            })
        # ==========================================================
        # OLD SYSTEM FALLBACK
        # ==========================================================
        #
        # Only fall back when the new agent genuinely produced no
        # response. This allows capabilities to be migrated gradually.
        # ==========================================================
        with tracer.measure("backend_process_message"):
            response = process_message(
                request.message,
                llm,
            )
        if isinstance(response, KioskResponse):
            return finish(response.model_dump())
        return finish({
            "screen": None,
            "message": response,
            "cart": conversation_context.get(
                "cart",
                [],
            ),
        })
    finally:
        current_perf_tracer.reset(token)

class CheckoutSuggestionsRequest(BaseModel):
    cart_lines: list[dict] | None = None


def _build_checkout_recommendations(cart):
    from services.menu_service import get_category, get_available
    from services.modules.m02_m03_basket_completion import build_checkout_3slot_recommendations

    all_sides = get_category("side") or []
    all_drinks = get_category("drink") or []
    all_desserts = get_category("dessert") or []
    all_items = get_available() or []

    return build_checkout_3slot_recommendations(
        cart=cart,
        all_sides=all_sides,
        all_drinks=all_drinks,
        all_desserts=all_desserts,
        all_items=all_items,
    )


@app.get("/recommendations/checkout")
def checkout_suggestions_get():
    cart = conversation_context.get("cart", [])
    recs = _build_checkout_recommendations(cart)
    conversation_context["checkout_recommendations"] = recs
    return {
        "success": True,
        "recommendations": recs,
        "suggestions": recs,
    }


@app.post("/recommendations/checkout")
def checkout_suggestions_post(body: CheckoutSuggestionsRequest | None = None):
    cart = (body.cart_lines if body and body.cart_lines is not None else None) or conversation_context.get("cart", [])
    recs = _build_checkout_recommendations(cart)
    conversation_context["checkout_recommendations"] = recs
    return {
        "success": True,
        "recommendations": recs,
        "suggestions": recs,
    }


@app.get("/cart/checkout-suggestions")
def checkout_suggestions_alias():
    cart = conversation_context.get("cart", [])
    recs = _build_checkout_recommendations(cart)
    return {
        "success": True,
        "recommendations": recs,
        "suggestions": recs,
    }


@app.post("/cart/add")
def cart_add(request: AddToCartRequest, raw_req: Request = None, response: Response = None):
    tracer = extract_or_create_tracer(request=raw_req)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_touch_request_started", endpoint="/cart/add")
    try:
        if response is not None:
            response.headers["X-Interaction-ID"] = tracer.interaction_id
        idempotency_key = (
            request.idempotency_key
            or (raw_req.headers.get("X-Idempotency-Key") if raw_req else None)
            or (raw_req.headers.get("X-Interaction-ID") if raw_req else None)
        )
        res = cart_add_item(
            request.item_name,
            request.quantity,
            idempotency_key=idempotency_key,
        )
        tracer.log("backend_touch_request_completed", duration_ms=(time.perf_counter() - t0) * 1000.0, endpoint="/cart/add")
        return res
    finally:
        current_perf_tracer.reset(token)
@app.post("/cart/clear")
def cart_clear():
    return clear_cart()
@app.post("/meal/options")
def meal_options(request: dict):
    try:
        item_id = request.get("item_id")
        if item_id is None:
            return {
                "success": False,
                "message": "item_id is required",
            }
        pref = request.get("food_preference") or conversation_context.get("food_preference")
        cart = request.get("cart") if ("cart" in request and request.get("cart") is not None) else conversation_context.get("cart", [])
        offer = get_meal_options(item_id, food_preference=pref, cart=cart)
        if not offer or not offer.get("is_meal_available"):
            return offer or {
                "success": True,
                "is_meal_available": False,
                "message": "Meal not available.",
            }
        conversation_context["meal_flow"] = {
            "item_id": item_id,
            "status": "pending",
        }
        return offer
    except Exception as e:
        from services.meal_service import _sanitize_error
        print(f"Error in meal_options endpoint: {_sanitize_error(e)}")
        return {
            "success": False,
            "is_meal_available": False,
            "message": "Failed to load meal options.",
        }
@app.post("/meal/decline")
def decline_meal(request: Optional[dict] = None, raw_req: Request = None, response: Response = None):
    tracer = extract_or_create_tracer(request=raw_req)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_touch_request_started", endpoint="/meal/decline")
    try:
        if response is not None:
            response.headers["X-Interaction-ID"] = tracer.interaction_id
        req_dict = request or {}
        item_id = req_dict.get("item_id") or req_dict.get("product_id")

        meal_flow = conversation_context.get("meal_flow")
        if not item_id:
            if meal_flow and meal_flow.get("item_id"):
                item_id = meal_flow.get("item_id")
            elif "meal_offer" in conversation_context and isinstance(conversation_context["meal_offer"], dict):
                item_id = conversation_context["meal_offer"].get("product_id")

        if not meal_flow and not item_id:
            return {
                "success": False,
                "message": "No active meal flow or product to decline.",
            }

        if meal_flow:
            if item_id is None or str(meal_flow.get("item_id")) == str(item_id):
                meal_flow["status"] = "declined"
        if "meal_offer" in conversation_context and isinstance(conversation_context["meal_offer"], dict):
            offer_prod_id = conversation_context["meal_offer"].get("product_id")
            if item_id is None or offer_prod_id is None or str(offer_prod_id) == str(item_id):
                conversation_context["meal_offer"]["is_open"] = False
                if "available_controls" in conversation_context:
                    conversation_context["available_controls"] = [
                        c for c in conversation_context["available_controls"]
                        if c not in ["select_meal", "decline_meal", "accept_meal"]
                    ]

        if item_id is not None:
            if "declined_meal_products" not in conversation_context:
                conversation_context["declined_meal_products"] = []
            if str(item_id) not in [str(x) for x in conversation_context["declined_meal_products"]]:
                conversation_context["declined_meal_products"].append(item_id)

        tracer.log("backend_touch_request_completed", duration_ms=(time.perf_counter() - t0) * 1000.0, endpoint="/meal/decline")
        return {
            "success": True,
            "meal_flow": meal_flow,
            "declined_product_id": item_id,
            "declined_meal_products": conversation_context.get("declined_meal_products", []),
        }
    finally:
        current_perf_tracer.reset(token)
@app.post("/cart/add-meal")
def cart_add_meal(request: dict, raw_req: Request = None, response: Response = None):
    tracer = extract_or_create_tracer(request=raw_req)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_touch_request_started", endpoint="/cart/add-meal")
    try:
        if response is not None:
            response.headers["X-Interaction-ID"] = tracer.interaction_id
        idempotency_key = (
            request.get("idempotency_key")
            or (raw_req.headers.get("X-Idempotency-Key") if raw_req else None)
            or (raw_req.headers.get("X-Interaction-ID") if raw_req else None)
        )
        res = add_meal(
            request["meal"],
            request.get("quantity", 1),
            idempotency_key=idempotency_key,
        )
        tracer.log("backend_touch_request_completed", duration_ms=(time.perf_counter() - t0) * 1000.0, endpoint="/cart/add-meal")
        return res
    finally:
        current_perf_tracer.reset(token)
@app.patch("/cart/item")
def update_cart_item_endpoint(request: dict):
    return update_cart_item(
        request.get("item_index"),
        request.get("action"),
    )
@app.post("/order/complete")
def complete_order_endpoint(raw_req: Request = None, response: Response = None):
    tracer = extract_or_create_tracer(request=raw_req)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_touch_request_started", endpoint="/order/complete")
    try:
        if response is not None:
            response.headers["X-Interaction-ID"] = tracer.interaction_id
        result = complete_order(
            conversation_context.get("cart", [])
        )
        if isinstance(result, dict) and result.get("success"):
            conversation_context["current_screen"] = ScreenTypes.ORDER_COMPLETE
            conversation_context["available_controls"] = []
            conversation_context["selected_product"] = None
            conversation_context["selected_product_id"] = None
            conversation_context["displayed_products"] = []
            conversation_context["last_item"] = None
            conversation_context["last_offer"] = None
            conversation_context["pending_suggestion"] = None
            conversation_context["pending_clarification"] = None
            conversation_context["declined_meal_products"] = []
            conversation_context["meal_flow"] = None
            conversation_context["meal_offer"] = None
            conversation_context["active_meal"] = None
            conversation_context["meal_stage"] = None
            conversation_context["cart_stage"] = None
            conversation_context["selected_payment"] = None
            conversation_context["checkout_recommendations"] = []
            conversation_context["conversation_history"] = []
            conversation_context["pending_items"] = []
            conversation_context["processed_idempotency_keys"] = {}
            conversation_context["explicit_meal_intent"] = None
            conversation_context["current_interaction_id"] = None
            conversation_context["current_idempotency_key"] = None
            conversation_context["session_id"] = str(uuid.uuid4())
            if "session_start_time" in conversation_context:
                session_dur = time.perf_counter() - conversation_context["session_start_time"]
                tracer.log(
                    "milestone_order_session_completed",
                    session_duration_s=round(session_dur, 2),
                    session_duration_ms=round(session_dur * 1000, 2),
                )
        tracer.log("backend_touch_request_completed", duration_ms=(time.perf_counter() - t0) * 1000.0, endpoint="/order/complete")
        return result
    finally:
        current_perf_tracer.reset(token)
# ============================================================
# LOCAL KOKORO TEXT TO SPEECH
# ============================================================
@app.post("/tts")
def text_to_speech(request: dict, raw_req: Request = None, response: Response = None):
    tracer = extract_or_create_tracer(request=raw_req)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_tts_started", endpoint="/tts")
    if response is not None:
        response.headers["X-Interaction-ID"] = tracer.interaction_id

    try:
        text = request.get("text")
        print("TTS REQUEST:", text)
        if not text:
            return Response(
                content=b"",
                media_type="audio/wav",
                status_code=400,
                headers={"X-Interaction-ID": tracer.interaction_id},
            )
        try:
            print("GENERATING KOKORO AUDIO...")
            with tracer.measure("backend_tts_kokoro_generation"):
                generator = tts_pipeline(
                    text,
                    voice="af_heart",
                )
                audio_segments = []
                for _, _, audio in generator:
                    audio_segments.append(
                        np.asarray(audio)
                    )
                if not audio_segments:
                    raise RuntimeError(
                        "Kokoro generated no audio."
                    )
                audio_data = np.concatenate(
                    audio_segments
                )
                audio_buffer = io.BytesIO()
                sf.write(
                    audio_buffer,
                    audio_data,
                    24000,
                    format="WAV",
                )
                audio_buffer.seek(0)
                audio_bytes = audio_buffer.read()
            print(
                "KOKORO AUDIO GENERATED:",
                len(audio_bytes),
                "bytes",
            )
            duration_ms = (time.perf_counter() - t0) * 1000.0
            tracer.log("backend_tts_completed", duration_ms=duration_ms, endpoint="/tts")
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"X-Interaction-ID": tracer.interaction_id},
            )
        except Exception as e:
            print(
                "KOKORO TTS ERROR:",
                repr(e),
            )
            return Response(
                content=b"TTS generation failed",
                media_type="text/plain",
                status_code=500,
                headers={"X-Interaction-ID": tracer.interaction_id},
            )
    finally:
        current_perf_tracer.reset(token)
# ============================================================
# LOCAL WHISPER SPEECH TO TEXT
# ============================================================
print("INITIALIZING WHISPER STT...")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small.en")
try:
    if whisper is not None:
        whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
        print(f"WHISPER STT READY: {WHISPER_MODEL_NAME}")
    else:
        whisper_model = None
        print("WHISPER STT NOT INSTALLED")
except Exception as e:
    whisper_model = None
    print("WHISPER INITIALIZATION ERROR:", repr(e))
@app.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    raw_req: Request = None,
    response: Response = None,
):
    tracer = extract_or_create_tracer(request=raw_req)
    token = current_perf_tracer.set(tracer)
    t0 = time.perf_counter()
    tracer.log("backend_stt_started", endpoint="/stt")
    if response is not None:
        response.headers["X-Interaction-ID"] = tracer.interaction_id

    try:
        print("\n" + "=" * 80)
        print("STT REQUEST")
        print("=" * 80)
        # Find FFmpeg automatically so the same code works on
        # macOS, Linux/Codespaces, and other environments.
        ffmpeg = shutil.which("ffmpeg")
        print("WHISPER MODEL:", WHISPER_MODEL_NAME)
        print("FFMPEG:", ffmpeg)
        print("UPLOADED FILE:", file.filename)
        print("CONTENT TYPE:", file.content_type)
        if whisper_model is None:
            print("ERROR: Whisper model is not initialized.")
            return {
                "success": False,
                "message": "Whisper model is not initialized.",
            }
        if not ffmpeg:
            print("ERROR: FFmpeg not found.")
            return {
                "success": False,
                "message": "FFmpeg not found.",
            }
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                input_file = temp_dir / "input.webm"
                wav_file = temp_dir / "input.wav"
                print("READING UPLOADED AUDIO...")
                audio_data = await file.read()
                print(
                    "AUDIO SIZE:",
                    len(audio_data),
                    "bytes",
                )
                if not audio_data:
                    return {
                        "success": False,
                        "message": "Uploaded audio file is empty.",
                    }
                input_file.write_bytes(audio_data)
                # --------------------------------------------------------
                # Convert browser WebM/Opus audio to 16 kHz mono WAV.
                # --------------------------------------------------------
                print("STARTING FFMPEG...")
                with tracer.measure("backend_stt_audio_conversion"):
                    ffmpeg_result = subprocess.run(
                        [
                            ffmpeg,
                            "-y",
                            "-i",
                            str(input_file),
                            "-ar",
                            "16000",
                            "-ac",
                            "1",
                            "-c:a",
                            "pcm_s16le",
                            str(wav_file),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                print(
                    "FFMPEG FINISHED:",
                    ffmpeg_result.returncode,
                )
                if ffmpeg_result.returncode != 0:
                    print("FFMPEG ERROR:")
                    print(ffmpeg_result.stderr)
                    return {
                        "success": False,
                        "message": "Audio conversion failed.",
                    }
                print("WAV CREATED:", wav_file.exists())
                if not wav_file.exists():
                    return {
                        "success": False,
                        "message": "WAV file was not created.",
                    }
                print(
                    "WAV SIZE:",
                    wav_file.stat().st_size,
                    "bytes",
                )
                # --------------------------------------------------------
                # Transcribe using the installed openai-whisper package.
                # This replaces the old whisper.cpp CLI dependency.
                # --------------------------------------------------------
                print("STARTING WHISPER...")
                with tracer.measure("backend_stt_whisper_transcribe"):
                    whisper_result = whisper_model.transcribe(
                        str(wav_file),
                        language="en",
                        fp16=False,
                    )
                transcript = whisper_result.get("text", "").strip()
                print("WHISPER TRANSCRIPT:", transcript)
                print("=" * 80 + "\n")
                duration_ms = (time.perf_counter() - t0) * 1000.0
                tracer.log("backend_stt_completed", duration_ms=duration_ms, endpoint="/stt")
                return {
                    "success": True,
                    "text": transcript,
                }
        except subprocess.TimeoutExpired as e:
            print(
                "STT TIMEOUT:",
                repr(e),
            )
            return {
                "success": False,
                "message": "Speech recognition timed out.",
            }
        except Exception as e:
            print(
                "STT ERROR:",
                repr(e),
            )
            return {
                "success": False,
                "message": "Speech recognition failed.",
            }
    finally:
        current_perf_tracer.reset(token)
