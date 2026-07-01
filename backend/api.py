from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from kiosk_service import process_message
from state import conversation_context
from schemas import KioskResponse
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)
from services.cart_service import (
    add_item as cart_add_item,
    get_cart,
    clear_cart
)

load_dotenv()

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

llm = ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
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

@app.get("/menu/burgers")
def burgers():

    return get_menu("burger")


@app.get("/menu/drinks")
def drinks():

    return get_menu("drink")


@app.get("/menu/sides")
def sides():

    return  get_menu("side")

@app.get("/cart")
def cart():

    return get_cart()


@app.get("/menu/desserts")
def desserts():

    return get_menu("dessert")


@app.post("/message")
def message(request: MessageRequest):

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