"""
app/intelligence/recommendation/signals/popularity_signal.py
Scores items according to popularity priors / sales volume.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore


class PopularitySignal:
    name = "popularity"

    def __init__(self, weight: float = 0.30):
        self.weight = weight
        self._default_priors = {
            "whopper": 0.95,
            "whopper jr": 0.88,
            "crispy chicken burger": 0.90,
            "classic fries": 0.92,
            "king peri peri fries": 0.85,
            "coke": 0.90,
            "cold coffee": 0.80,
            "bk fusion sundae": 0.75,
        }

    def score(self, item: MenuItem) -> SignalScore:
        item_key = item.name.lower()
        prior = self._default_priors.get(item_key, 0.50)
        return SignalScore(
            signal_name=self.name,
            raw_score=prior,
            weight=self.weight,
            explanation=f"Historical popularity prior: {prior:.2f}",
        )
