import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from kiosk_service import process_message
from state import conversation_context, reset_conversation
from schemas import KioskResponse
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)
from services.meal_service import get_meal_options
from services.cart_service import (
    add_item as cart_add_item,
    add_meal,
    get_cart,
    clear_cart,
    update_cart_item,
    complete_order
)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)


class MessageRequest(BaseModel):
    message: str


class AddToCartRequest(BaseModel):
    item_name: str
    quantity: int = 1


@app.get("/health")
def health():
    return {
        "status": "running"
    }


@app.post("/session/start")
def start_session():

    session_id = str(uuid.uuid4())

    reset_conversation(session_id)
    print("SESSION STARTED")
    print(conversation_context)
    return {
        "success": True,
        "session_id": session_id,
        "message": "Welcome to Burger King",
        "voice_enabled": True
    }


@app.get("/menu/burgers")
def burgers():
    return get_menu("burger")


@app.get("/menu/drinks")
def drinks():
    return get_menu("drink")


@app.get("/menu/sides")
def sides():
    return get_menu("side")


@app.get("/menu/desserts")
def desserts():
    return get_menu("dessert")


@app.get("/cart")
def cart():
    return get_cart()


@app.post("/message")
def message(request: MessageRequest):
    print("USER MESSAGE:", request.message)
    response = process_message(
        request.message,
        llm
    )

    if isinstance(response, KioskResponse):
        return response.model_dump()

    return {
        "screen": None,
        "message": response,
        "cart": conversation_context["cart"]
    }


@app.post("/cart/add")
def cart_add(request: AddToCartRequest):

    return cart_add_item(
        request.item_name,
        request.quantity
    )


@app.post("/cart/clear")
def cart_clear():

    return clear_cart()

@app.post("/meal/options")
def meal_options(request: dict):

    item_id = request.get("item_id")

    if item_id is None:
        return {
            "success": False,
            "message": "item_id is required"
        }

    # Check whether this burger's CURRENT meal offer
    # was already declined
    meal_flow = conversation_context.get("meal_flow")

    if (
        meal_flow
        and meal_flow.get("item_id") == item_id
        and meal_flow.get("status") == "declined"
    ):
        return {
            "success": True,
            "is_meal_available": False,
            "message": "Meal offer was declined."
        }

    offer = get_meal_options(item_id)

    if not offer:
        return {
            "success": False,
            "message": "Meal not available."
        }

    # Start a meal decision flow for this product instance
    conversation_context["meal_flow"] = {
        "item_id": item_id,
        "status": "pending"
    }

    return offer

@app.post("/meal/decline")
def decline_meal():

    meal_flow = conversation_context.get("meal_flow")

    if not meal_flow:
        return {
            "success": False,
            "message": "No active meal flow."
        }

    meal_flow["status"] = "declined"

    return {
        "success": True,
        "meal_flow": meal_flow
    }

@app.post("/cart/add-meal")
def cart_add_meal(request: dict):
    return add_meal(
        request["meal"],
        request.get("quantity", 1)
    )


@app.patch("/cart/item")
def update_cart_item_endpoint(request: dict):
    return update_cart_item(
        request.get("item_index"),
        request.get("action")
    )

@app.post("/order/complete")
def complete_order_endpoint():

    result = complete_order(
        conversation_context.get("cart", [])
    )

    return result