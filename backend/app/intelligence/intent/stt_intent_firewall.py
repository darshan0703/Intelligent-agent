"""
app/intelligence/intent/stt_intent_firewall.py
Grok STT Intent Engine & Strict LLM Firewall
- Parses noisy, colloquial speech-to-text transcripts (English & Hinglish) into structured filter parameters.
- Strict Firewall: Prohibits the LLM from inventing products, prices, or inventory numbers.
  All actual pricing, availability, and item lookups are strictly performed by the database repository.
"""
from __future__ import annotations
import json
import re
from typing import Any
from app.config.settings import get_settings
from app.infrastructure.llm.hybrid_llm_adapter import HybridLLMAdapter
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)

INTENT_EXTRACTION_SYSTEM_PROMPT = """You are the Natural Language Intent Extraction Firewall for Burger King Kiosk (TheAtom).
Your job is to parse noisy, colloquial user Speech-to-Text (STT) transcripts into a strict structured JSON filter schema.

RULES:
1. Output ONLY valid JSON. No markdown formatting, no conversational text.
2. You CANNOT invent products, prices, calorie counts, or inventory stock.
3. Map customer requests to structured filter parameters only:
   - "action": "navigate" | "filter" | "add_to_cart" | "customize" | "checkout" | "general_query"
   - "target_category": "burger" | "drink" | "side" | "dessert" | null
   - "dietary_preference": "veg" | "non_veg" | "both" | null
   - "keywords": list of string tokens mentioned (e.g., ["whopper", "spicy", "peri peri", "coke"])
   - "quantity": integer (default 1)
   - "urgency": "low" | "medium" | "high"

EXAMPLES:
Input: "bhaiya ek spicy veg burger aur cold drink dikhao"
Output: {"action": "filter", "target_category": "burger", "dietary_preference": "veg", "keywords": ["spicy", "burger", "cold drink"], "quantity": 1, "urgency": "medium"}

Input: "show me some desserts or ice cream"
Output: {"action": "navigate", "target_category": "dessert", "dietary_preference": null, "keywords": ["dessert", "ice cream"], "quantity": 1, "urgency": "low"}

Input: "i only eat pure veg food"
Output: {"action": "filter", "target_category": null, "dietary_preference": "veg", "keywords": ["pure veg"], "quantity": 1, "urgency": "high"}
"""


class STTIntentFirewall:
    def __init__(self, llm_adapter: LanguageModelPort | None = None):
        self.settings = get_settings()
        self.llm = llm_adapter or HybridLLMAdapter()

    def _fast_rule_parser(self, transcript: str) -> dict[str, Any] | None:
        """High-speed 0ms rule parser for common kiosk speech patterns."""
        t = transcript.lower().strip()
        if not t:
            return None

        # Veg / Non-veg explicit triggers
        if any(x in t for x in ["pure veg", "only veg", "shakahari", "show veg", "veg only"]):
            return {
                "action": "filter",
                "target_category": None,
                "dietary_preference": "veg",
                "keywords": ["veg"],
                "quantity": 1,
                "urgency": "high",
            }
        if any(x in t for x in ["non veg", "chicken only", "meat", "nonveg", "show non veg"]):
            return {
                "action": "filter",
                "target_category": None,
                "dietary_preference": "non_veg",
                "keywords": ["non_veg"],
                "quantity": 1,
                "urgency": "high",
            }

        # Direct Category Navigation
        if "burger" in t or "whopper" in t:
            ft = "veg" if "veg" in t and "non" not in t else ("non_veg" if "chicken" in t or "non" in t else None)
            return {
                "action": "navigate",
                "target_category": "burger",
                "dietary_preference": ft,
                "keywords": [w for w in ["whopper", "burger", "spicy", "paneer", "chicken"] if w in t],
                "quantity": 1,
                "urgency": "medium",
            }
        if any(x in t for x in ["drink", "beverage", "coke", "shake", "coffee", "pepsi", "thirst"]):
            return {
                "action": "navigate",
                "target_category": "drink",
                "dietary_preference": None,
                "keywords": ["drink"],
                "quantity": 1,
                "urgency": "medium",
            }
        if any(x in t for x in ["side", "fries", "nugget", "wing", "strip", "snack"]):
            return {
                "action": "navigate",
                "target_category": "side",
                "dietary_preference": None,
                "keywords": ["side", "fries"],
                "quantity": 1,
                "urgency": "medium",
            }
        if any(x in t for x in ["dessert", "sundae", "ice cream", "sweet", "mousse"]):
            return {
                "action": "navigate",
                "target_category": "dessert",
                "dietary_preference": None,
                "keywords": ["dessert"],
                "quantity": 1,
                "urgency": "medium",
            }

        return None

    async def parse_stt_transcript(self, transcript: str) -> dict[str, Any]:
        """
        Extracts structured intent parameters from spoken conversational text with strict firewall guardrails.
        """
        # Step 1: Check fast deterministic rule parser (0ms)
        fast_intent = self._fast_rule_parser(transcript)
        if fast_intent is not None:
            return fast_intent

        # Step 2: Use Grok LLM for complex colloquial / conversational nuances
        try:
            full_prompt = f"{INTENT_EXTRACTION_SYSTEM_PROMPT}\n\nTranscript: \"{transcript}\"\n\nJSON output:"
            response_text = await self.llm.generate_text(full_prompt)
            # Sanitize response
            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
                clean_json = re.sub(r"\n?```$", "", clean_json)
            parsed = json.loads(clean_json)

            # Strict schema validation (Firewall)
            return {
                "action": str(parsed.get("action", "general_query")),
                "target_category": parsed.get("target_category"),
                "dietary_preference": parsed.get("dietary_preference"),
                "keywords": parsed.get("keywords", []),
                "quantity": int(parsed.get("quantity", 1)),
                "urgency": str(parsed.get("urgency", "medium")),
            }
        except Exception as err:
            logger.warning("stt_intent_firewall_fallback", error=str(err), transcript=transcript)
            return {
                "action": "general_query",
                "target_category": None,
                "dietary_preference": None,
                "keywords": [transcript],
                "quantity": 1,
                "urgency": "low",
            }
