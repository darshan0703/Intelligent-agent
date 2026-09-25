"""
app/intelligence/recommendation/signals/inventory_signal.py
Calculates score based on stock levels and expiry urgency.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore


class InventorySignal:
    name = "inventory_pressure"

    def __init__(self, weight: float = 0.25):
        self.weight = weight

    def score(self, item: MenuItem) -> SignalScore:
        if not item.inventory or item.inventory.stock <= 0:
            return SignalScore(
                signal_name=self.name,
                raw_score=0.0,
                weight=self.weight,
                explanation="Out of stock",
            )

        stock = item.inventory.stock
        stock_score = min(1.0, stock / 50.0)

        expiry_score = 0.0
        days = item.days_to_expiry
        if days is not None:
            if days <= 3:
                expiry_score = 1.0
            elif days <= 7:
                expiry_score = 0.7
            elif days <= 14:
                expiry_score = 0.4
            else:
                expiry_score = 0.1

        combined = 0.6 * stock_score + 0.4 * expiry_score
        return SignalScore(
            signal_name=self.name,
            raw_score=combined,
            weight=self.weight,
            explanation=f"Stock={stock}, DaysToExpiry={days}",
        )
