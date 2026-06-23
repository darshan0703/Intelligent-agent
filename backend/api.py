from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from kiosk_service import process_message
from state import conversation_context
from schemas import KioskResponse

from langchain_groq import ChatGroq
from dotenv import load_dotenv

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


@app.get("/health")
def health():

    return {
        "status": "running"
    }


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