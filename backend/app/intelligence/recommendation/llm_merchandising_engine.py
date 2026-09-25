"""
app/intelligence/recommendation/llm_merchandising_engine.py
Deterministic Merchandising Presentation Engine & Policy Governance.
- LLM generation is removed from the recommendation path; badges and reason copy come
  strictly from the deterministic `badge_rules` table via PresentationLayer.
- Micro-deals and discounts are disabled while `deals_enabled = False`.
- Preserves the underlying margin-constrained discount calculation and LLM copy functions
  intact for future reversal without rebuilding.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from app.config.settings import get_settings
from app.domain.catalog.entities import MenuItem
from app.infrastructure.llm.hybrid_llm_adapter import HybridLLMAdapter
from app.intelligence.recommendation.presentation import BADGE_RULES, PresentationLayer
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)

TRACE_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "observability",
    "logs",
    "cognitive_traces.jsonl",
)

MERCHANDISING_SYSTEM_PROMPT = """You are the Chief Culinary Merchandiser and Behavioral Conversion Strategist for Burger King (TheAtom).
Your task is to IMPROVISE hyper-persuasive, appetizing, and context-aware merchandising copy to convince diners and manifest purchases.

ANALYSIS GUIDELINES:
1. Dynamic Emotional Headline & Subline:
   - Must be witty, appetizing, and directly responsive to their basket state.
   - If cart has premium cold drink/juice: Focus on hot, savory, flame-grilled food essentials to balance cold liquid.
   - If cart has entry-level budget item: Focus on smart pocket-friendly micro-upgrades and value additions.
   - If cart is empty: Hook them based on the current biological craving phase (e.g. lunch energy or late night indulgence).
2. Item Merchandising & Sensory Rationale:
   - For each candidate item, craft a punchy psychological badge (e.g. '🔥 Chef's Flame Match', '⭐ 92% Pair This', '❄️ Calms The Spice', '🍫 Velvet Indulgence', '⚡ Must-Have Side').
   - Provide a 1-sentence sensory rationale explaining why this taste/texture/temperature complements their order.
   - Assign a synergy multiplier between 0.6 (low relevance) and 1.8 (exceptional pairing).
3. Manifestation Micro-Deals (<10% Discount Rule):
   - You may attach a dynamic micro-deal to 1 or 2 high-synergy items to trigger instant conversion.
   - STRICT CONSTRAINT: The discount MUST BE LESS THAN 10% (between 5% and 9.5% off the original price).
   - Compute clean rounded offer_price in Indian Rupees (₹).
   - Provide a deal_tag (e.g. '⚡ Flash Add-On (Save ₹6)').
4. Manifestation Nudge / Social Proof:
   - A single compelling social proof or FOMO hook line (e.g. '🔥 84% of diners who ordered Cold Coffee added Golden Fries today!').
5. STRICT TONE & VOCABULARY INVARIANT:
   - NEVER write the words 'dynamic', 'AI', 'algorithmic', 'recommendation engine', or technical jargon in headlines, sublines, or badges.
   - All text is shown directly to human guests on restaurant kiosks. Use warm, natural culinary phrasing (e.g. 'Pairs Best With', 'Chef's Picks', 'Hand-Crafted Favorites').
   - Sensory rationales MUST match reality: drinks are chilled/fizzy/creamy/aromatic (NEVER flame-grilled!), sides are crispy/golden/savory, desserts are cool/creamy/sweet.

OUTPUT FORMAT: Return ONLY valid JSON conforming to:
{
  "headline": "<appetizing headline>",
  "subline": "<compelling context subline>",
  "manifestation_nudge": "<social proof / FOMO hook>",
  "items": {
    "<item_id>": {
      "badge": "<psychological badge>",
      "sensory_rationale": "<1-sentence culinary hook>",
      "synergy_score": <float 0.6-1.8>,
      "has_micro_deal": <true/false>,
      "discount_pct": <integer 5-9>,
      "offer_price": <float>,
      "deal_tag": "<badge label e.g. ⚡ Flash Deal (Save ₹6)>"
    }
  }
}
"""

DETERMINISTIC_REASONS: dict[str, str] = {
    "top_score_in_slot": "Top recommended pairing to complete your meal",
    "meal_completer": "Essential companion to complete your tray",
    "circadian_boost": "Refreshing guest favorite for this time of day",
    "sensory_contrast": "Crisp, balanced flavor contrast to complement your order",
    "co_purchase": "Frequently ordered together by guests",
    "popularity": "All-time guest favorite at Burger King",
    "budget_fit": "Great value addition packed with flavor",
    "bandit_exploration": "Discover a flavorful new addition to your order",
    "fallback_curated": "Chef's curated pairing selection",
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 45.0
_session_impressions: dict[str, dict[int, int]] = {}


def record_impressions(session_id: str, item_ids: list[int]):
    if session_id not in _session_impressions:
        _session_impressions[session_id] = {}
    for cid in item_ids:
        _session_impressions[session_id][cid] = _session_impressions[session_id].get(cid, 0) + 1


def get_impression_penalty(session_id: str, item_id: int) -> float:
    count = _session_impressions.get(session_id, {}).get(item_id, 0)
    if count == 0:
        return 1.15  # Fresh un-viewed novelty boost!
    elif count == 1:
        return 1.0
    elif count == 2:
        return 0.85
    else:
        return 0.70  # Rotate stale items out of view on re-navigation


def calculate_margin_constrained_deal(
    it: MenuItem,
    orig_price: float,
    raw_offer: float | None = None,
    deals_enabled: bool | None = None,
) -> tuple[bool, float, int, str | None]:
    """
    Margin-Constrained Discounting (v4 §8):
      discount <= (item_margin - minimum_acceptable_margin)
      capped at 9.5% for kiosk micro-deals.
    Preserved intact behind policy flag `deals_enabled`.
    While `deals_enabled = False`:
      returns (False, orig_price, 0, None) unconditionally.
    """
    settings = get_settings()
    is_enabled = settings.deals_enabled if deals_enabled is None else deals_enabled
    if not is_enabled:
        return False, orig_price, 0, None

    if orig_price <= 20:
        return False, orig_price, 0, None

    item_margin = getattr(it, "margin", None)
    if item_margin is None:
        item_margin = 0.35  # Conservative default 35% margin
    min_margin = 0.15      # 15% floor for healthy unit economics
    max_allowed_discount_pct = max(0.0, float(item_margin) - min_margin)
    capped_discount_pct = min(max_allowed_discount_pct, 0.095)

    if raw_offer is None:
        raw_offer = orig_price * (1.0 - capped_discount_pct)

    min_allowed = orig_price * (1.0 - capped_discount_pct)
    if raw_offer < min_allowed:
        raw_offer = round(min_allowed, 1)

    if raw_offer < orig_price and capped_discount_pct >= 0.03:
        offer_price = round(raw_offer, 0)
        discount_pct = int(round(((orig_price - offer_price) / orig_price) * 100))
        discount_pct = max(1, min(int(capped_discount_pct * 100), discount_pct))
        savings = int(orig_price - offer_price)
        deal_tag = f"⚡ Flash Deal (Save ₹{savings})"
        return True, offer_price, discount_pct, deal_tag

    return False, orig_price, 0, None


class LLMMerchandisingEngine:
    """
    Deterministic merchandising engine.
    - Badges come exclusively from `badge_rules` via PresentationLayer.
    - Discounts are disabled behind `deals_enabled` policy flag.
    - Zero runtime LLM network calls for recommendation shelves.
    - Preserves underlying LLM generation & margin calculations for reversibility.
    """

    def __init__(self, llm_adapter: LanguageModelPort | None = None):
        self.settings = get_settings()
        self.llm = llm_adapter or HybridLLMAdapter()
        try:
            os.makedirs(os.path.dirname(TRACE_LOG_PATH), exist_ok=True)
        except Exception:
            pass

    def _get_cache_key(
        self,
        session_id: str,
        category: str,
        cart_summary: list[dict[str, Any]],
        circadian_phase: str,
    ) -> str:
        cart_sig = hashlib.md5(json.dumps(cart_summary, sort_keys=True).encode("utf-8")).hexdigest()[:8]
        return f"{session_id}:{category}:{circadian_phase}:{cart_sig}"

    async def improvise_merchandising(
        self,
        session_id: str,
        category: str,
        cart_items: list[dict[str, Any]],
        candidates: list[MenuItem],
        circadian_phase: str = "lunch",
        session_behavior: dict[str, Any] | None = None,
        dietary_preference: str | None = None,
        force_legacy_llm: bool = False,
        candidate_signals: dict[int, dict[str, float]] | None = None,
    ) -> dict[str, Any]:
        """
        Deterministic merchandising presentation:
        - Resolves badges and reasons strictly from deterministic tables (0ms, byte-identical).
        - Zero deals when `deals_enabled = False`.
        - If `force_legacy_llm` is explicitly True, invokes preserved legacy LLM method.
        """
        if force_legacy_llm:
            return await self.legacy_llm_improvise(
                session_id=session_id,
                category=category,
                cart_items=cart_items,
                candidates=candidates,
                circadian_phase=circadian_phase,
                session_behavior=session_behavior,
                dietary_preference=dietary_preference,
            )

        if not candidates:
            return {
                "headline": "Curated For You",
                "subline": "Delicious picks for your visit",
                "manifestation_nudge": "Freshly prepared to order",
                "items": {},
            }

        cart_summary = [
            {
                "id": c.get("item_id") or c.get("id"),
                "name": c.get("item_name") or c.get("name"),
                "price": float(c.get("unit_price") or c.get("price") or 0.0),
                "category": c.get("category", "general"),
            }
            for c in cart_items
        ]

        # Check Cache for instant repeat performance
        cache_key = self._get_cache_key(session_id, category, cart_summary, circadian_phase)
        now = time.monotonic()
        if cache_key in _cache:
            ts, cached_val = _cache[cache_key]
            if now - ts < CACHE_TTL_SECONDS:
                return cached_val

        # Sort candidates using impression penalty to rotate fresh choices into view on refresh
        rotated_candidates = sorted(
            candidates,
            key=lambda c: get_impression_penalty(session_id, c.id),
            reverse=True,
        )

        has_expensive_drink = any(
            "drink" in str(c.get("category", "")).lower() and float(c.get("unit_price") or c.get("price") or 0) >= 110.0
            for c in cart_items
        )
        is_budget = any(float(c.get("unit_price") or c.get("price") or 0) <= 75.0 for c in cart_items)

        if has_expensive_drink:
            headline = "Essential Bites to Pair with Your Drink"
            subline = "Hot savory favorites to balance your beverage"
            nudge = "Freshly prepared to order with pure ingredients"
        elif is_budget:
            headline = "Value Favorites & Add-Ons"
            subline = "Delicious additions that maximize your meal"
            nudge = "Unbeatable taste prepared fresh on order"
        elif circadian_phase == "late_night":
            headline = "Late Night Craving Picks"
            subline = "Satisfy your late night appetite with warm favorites"
            nudge = "Freshly baked sweet treats & hot savory sides"
        else:
            headline = "Curated For You"
            subline = "Hand-picked favorites to complete your meal"
            nudge = "Freshly prepared to order with 100% pure ingredients"

        sanitized_items = {}
        for idx, it in enumerate(rotated_candidates):
            orig_price = float(it.price.amount)
            cand_signals = (candidate_signals or {}).get(it.id)

            # Deterministic reason code assignment based on candidate context & signals
            if cand_signals:
                reason_code = PresentationLayer.get_top_reason_code(cand_signals)
            elif idx == 0:
                reason_code = "top_score_in_slot"
            elif any(c in str(it.category.value if hasattr(it.category, "value") else it.category).lower() for c in ["drink", "side"]):
                reason_code = "sensory_contrast"
            elif circadian_phase in ["snack", "late_night"]:
                reason_code = "circadian_boost"
            else:
                reason_code = "meal_completer"

            # Badge resolution: strictly from PresentationLayer / badge_rules table
            b_text, b_icon = PresentationLayer.resolve_badge(reason_code)
            if not b_text:
                badge = "Recommended For You"
            else:
                badge = f"{b_icon} {b_text}".strip() if b_icon else b_text

            reason = DETERMINISTIC_REASONS.get(reason_code, "Recommended to complement your meal")
            synergy = 1.0 * get_impression_penalty(session_id, it.id)

            # Deal assembly: strictly disabled when deals_enabled == False
            has_deal, offer_price, discount_pct, deal_tag = calculate_margin_constrained_deal(
                it, orig_price, deals_enabled=self.settings.deals_enabled
            )

            sanitized_items[it.id] = {
                "badge": badge,
                "sensory_rationale": reason,
                "synergy_score": synergy,
                "has_micro_deal": has_deal,
                "original_price": orig_price,
                "offer_price": offer_price,
                "discount_pct": discount_pct,
                "deal_tag": deal_tag,
            }

        result = {
            "headline": headline,
            "subline": subline,
            "manifestation_nudge": nudge,
            "items": sanitized_items,
        }

        _cache[cache_key] = (now, result)
        record_impressions(session_id, list(sanitized_items.keys()))
        return result

    async def legacy_llm_improvise(
        self,
        session_id: str,
        category: str,
        cart_items: list[dict[str, Any]],
        candidates: list[MenuItem],
        circadian_phase: str = "lunch",
        session_behavior: dict[str, Any] | None = None,
        dietary_preference: str | None = None,
        deals_enabled: bool = True,
    ) -> dict[str, Any]:
        """
        PRESERVED UNREACHABLE FUNCTION (Phase 1 Invariant #5):
        Retains the original LLM copy generation and margin-clamped discount logic.
        Can be re-enabled if policy changes in the future without a rebuild.
        """
        cart_summary = [
            {
                "id": c.get("item_id") or c.get("id"),
                "name": c.get("item_name") or c.get("name"),
                "price": float(c.get("unit_price") or c.get("price") or 0.0),
                "category": c.get("category", "general"),
            }
            for c in cart_items
        ]
        candidate_summary = [
            {
                "id": it.id,
                "name": it.name,
                "category": str(it.category.value if hasattr(it.category, "value") else it.category),
                "price": float(it.price.amount),
                "description": it.short_description or "",
            }
            for it in candidates[:8]
        ]
        user_payload = {
            "session_id": session_id,
            "category_viewed": category,
            "circadian_phase": circadian_phase,
            "cart_items": cart_summary,
            "dietary_preference": dietary_preference,
            "session_behavior": session_behavior or {},
            "candidates": candidate_summary,
        }
        full_prompt = (
            f"{MERCHANDISING_SYSTEM_PROMPT}\n\n"
            f"CUSTOMER CONTEXT:\n{json.dumps(user_payload, indent=2)}\n\n"
            f"Return ONLY valid JSON:"
        )

        try:
            response_text = await asyncio.wait_for(
                self.llm.generate_text(full_prompt),
                timeout=2.2,
            )
            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
                clean_json = re.sub(r"\n?```$", "", clean_json)

            data = json.loads(clean_json)
            sanitized_items = {}
            raw_items = data.get("items", {})
            candidate_map = {c.id: c for c in candidates}

            for cid_str, merch in raw_items.items():
                try:
                    cid = int(cid_str)
                except ValueError:
                    continue
                if cid not in candidate_map:
                    continue

                it = candidate_map[cid]
                orig_price = float(it.price.amount)
                badge = str(merch.get("badge") or "🔥 Top Pick")
                reason = str(merch.get("sensory_rationale") or "Appetizing complement to your order")
                synergy = float(merch.get("synergy_score") or 1.0)
                synergy = max(0.5, min(2.0, synergy))

                has_deal = bool(merch.get("has_micro_deal", False))
                raw_offer = float(merch.get("offer_price", orig_price)) if has_deal else None
                deal_ok, offer_price, discount_pct, deal_tag = calculate_margin_constrained_deal(
                    it, orig_price, raw_offer=raw_offer, deals_enabled=deals_enabled
                )
                if deal_ok and merch.get("deal_tag"):
                    deal_tag = merch.get("deal_tag")

                sanitized_items[cid] = {
                    "badge": badge,
                    "sensory_rationale": reason,
                    "synergy_score": synergy,
                    "has_micro_deal": deal_ok,
                    "original_price": orig_price,
                    "offer_price": offer_price,
                    "discount_pct": discount_pct,
                    "deal_tag": deal_tag,
                }

            return {
                "headline": str(data.get("headline") or "Curated For You"),
                "subline": str(data.get("subline") or "Tailored to your taste & basket"),
                "manifestation_nudge": str(data.get("manifestation_nudge") or "🔥 Hand-crafted fresh for you"),
                "items": sanitized_items,
            }
        except Exception:
            return self._heuristic_fallback(candidates, cart_items, category, circadian_phase, session_id)

    def _heuristic_fallback(
        self,
        candidates: list[MenuItem],
        cart_items: list[dict[str, Any]],
        category: str,
        circadian_phase: str,
        session_id: str = "default-session",
    ) -> dict[str, Any]:
        """Instant deterministic fallback if needed."""
        items = {}
        for idx, it in enumerate(candidates):
            orig_p = float(it.price.amount)
            has_deal, offer_p, disc_pct, deal_tag = calculate_margin_constrained_deal(
                it, orig_p, deals_enabled=self.settings.deals_enabled
            )
            reason_code = "top_score_in_slot" if idx == 0 else "sensory_contrast"
            b_text, b_icon = PresentationLayer.resolve_badge(reason_code)
            badge = f"{b_icon} {b_text}".strip() if b_icon else (b_text or "Recommended For You")
            reason = DETERMINISTIC_REASONS.get(reason_code, "Recommended to complement your meal")

            items[it.id] = {
                "badge": badge,
                "sensory_rationale": reason,
                "synergy_score": 1.0,
                "has_micro_deal": has_deal,
                "original_price": orig_p,
                "offer_price": offer_p,
                "discount_pct": disc_pct,
                "deal_tag": deal_tag,
            }

        return {
            "headline": "Curated For You",
            "subline": "Hand-picked favorites to complete your meal",
            "manifestation_nudge": "Freshly prepared to order with pure ingredients",
            "items": items,
        }
