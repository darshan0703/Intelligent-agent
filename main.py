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
from db_service import add_to_cart, get_available_menu ,get_menu_by_category
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
conversation_context = {"last_category": None}


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
You are an intent classification engine for a restaurant ordering system.

Classify the user's message into ONE of these actions:

1. add_item → customer wants to order a specific item
2. show_priority_menu → customer asks for specials / suggestions / recommendations
3. show_full_menu → customer asks for full menu / all items / what else is available
4. show_category → customer asks for a category like desserts, drinks, burgers, sides
5. checkout → customer wants to pay / finish order
6. unknown → anything else

Rules:

- Return ONLY JSON
- Do not explain
- If action is add_item, include item_name
- If action is show_category, include category

Examples:

User: what is special today
Response: {{"action":"show_priority_menu"}}

User: what do you recommend
Response: {{"action":"show_priority_menu"}}

User: what do you have
Response: {{"action":"show_priority_menu"}}

User: show menu
Response: {{"action":"show_full_menu"}}

User: what's on menu
Response: {{"action":"show_full_menu"}}

User: what else do you have
Response: {{"action":"show_full_menu"}}

User: show all items
Response: {{"action":"show_full_menu"}}

User: desserts
Response: {{"action":"show_category","category":"dessert"}}

User: what desserts do you have
Response: {{"action":"show_category","category":"dessert"}}

User: drinks
Response: {{"action":"show_category","category":"beverage"}}

User: burgers
Response: {{"action":"show_category","category":"burger"}}

User: fries please
Response: {{"action":"add_item","item_name":"Fries"}}

User: one whopper
Response: {{"action":"add_item","item_name":"Whopper"}}

User: add whopper jr
Response: {{"action":"add_item","item_name":"Whopper Jr"}}

User: I want to pay
Response: {{"action":"checkout"}}

User: checkout
Response: {{"action":"checkout"}}

Now classify:

User: "{user_input}"
"""

    response = llm.invoke(prompt)

    try:
        data = json.loads(response.content)
        return OrderIntent(**data)

    except:
        return OrderIntent(action="unknown")
    
def handle_more_options():

    menu = get_available_menu()

    priority_items = get_priority_items(menu)

    remaining_items = [item for item in menu if item not in priority_items]

    response = "Yes, besides our current recommendations, we also have:\n\n"

    for item in remaining_items:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nThat’s the full menu currently available today. Would you like to try any of these?"

    return response
def handle_category(category):

    conversation_context["last_category"] = category

    menu = get_menu_by_category(category)

    if not menu:
        return f"Sorry, we don't have any {category} available right now."

    priority_items = get_priority_items(menu)

    response = f"Here are our {category} options today:\n\n"

    for item in priority_items:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nWhat would you like to order?"

    return response

def handle_menu(user_input):

    menu = get_available_menu()
    priority_items = get_priority_items(menu)

    expanded_keywords = [
        "what else",
        "other items",
        "full menu",
        "all items",
        "more options"
    ]

    # If customer asks for more options → show full menu directly
    if any(word in user_input.lower() for word in expanded_keywords):

        response = "Sure, here are all the available items today:\n\n"

        for item in menu:
            response += f"• {item['name']} – ₹{int(item['price'])}\n"

        response += "\nWhat would you like to order?"

        return response

    # Otherwise use LLM for natural selling
    priority_text = "\n".join(
        [f"{item['name']} – ₹{int(item['price'])}" for item in priority_items]
    )

    full_menu_text = "\n".join(
        [f"{item['name']} – ₹{int(item['price'])}" for item in menu]
    )

    prompt = f"""
You are a Burger King India cashier.

Priority items:
{priority_text}

Full menu:
{full_menu_text}

Rules:
- Mention priority items first naturally
- Briefly mention there are more options
- Do not invent items
- Do not change prices
"""

    response = llm.invoke(prompt)

    return response.content
    
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

def handle_full_menu():

    menu = get_available_menu()

    response = "Sure, here are all available items today:\n\n"

    for item in menu:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nThat's everything currently available. What would you like to order?"

    return response

def handle_recommendation():

    if conversation_context["last_category"]:

        items = get_menu_by_category(conversation_context["last_category"])

    else:
        items = get_available_menu()

    priority = get_priority_items(items)

    if not priority:
        return "Everything available is already shown."

    response = "I'd recommend:\n\n"

    for item in priority:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nThese are moving well today."

    return response

def get_priority_items(menu):

    today = date.today()

    for item in menu:
        days_to_expiry = (item["expiry"] - today).days

        # high stock + near expiry = higher priority
        expiry_score = max(0, 30 - days_to_expiry)

        item["priority"] = item["stock"] + expiry_score

    menu_sorted = sorted(menu, key=lambda x: x["priority"], reverse=True)

    return menu_sorted[:2]  # top items to push
def handle_category(category):

    items = get_menu_by_category(category)

    if not items:
        return f"Sorry, we don't have any {category} available right now."

    priority = get_priority_items(items)

    response = f"Here are our available {category} options:\n\n"

    for item in priority:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    return response

def handle_order(item_name):

    result = add_to_cart(item_name)

    if result["success"]:

        menu = get_available_menu()
        priority_items = get_priority_items(menu)

        upsell = priority_items[0]["name"] if priority_items else None

        prompt = f"""
You are a friendly Burger King India cashier.

Facts:
- Item added: {result['item']}
- Price: ₹{int(result['price'])}

Upsell item:
- {upsell}

Rules:
- Never change item name
- Never change price
- Speak naturally like a human cashier
- Softly suggest the upsell item if appropriate
"""

        response = llm.invoke(prompt)

        return response.content
    return result["message"]
  
def handle_checkout():

    prompt = """
You are a Burger King India cashier.

Customer is ready to pay.

Respond naturally like a cashier collecting payment.
"""

    response = llm.invoke(prompt)

    return response.content

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

    if intent.action == "unknown":
     reply = handle_greeting(user_input)

    elif intent.action == "show_priority_menu":
     reply = handle_menu(user_input)

    elif intent.action == "show_full_menu":
     reply = handle_full_menu()

    elif intent.action == "show_category":
     reply = handle_category(intent.category)

    elif intent.action == "add_item":
     reply = handle_order(intent.item_name)

    elif intent.action == "checkout":
     reply = handle_checkout()

    else:
     reply = "I'm sorry, I didn't understand that."

    print("Cashier:", reply)
