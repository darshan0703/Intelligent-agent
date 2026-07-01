from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel
from intent import extract_intent
from services.recommendation import get_priority_items,handle_recommendation
from services.menuservice import handle_menu, handle_category, handle_more_options, handle_full_menu, handle_burger_selection
from orderservice import handle_order, handle_remove
from conversation import handle_greeting, handle_checkout
from state import conversation_context
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
#from tools import search_tool
from tools import fetch_menu, add_item_to_cart
from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)
from langchain_groq import ChatGroq
from schemas import OrderIntent
from itemclassifiers import resolve_burger_clarification
from pydantic import ValidationError
import json
import time
from datetime import date
import os
from kiosk_service import process_message

load_dotenv()


llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct",temperature=0)

class OrderResponse(BaseModel):
  topic: str
  summary: str
  sources: List[str]
  tools: List[str]
  dialogue: List[str]


#parser = PydanticOutputParser(pydantic_object=OrderResponse)

prompt = ChatPromptTemplate.from_messages(
  [
    (
      "system",
      """ 
   You may use tools when needed to:
- Fetch menu
- Add items to cart
when the asked for menu , don't quote prices , only quote price when user asks to add item to cart. Always use the tools to get real-time data on menu and stock.

If no tool is required, respond normally.

   Never invent price.
   Never invent availability.
   Always rely on tool responses.
   All prices must be in ₹.
  if someone asks for offers just suggest only two costliest items
    
      """,
    ),
    ("placeholder","{chat_history}"),
    ("human","{input}"),
    ("placeholder","{agent_scratchpad}"),
  ]
)#.partial(format_instructions=parser.get_format_instructions())
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)


tools = [fetch_menu, add_item_to_cart]
agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)  
agent_executor = AgentExecutor(agent=agent, tools=[fetch_menu, add_item_to_cart], memory=memory,verbose=True)
order_completed = False

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