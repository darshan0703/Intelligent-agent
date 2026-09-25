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
        # Category base priors - no hardcoded item names!
        self._category_priors = {
            "burger": 0.70,
            "side": 0.65,
            "drink": 0.65,
            "dessert": 0.60,
        }

    def score(self, item: MenuItem) -> SignalScore:
        cat = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
        base_prior = self._category_priors.get(cat, 0.60)
        # Smooth with display_order if present (top display order gets small boost up to +0.20)
        disp = getattr(item, "display_order", None)
        if disp is not None and disp > 0:
            order_factor = max(0.0, (20 - min(disp, 20)) / 100.0)
            prior = min(0.95, base_prior + order_factor)
        else:
            prior = base_prior

        return SignalScore(
            signal_name=self.name,
            raw_score=prior,
            weight=self.weight,
            explanation=f"Category popularity prior: {prior:.2f}",
        )
