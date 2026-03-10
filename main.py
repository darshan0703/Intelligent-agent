from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel
#from langchain_anthropic import ChatAnthropic
#from langchain.chat_models import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
#from tools import search_tool
from tools import fetch_menu, add_item_to_cart
from db_service import add_to_cart, get_available_menu
from langchain_groq import ChatGroq
from schemas import OrderIntent
from pydantic import ValidationError
import json
import time
from datetime import date
import os

load_dotenv()  # Load environment variables from .env file

# Newer LangChain chat model constructors accept `model=` consistently.
# Use `model` for both providers to match current usage patterns.
#llm = ChatOllama(model="phi3", temperature=0)cal
#llm = ChatOllama(model="mistral", temperature=0.3)
llm = ChatGroq(model="llama-3.3-70b-versatile",temperature=0)
#llm = ChatOpenAI(
 #     model="grok-1",  
   #   api_key=os.getenv("GROK_API_KEY"),
    #  GROK_API_KEY="GROQ_API_KEY=""



#llm = ChatAnthropic(model="claude-opus-4.5", temperature=0)
#response = llm.invoke("hi , good morning , i would like to get a burger")
#print(response)

class OrderResponse(BaseModel):
  topic: str
  summary: str
  sources: List[str]
  tools: List[str]
  dialogue: List[str]

#parser = PydanticOutputParser(pydantic_object=OrderResponse)
def handle_greeting(user_input):

    prompt = f"""
You are a friendly cashier at Burger King India.

Customer said: "{user_input}"

Respond naturally as a cashier greeting a customer.
Keep it short and friendly.
"""

    response = llm.invoke(prompt)

    return response.content

def extract_intent(user_input):
    prompt = f"""
You are an intent classification system.

Classify the user's message into one of these actions:

add_item → customer wants to order food
show_menu → customer asks what items are available
checkout → customer wants to pay
unknown → anything else

Examples:

User: show me the menu
Response: {{"action":"show_menu"}}

User: what items do you have
Response: {{"action":"show_menu"}}

User: do you have fries
Response: {{"action":"show_menu"}}

User: what burgers are available
Response: {{"action":"show_menu"}}

User: add whopper
Response: {{"action":"add_item","item_name":"Whopper"}}

User: I want fries
Response: {{"action":"add_item","item_name":"Fries Small"}}

User: I want to pay
Response: {{"action":"checkout"}}

Now classify:

User: "{user_input}"

Return ONLY JSON.
"""

    response = llm.invoke(prompt)

    try:
        data = json.loads(response.content)
        return OrderIntent(**data)
    except:
        return OrderIntent(action="unknown")
def handle_menu():

    menu = get_available_menu()

    # compute items we want to sell first
    priority_items = get_priority_items(menu)

    response = "Namaste! Welcome to Burger King India.\n\n"

    response += "Today we have some great options you might enjoy:\n"

    for item in priority_items:
        response += f"⭐ {item['name']} – ₹{int(item['price'])}\n"

    response += "\nFull menu:\n"

    for item in menu:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nWhat would you like to order?"

    return response
    
'''def handle_intent(intent, user_input):

    if intent.action == "show_menu":
        menu = get_available_menu()

        return {
            "type": "menu",
            "menu": menu,
            "user_question": user_input
        }

    elif intent.action == "add_item":
        result = add_to_cart(intent.item_name)
        return {
            "type": "add_item",
            "result": result
        }

    elif intent.action == "checkout":
        return {
            "type": "checkout"
        }

    return {"type": "unknown"}'''
def get_priority_items(menu):

    today = date.today()

    for item in menu:
        days_to_expiry = (item["expiry"] - today).days

        # high stock + near expiry = higher priority
        expiry_score = max(0, 30 - days_to_expiry)

        item["priority"] = item["stock"] + expiry_score

    menu_sorted = sorted(menu, key=lambda x: x["priority"], reverse=True)

    return menu_sorted[:2]  # top items to push

def handle_order(item_name):

    result = add_to_cart(item_name)

    if result["success"]:
        return f"{result['item']} has been added to your order. Price: ₹{int(result['price'])}"

    return result["message"]
  
def handle_checkout():

  return "Great! Please proceed to payment."

'''def format_response(system_result):

    if system_result["type"] == "menu":

        menu = system_result["menu"]

        response = "Namaste! Here are the items available today:\n\n"

        for item in menu:
            response += f"• {item['name']} – ₹{int(item['price'])}\n"

        response += "\nWhat would you like to order?"

        return response'''
    
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
agent_executor = AgentExecutor(agent=agent, tools=[fetch_menu, add_item_to_cart], memory=memory,verbose=False)
#input = input("Hi there, how can I help you today?")
order_completed = False
start_time = time.time()


from router import route_intent

print("Cashier: Welcome to Burger King India! What can I get for you today?")

while True:

    user_input = input("Customer: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    intent = extract_intent(user_input)

    route = route_intent(intent)

    if route == "llm":
        reply = handle_greeting(user_input)

    elif route == "menu":
        reply = handle_menu()

    elif route == "order":
        reply = handle_order(intent.item_name)

    elif route == "checkout":
        reply = handle_checkout()

    else:
        reply = "I'm sorry, I didn't understand that."

    print("Cashier:", reply)
