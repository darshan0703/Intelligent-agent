"""
app/intelligence/recommendation/signals/session_signal.py
Contextual relevance signal based on current session and cart.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore
from app.domain.session.entities import SessionState


class SessionSignal:
    name = "session_affinity"

    def __init__(self, weight: float = 0.25):
        self.weight = weight

    def score(self, item: MenuItem, session: SessionState, cart_item_ids: set[int]) -> SignalScore:
        raw = 0.50
        reasons = []

        if session.food_preference:
            pref = session.food_preference.lower()
            item_type = str(item.food_type).lower() if item.food_type else ""
            if pref == "veg" and "veg" in item_type and "non" not in item_type:
                raw += 0.30
                reasons.append("Matches veg preference")
            elif pref in ("non_veg", "non veg") and "non" in item_type:
                raw += 0.30
                reasons.append("Matches non-veg preference")

        if session.last_category and session.last_category.lower() == str(item.category).lower():
            raw += 0.15
            reasons.append("Matches active browsing category")

        if item.id in cart_item_ids:
            raw -= 0.35
            reasons.append("Already in cart (penalize duplicate)")

        raw = max(0.0, min(1.0, raw))
        return SignalScore(
            signal_name=self.name,
            raw_score=raw,
            weight=self.weight,
            explanation=", ".join(reasons) if reasons else "Neutral session context",
        )
