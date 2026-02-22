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
from tools import search_tool
from langchain_groq import ChatGroq
import time
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

prompt = ChatPromptTemplate.from_messages(
  [
    (
      "system",
      """ 
      You are a friendly, fast-paced Burger King cashier.
      Keep responses short and natural.
      Continue the conversation naturally.
      Remember what the customer already ordered.
      Ask follow-up questions when needed
      Do not mention sources or tools.
      after receiving the payment, say thank you for your purchase.
      Be conversational, not corporate.

    
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


tools = [search_tool]
agent = create_tool_calling_agent(
    llm=llm,
    tools=[search_tool],
    prompt=prompt,
)  
agent_executor = AgentExecutor(agent=agent, tools=[search_tool], memory=memory,verbose=False)
#input = input("Hi there, how can I help you today?")
order_completed = False
start_time = time.time()

opening = agent_executor.invoke({
    "input": "The customer just walked to the counter",})
print("Cashier:", opening["output"])

while not order_completed:
  user_input = input("Customer: ")

  if user_input.lower() in ["quit", "exit"]:
    break

  raw_response = agent_executor.invoke({
    "input": user_input,
 })
  if "payment received" in raw_response["output"].lower() or \
       "thank you for your purchase" in raw_response["output"].lower():
        order_completed = True
 #response = parser.parse(raw_response["output"])
  end_time = time.time()

 #structured_response = parser.parse(raw_response["output"])
  print(raw_response["output"])
print(f"Time taken: {end_time - start_time:.2f} seconds")

