"""
app/intelligence/recommendation/signals/crosssell_signal.py
Scores items based on explicit pairing rules with current cart contents.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore


class CrossSellSignal:
    name = "cross_sell"

    def __init__(self, weight: float = 0.20):
        self.weight = weight

    def score(self, item: MenuItem, cross_sell_candidate_ids: set[int]) -> SignalScore:
        if item.id in cross_sell_candidate_ids:
            raw = 0.90
            exp = "Explicit pairing match with current cart"
        else:
            raw = 0.20
            exp = "Standard complement candidate"

        return SignalScore(
            signal_name=self.name,
            raw_score=raw,
            weight=self.weight,
            explanation=exp,
        )
