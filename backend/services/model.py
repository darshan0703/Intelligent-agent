"""
services/model.py
LangChain-compatible model adapter for TheAtom Cashier Agent.
Uses Gemini 3.8 Flash REST API with single-turn tool execution protection.
"""
import os
import json
import httpx
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from state import conversation_context

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class ModelAdapter:
    def __init__(self, model=None):
        self.model = model

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return AIMessage(content="Welcome to Burger King! How can I help you today?")


class GeminiRestModel(ModelAdapter):
    """
    Direct, ultra-fast Gemini 3.8 Flash model implementation.
    Safe on Windows (pure ASCII logging), zero missing-module dependencies.
    Prevents tool-calling infinite loops by returning conversational response
    as soon as a tool has completed execution.
    """

    def __init__(self, model_name: str = "gemini-3.8-flash"):
        super().__init__()
        self.model_name = model_name
        self.api_key = GEMINI_API_KEY
        self.tools = []

    def bind_tools(self, tools):
        self.tools = tools or []
        return self

    def _extract_intent_and_action(self, user_text: str):
        """
        Fast heuristic check for common restaurant actions before calling LLM.
        Avoids network latency for standard navigational phrases.
        """
        text = user_text.lower().strip()

        # Category navigation
        if any(w in text for w in ["burger", "burgers", "whopper"]):
            return {"name": "open_category", "args": {"category": "burger"}}
        if any(w in text for w in ["drink", "drinks", "beverage", "beverages", "coke", "coffee", "shake"]):
            return {"name": "open_category", "args": {"category": "drink"}}
        if any(w in text for w in ["side", "sides", "fries", "nuggets", "wing", "dip"]):
            return {"name": "open_category", "args": {"category": "side"}}
        if any(w in text for w in ["dessert", "desserts", "sweet", "ice cream", "sundae", "mousse"]):
            return {"name": "open_category", "args": {"category": "dessert"}}

        # Recommendation request
        if any(w in text for w in ["recommend", "suggestion", "best", "popular", "what should i"]):
            return {"name": "get_recommendations", "args": {}}

        return None

    def invoke(self, messages):
        # 1. LOOP GUARD: If a tool was already executed in this turn, return spoken confirmation.
        # NEVER return another tool call after a ToolMessage!
        has_tool_message = any(
            getattr(m, "type", "") == "tool" or type(m).__name__ == "ToolMessage"
            for m in messages
        )
        if has_tool_message:
            cat = conversation_context.get("last_category", "")
            if cat == "burger":
                return AIMessage(content="Here are our flame-grilled burgers. Let me know what you'd like!")
            elif cat == "drink":
                return AIMessage(content="Here are our refreshing drinks and beverages.")
            elif cat == "side":
                return AIMessage(content="Here are our crispy golden sides and fries.")
            elif cat == "dessert":
                return AIMessage(content="Here are our delicious desserts and sundaes.")
            return AIMessage(content="I've opened that for you on the screen. What would you like?")

        # 2. Extract the latest user query from the messages list
        user_query = ""
        for m in reversed(messages):
            if getattr(m, "type", "") == "human" or getattr(m, "role", "") == "user":
                user_query = getattr(m, "content", "")
                break
            elif isinstance(m, str):
                user_query = m
                break

        if not user_query and messages:
            last = messages[-1]
            user_query = getattr(last, "content", str(last))

        # 3. Check for tool intent
        action = self._extract_intent_and_action(user_query)
        if action and any(getattr(t, "name", "") == action["name"] for t in self.tools):
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": action["name"],
                    "args": action["args"],
                    "id": f"call_{action['name']}",
                    "type": "tool_call",
                }]
            )

        # 4. Call Gemini 3.8 Flash for conversational generation
        prompt_lines = []
        for msg in messages:
            role = getattr(msg, "type", "human")
            content = getattr(msg, "content", str(msg))
            if role == "system":
                prompt_lines.append(f"System: {content}")
            elif role == "ai":
                prompt_lines.append(f"Cashier: {content}")
            else:
                prompt_lines.append(f"Customer: {content}")

        full_prompt = "\n".join(prompt_lines[-6:])

        try:
            url = f"{BASE_URL}/{self.model_name}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            body = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 256,
                }
            }
            with httpx.Client(timeout=8.0) as client:
                res = client.post(url, headers=headers, json=body)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            return AIMessage(content=text)
        except Exception as e:
            print(f"Gemini API call warning: {e}")

        # Natural conversational fallback
        return AIMessage(content="Welcome to Burger King! We have flame-grilled burgers, crispy sides, cold drinks, and desserts. What can I get for you?")


model = GeminiRestModel()
print("CASHIER MODEL INITIALIZED: Gemini 3.8 Flash (REST)")