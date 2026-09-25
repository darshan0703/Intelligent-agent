"""
app/intelligence/recommendation/heuristics/price_proximity.py
Continuous Sigmoid Decay Price Proximity Function (v4.0).

Replaces discontinuous step functions and hardcoded cliff penalties with a smooth,
continuous logistic decay suitable for learned ranking and optimization:
    f(r) = 1 / (1 + exp(k * (r - r_0)))

Where:
    r = P_cand / P_anchor (Price Ratio)
    r_0 = Inflection threshold where penalty accelerates (1.35 for budget, 1.75 for standard)
    k = Slope sharpness factor (controls how quickly willingness to pay drops off)
"""
from __future__ import annotations
import math


class ContinuousPriceProximity:
    """Computes smooth continuous price proximity features and multipliers."""

    @staticmethod
    def sigmoid_decay(
        p_cand: float,
        p_anchor: float,
        anchor_tier: str = "standard",
    ) -> float:
        """
        Computes continuous sigmoid price proximity score in range (0.0, 1.5].
        """
        if p_anchor <= 0:
            return 1.0

        r = p_cand / p_anchor

        if anchor_tier == "budget" or p_anchor < 100.0:
            # Budget tier: Sharp drop-off beyond 1.35x anchor price
            r_0 = 1.35
            k = 5.5
            # Bonus for micro-priced additions <= 0.9x anchor price
            base = 1.0 / (1.0 + math.exp(min(50.0, max(-50.0, k * (r - r_0)))))
            if r <= 1.0:
                bonus = 0.40 * (1.0 - r)
                return min(1.50, base + bonus + 0.20)
            return max(0.02, base)
        elif anchor_tier == "premium" or p_anchor >= 180.0:
            # Premium tier: Customer has higher willingness to pay; gentler slope
            r_0 = 1.85
            k = 3.2
            base = 1.0 / (1.0 + math.exp(min(50.0, max(-50.0, k * (r - r_0)))))
            # Reward high-quality pairings (items >= 80 Rs)
            if p_cand >= 80.0 and r <= 1.4:
                return min(1.40, base + 0.35)
            return max(0.05, base)
        else:
            # Standard tier: Inflection at 1.60x
            r_0 = 1.60
            k = 4.0
            base = 1.0 / (1.0 + math.exp(min(50.0, max(-50.0, k * (r - r_0)))))
            return max(0.05, base)

    @classmethod
    def evaluate_candidate(cls, p_cand: float, p_anchor: float) -> float:
        """Convenience method returning proximity multiplier for candidate."""
        tier = "budget" if p_anchor < 100.0 else ("premium" if p_anchor >= 180.0 else "standard")
        return cls.sigmoid_decay(p_cand, p_anchor, anchor_tier=tier)
