"""
app/intelligence/recommendation/heuristics/basket_elasticity.py
Basket-Level Checkout Elasticity & Harmonic Mean Price Anchoring (v4.0).

At checkout and cart drawer view, anchoring recommendations to a single item is flawed.
This engine calculates the Harmonic Mean Price of the current basket:
    P_harmonic = n / sum(1 / P_i)
Harmonic mean dampens the distortion of single high-priced outliers (e.g., one ₹249 Frappe in a ₹59 order),
ensuring impulse add-ons respect the customer's true spending willingness and avoid checkout drop-off.
"""
from __future__ import annotations
from typing import Any
from app.domain.catalog.entities import MenuItem


class BasketElasticityAnalyzer:
    """Calculates harmonic basket anchor and impulse elasticity thresholds."""

    @staticmethod
    def calculate_harmonic_anchor(cart_lines: list[Any]) -> float:
        """
        Calculates harmonic mean price of items in cart.
        Falls back to 100.0 if cart is empty.
        """
        if not cart_lines:
            return 100.0

        prices: list[float] = []
        for line in cart_lines:
            p = getattr(line, "unit_price", line.get("price") if isinstance(line, dict) else None)
            if p is not None:
                val = float(p.amount if hasattr(p, "amount") else p)
                if val > 0:
                    prices.append(val)

        if not prices:
            return 100.0

        # Harmonic Mean: n / sum(1 / P_i)
        try:
            sum_reciprocal = sum(1.0 / p for p in prices)
            if sum_reciprocal <= 0:
                return sum(prices) / len(prices)
            return len(prices) / sum_reciprocal
        except ZeroDivisionError:
            return 100.0

    @classmethod
    def get_checkout_impulse_ceiling(cls, cart_lines: list[Any]) -> float:
        """
        Calculates the maximum recommended add-on price at checkout to prevent cart abandonment.
        - Budget Basket (Harmonic <= 80): Max impulse item <= ₹55.0 (dips, softies, float upgrades).
        - Mid Basket (Harmonic 80-160): Max impulse item <= 0.45 * Harmonic Anchor.
        - Premium Basket (Harmonic > 160): Max impulse item <= 0.60 * Harmonic Anchor.
        """
        h_anchor = cls.calculate_harmonic_anchor(cart_lines)

        if h_anchor <= 80.0:
            return 55.0
        elif h_anchor <= 160.0:
            return max(60.0, h_anchor * 0.45)
        else:
            return max(85.0, h_anchor * 0.55)

    @classmethod
    def evaluate_checkout_proximity_score(
        cls, candidate: MenuItem, cart_lines: list[Any]
    ) -> float:
        """
        Evaluates continuous proximity score for checkout impulse add-on against basket elasticity.
        """
        p_cand = float(candidate.price.amount)
        ceiling = cls.get_checkout_impulse_ceiling(cart_lines)
        h_anchor = cls.calculate_harmonic_anchor(cart_lines)

        if p_cand > ceiling:
            # Drop off smoothly if it exceeds impulse ceiling
            ratio = p_cand / ceiling
            return max(0.05, (1.0 / ratio) ** 2.5)
        else:
            # Reward low-friction impulse add-ons (sub-₹45 gets highest impulse score)
            if p_cand <= 45.0:
                return 1.40
            elif p_cand <= 65.0:
                return 1.15
            else:
                return 1.00
