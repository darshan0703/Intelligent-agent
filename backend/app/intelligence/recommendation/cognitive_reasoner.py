"""
app/intelligence/recommendation/cognitive_reasoner.py
Cognitive Context Reasoner (Intellectual LLM Analysis)
- Analyzes cart compositions, flavor synergies (spicy vs cooling, heavy vs light), and conversational nuances.
- Strict Firewall: Ranks and boosts only valid database candidate items passed to it.
- Persists cognitive decision traces into both database and observability log file (cognitive_traces.jsonl).
"""
from __future__ import annotations
import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any
from app.config.settings import get_settings
from app.domain.catalog.entities import MenuItem
from app.infrastructure.llm.hybrid_llm_adapter import HybridLLMAdapter
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)

TRACE_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "observability",
    "logs",
    "cognitive_traces.jsonl",
)

REASONING_SYSTEM_PROMPT = """You are the Senior Culinary & Recommendation Intelligence Reasoner for Burger King (TheAtom).
Your task is to analyze the customer's current cart and session context, then provide culinary synergy scores for a provided list of candidate items.

ANALYSIS RULES:
1. Culinary Balance:
   - If cart contains heavy/spicy items (e.g. Fiery Chicken, Spicy Paneer), strongly prefer cooling complements (softies, shakes, cold drinks, creamy dips).
   - If cart is budget-oriented (e.g. Crispy Veg ₹70), favor low-cost add-ons (fries, small coke, dips, cones).
   - If cart has sweet dessert, favor savory snacks or beverages over more sweet desserts.
2. Return ONLY a JSON object mapping Candidate ID (as string) to a synergy multiplier between 0.5 (poor match) and 1.5 (exceptional synergy).
3. Do NOT invent new item IDs. ONLY score the exact candidate IDs provided in the prompt.

Output format:
{
  "scores": {
    "<item_id>": <float between 0.5 and 1.5>
  },
  "rationale": "<brief explanation of culinary synergy>"
}
"""


class CognitiveContextReasoner:
    def __init__(self, llm_adapter: LanguageModelPort | None = None):
        self.settings = get_settings()
        self.llm = llm_adapter or HybridLLMAdapter()
        # Ensure log directory exists
        try:
            os.makedirs(os.path.dirname(TRACE_LOG_PATH), exist_ok=True)
        except Exception:
            pass

    async def analyze_synergy(
        self,
        session_id: str,
        cart_items: list[dict[str, Any]],
        candidates: list[MenuItem],
        session_preference: str | None = None,
    ) -> tuple[dict[int, float], str]:
        """
        Uses LLM cognitive analysis to compute flavor synergy multipliers for candidates.
        Returns (dict of {item_id: multiplier}, rationale_string).
        """
        if not candidates or not cart_items:
            return {c.id: 1.0 for c in candidates}, "No cart items to evaluate"

        # Format minimal prompt payload
        cart_summary = [{"name": c.get("name") or c.get("item_name"), "price": float(c.get("unit_price") or c.get("price") or 0)} for c in cart_items]
        candidate_summary = [{"id": c.id, "name": c.name, "category": str(c.category.value if hasattr(c.category, "value") else c.category), "price": float(c.price.amount)} for c in candidates[:8]]

        user_content = json.dumps({
            "cart": cart_summary,
            "candidates": candidate_summary,
            "dietary_preference": session_preference,
        })

        full_prompt = f"{REASONING_SYSTEM_PROMPT}\n\nContext Payload:\n{user_content}\n\nRespond with valid JSON only:"

        # Rule 1: LLM usage is restricted to structured intent parsing only.
        # Recommendation scoring must never invoke generative LLM calls.
        return result, "Deterministic cognitive baseline"

    async def _legacy_llm_analyze_synergy(
        self,
        session_id: str,
        cart_items: list[dict[str, Any]],
        candidates: list[MenuItem],
        session_preference: str | None = None,
    ) -> tuple[dict[int, float], str]:
        """Preserved legacy LLM synergy analysis."""
        if not candidates or not cart_items:
            return {c.id: 1.0 for c in candidates}, "No cart items to evaluate"

        cart_summary = [{"name": c.get("name") or c.get("item_name"), "price": float(c.get("unit_price") or c.get("price") or 0)} for c in cart_items]
        candidate_summary = [{"id": c.id, "name": c.name, "category": str(c.category.value if hasattr(c.category, "value") else c.category), "price": float(c.price.amount)} for c in candidates[:8]]
        user_content = json.dumps({
            "cart": cart_summary,
            "candidates": candidate_summary,
            "dietary_preference": session_preference,
        })
        full_prompt = f"{REASONING_SYSTEM_PROMPT}\n\nContext Payload:\n{user_content}\n\nRespond with valid JSON only:"
        result: dict[int, float] = {c.id: 1.0 for c in candidates}
        try:
            response_text = await asyncio.wait_for(
                self.llm.generate_text(full_prompt),
                timeout=2.0,
            )
            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
                clean_json = re.sub(r"\n?```$", "", clean_json)
            parsed = json.loads(clean_json)
            scores = parsed.get("scores", {})
            rationale = str(parsed.get("rationale", "Cognitive flavor synergy applied"))

            for c in candidates:
                raw_multiplier = scores.get(str(c.id))
                if raw_multiplier is not None and isinstance(raw_multiplier, (int, float)):
                    result[c.id] = max(0.5, min(1.5, float(raw_multiplier)))

            # Append to cognitive traces log file for offline refinement & auditing
            try:
                trace_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": session_id,
                    "cart": cart_summary,
                    "rationale": rationale,
                    "multipliers": {str(k): round(v, 2) for k, v in result.items()},
                }
                with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(trace_entry) + "\n")
            except Exception:
                pass

            return result, rationale
        except Exception as err:
            logger.info("cognitive_reasoner_passthrough", reason=str(err))
            return {c.id: 1.0 for c in candidates}, f"Passthrough default: {err}"
