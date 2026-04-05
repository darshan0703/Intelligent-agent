from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel
from intent import extract_intent
from recommendation import get_priority_items,handle_recommendation
from menuservice import handle_menu, handle_category, handle_more_options, handle_full_menu
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
from db_service import add_to_cart, get_available_menu ,get_menu_by_category
from langchain_groq import ChatGroq
from schemas import OrderIntent
from pydantic import ValidationError
import json
import time
from datetime import date
import os

load_dotenv()


llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct",temperature=0)

class OrderResponse(BaseModel):
  topic: str
  summary: str
  sources: List[str]
  tools: List[str]
  dialogue: List[str]


#parser = PydanticOutputParser(pydantic_object=OrderResponse)

def handle_decline():

    prompt = f"""
You are a Burger King India cashier.

Facts:
- Current cart: {conversation_context['cart']}

Customer declined the previous suggestion.

Rules:
- Do not greet again
- Speak naturally
- Ask whether customer wants checkout or more items
"""

    response = llm.invoke(prompt)

    return response.content

def handle_correction(item_name):

    if not conversation_context["cart"]:
        return "Tell me what you'd like to order."

    previous = conversation_context["cart"].pop()

    result = add_to_cart(item_name)

    if result["success"]:
        conversation_context["cart"].append(result["item"])

        return f"Sure 👍 I've replaced {previous} with {result['item']} for ₹{int(result['price'])}."

    else:
        conversation_context["cart"].append(previous)
        return f"I removed {previous}, but {item_name} is not available."
    

    
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

    if conversation_context["checkout_pending"]:

     lower = user_input.lower()

     if "cash" in lower:
        conversation_context["cart"] = []
        conversation_context["checkout_pending"] = False
        reply = "You can pay at the counter. Thank you for your order."
        print("Cashier:", reply)
        break

     elif "card" in lower:
        conversation_context["cart"] = []
        conversation_context["checkout_pending"] = False
        reply = "Please proceed with card payment at the counter. Thank you for your order."
        print("Cashier:", reply)
        break


    turn_start = time.time()
    intent = extract_intent(user_input, llm, conversation_context)
    print("Intent:", intent)

    intent_end = time.time()
    print(f"Intent time: {intent_end - turn_start:.2f}s")

    if intent.action == "show_category" and not intent.category:
     reply = "Which category would you like — burgers, beverages, desserts, or sides?"
     print("Cashier:", reply)
     continue

    if intent.action == "unknown":
     reply = handle_greeting(user_input, conversation_context, llm)

    elif intent.action == "recommend":
     reply = handle_recommendation(user_input, conversation_context, llm)

    elif intent.action == "expand_context":
     reply = handle_more_options()

    elif intent.action == "decline_offer":
     reply = handle_decline()

    elif intent.action == "show_priority_menu":
     reply = handle_menu(user_input, conversation_context, llm)

    elif intent.action == "show_full_menu":
     reply = handle_full_menu(conversation_context)

    elif intent.action == "show_category":
     reply = handle_category(intent.category, conversation_context)

    elif intent.action == "correct_item":
     reply = handle_correction(intent.item_name)

    elif intent.action == "add_item":
     reply = handle_order(intent.item_name,intent.quantity,intent.category,conversation_context,llm)

    elif intent.action == "remove_item":
     reply = handle_remove(intent.item_name,conversation_context)

    elif intent.action == "checkout":
     reply = handle_checkout(conversation_context, llm)

    else:
     reply = "I'm sorry, I didn't understand that."

    reply_end = time.time()
    print(f"Total response time: {reply_end - turn_start:.2f}s")

    print("Cashier:", reply)