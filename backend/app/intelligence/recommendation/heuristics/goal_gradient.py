"""
app/intelligence/recommendation/heuristics/goal_gradient.py
The Goal Gradient Threshold (Cart Gamification & Reward Acceleration)
- Reads reward_threshold (e.g. ₹299 for Free Delivery, ₹350 for Free Surprise Dip).
- If cart total is within 25% of the threshold, prioritizes candidates priced in the exact gap window.
- Frames the recommendation around unlocking the reward rather than just selling an item.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from app.domain.catalog.entities import MenuItem


class GoalGradientAnalyzer:
    @staticmethod
    def evaluate_goal_gradient(
        cart_total: Decimal,
        candidate_item: MenuItem,
        reward_threshold: Decimal | None = Decimal("299.00"),
        reward_name: str = "Free Delivery",
    ) -> tuple[float, str | None]:
        """
        Calculates score boost and framing text if candidate helps bridge the threshold gap.
        Returns (boost_bonus: float, framing_hint: str | None).
        """
        if reward_threshold is None or reward_threshold <= Decimal("0"):
            return 0.0, None

        if cart_total >= reward_threshold:
            # Reward already achieved
            return 0.0, None

        gap = reward_threshold - cart_total
        distance_ratio = float(gap / reward_threshold)

        # Check if cart is within striking distance (within 30% of threshold)
        if distance_ratio > 0.35:
            return 0.0, None

        item_price = candidate_item.price.amount if hasattr(candidate_item.price, "amount") else Decimal(str(candidate_item.price))

        # Check if candidate lands right at or just slightly above the gap
        # Item price between (gap - 20) and (gap + 30)
        min_fit = max(Decimal("10.00"), gap - Decimal("25.00"))
        max_fit = gap + Decimal("40.00")

        if min_fit <= item_price <= max_fit:
            # High psychological resonance
            boost = 0.50
            framing = f"Add {candidate_item.name} for Rs.{item_price:.0f} to unlock {reward_name}!"
            return boost, framing

        return 0.0, None
