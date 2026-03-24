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
conversation_context = {   "last_category": None,"cart": [],"last_item": None,"last_offer": None}


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

def extract_intent(user_input):

    structured_llm = llm.with_structured_output(OrderIntent)

    menu = get_available_menu()
    menu_names = [item["name"] for item in menu]

    prompt = f"""
You are an intelligent restaurant intent extractor.

Understand customer intent semantically.

Available menu items:
{menu_names}

Customer message:
{user_input}

Rules:

Rules:

- If customer wants to order something:
  action = add_item

- If customer wants to remove something already ordered:
  action = remove_item

- If customer asks for specials / best / highlights:
  action = show_priority_menu

- If customer asks for all available items:
  action = show_full_menu

- If customer asks for a category:
  action = show_category
- If customer asks for more within current context:
  action = expand_context

- If customer declines recommendation or upsell:
  action = decline_offer

Allowed categories:
burger
beverage
dessert
side

- If customer asks for recommendation:
  action = recommend

- If customer asks for more within current context:
  action = expand_context

- If customer declines recommendation / upsell:
  action = decline_offer

- If customer asks to pay:
  action = checkout

- If greeting or casual talk:
  action = unknown

Important:
- item_name must match closest available menu item
- If customer uses partial names, map intelligently
- If customer says cancel / remove / don't want / delete:
  action = remove_item.
"""

    try:
        result = structured_llm.invoke(prompt)

        if result.category:
            mapping = {
                "burgers": "burger",
                "burger": "burger",
                "drinks": "beverage",
                "drink": "beverage",
                "beverages": "beverage",
                "desserts": "dessert",
                "dessert": "dessert",
                "sides": "side",
                "side": "side"
            }

            result.category = mapping.get(result.category.lower(), result.category.lower())

        return result

    except Exception:
        return OrderIntent(action="unknown")
    


def handle_more_options():

    if conversation_context["last_category"]:
        menu = get_menu_by_category(conversation_context["last_category"])
    else:
        menu = get_available_menu()

    priority_items = get_priority_items(menu)

    remaining_items = [item for item in menu if item not in priority_items]

    if not remaining_items:
        return f"That's all we currently have in {conversation_context['last_category']}."

    response = "Besides those, we also have:\n\n"

    for item in remaining_items:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nWould you like to try any of these?"

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

    if conversation_context["last_category"]:
        menu = get_menu_by_category(conversation_context["last_category"])
    else:
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

def handle_full_menu():

    if conversation_context["last_category"]:
        menu = get_menu_by_category(conversation_context["last_category"])

        priority = get_priority_items(menu)

        remaining = [item for item in menu if item not in priority]

        if not remaining:
            return f"That's all we currently have in {conversation_context['last_category']}."

        response = f"Besides those, we also have:\n\n"

        for item in remaining:
            response += f"• {item['name']} – ₹{int(item['price'])}\n"

        response += "\nThat completes our available options in this category."

        return response

    menu = get_available_menu()

    response = "Sure, here are all available items today:\n\n"

    for item in menu:
        response += f"• {item['name']} – ₹{int(item['price'])}\n"

    response += "\nThat's everything currently available. What would you like to order?"

    return response

def handle_recommendation(user_input):

    if conversation_context["last_category"]:
        items = get_menu_by_category(conversation_context["last_category"])
        category = conversation_context["last_category"]
    else:
        items = get_available_menu()
        category = "menu"

    priority = get_priority_items(items)

    if not priority:
        return "Everything available is already shown."

    recommended = priority[0]

    prompt = f"""
You are a Burger King India cashier.

Facts:
- Customer asked: "{user_input}"
- Current category: {category}
- Recommended item: {recommended['name']}
- Price: ₹{int(recommended['price'])}

Rules:
- Recommend ONLY this item
- Speak naturally
- Explain briefly why it is a good choice
- Do not invent other items
"""

    response = llm.invoke(prompt)

    return response.content

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
        conversation_context["cart"].append(result["item"])

        menu = get_available_menu()
        priority_items = get_priority_items(menu)

        upsell = None
        for item in priority_items:
            if item["name"] != result["item"]:
                upsell = item["name"]
                break

        prompt = f"""
You are a Burger King India cashier continuing an active order conversation.

Facts:
- Item added: {result['item']}
- Price: ₹{int(result['price'])}
- Suggested upsell: {upsell}

Rules:
- Do NOT greet
- Do NOT say welcome again
- Confirm item directly
- Mention exact price only
- Sound natural like a cashier already mid-conversation
- Softly suggest upsell only if available
- Do not invent menu items
"""

        response = llm.invoke(prompt)

        return response.content

    return result["message"]
def handle_remove(item_name):

    if item_name in conversation_context["cart"]:
        conversation_context["cart"].remove(item_name)
        return f"{item_name} removed from your order. Anything else?"

    return "That item is not in your current order."
  
def handle_checkout():

    prompt = """
You are a Burger King India cashier.

Customer is ready to pay.

Respond naturally like a cashier collecting payment.
"""

    response = llm.invoke(prompt)

    return response.content

    
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

    if intent.action == "show_category" and not intent.category:
     reply = "Which category would you like — burgers, beverages, desserts, or sides?"
     print("Cashier:", reply)
     continue

    if intent.action == "unknown":
     reply = handle_greeting(user_input)

    elif intent.action == "recommend":
     reply = handle_recommendation(user_input)

    elif intent.action == "expand_context":
     reply = handle_more_options()

    elif intent.action == "decline_offer":
     reply = handle_decline()

    elif intent.action == "show_priority_menu":
     reply = handle_menu(user_input)

    elif intent.action == "show_full_menu":
     reply = handle_full_menu()

    elif intent.action == "show_category":
     reply = handle_category(intent.category)

    elif intent.action == "add_item":
     reply = handle_order(intent.item_name)

    elif intent.action == "remove_item":
     reply = handle_remove(intent.item_name)

    elif intent.action == "checkout":
     reply = handle_checkout()

    else:
     reply = "I'm sorry, I didn't understand that."

    print("Cashier:", reply)