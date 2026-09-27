import time

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from kiosk_service import process_message
from state import conversation_context


load_dotenv()


# LLM used by the legacy process_message() flow
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)


print("Cashier: Welcome to Burger King India! What can I get for you today?")


while True:

    user_input = input("Customer: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    turn_start = time.time()

    reply = process_message(
        user_input,
        llm
    )

    reply_end = time.time()

    print(
        "LAST CATEGORY:",
        conversation_context["last_category"]
    )

    print(
        f"Total response time: {reply_end - turn_start:.2f}s"
    )

    print("Cashier:", reply)