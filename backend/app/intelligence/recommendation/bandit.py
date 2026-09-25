"""
app/intelligence/recommendation/bandit.py
Bayesian Multi-Armed Bandit with Thompson Sampling (v4 Specification).

Operates at the (time_bucket x anchor_category x item) arm level:
- Maintains Beta conjugate priors: Beta(alpha, beta)
- Thompson Sampling draws theta ~ Beta(alpha, beta) for active exploration/exploitation.
- Self-corrects: high-converting pairings maintain visibility; low-converting pairings decay naturally.
- Forward-compatible: once user_id exists, the arm key effortlessly narrows to include user_id.
"""
from __future__ import annotations
import random
from typing import Optional


class ThompsonSamplingBandit:
    """In-memory Bayesian Thompson Sampling engine for recommendation arms."""
    # (time_bucket, anchor_category, item_id) -> [alpha, beta]
    _priors: dict[tuple[str, str, int], list[float]] = {}

    @classmethod
    def _normalize_key(cls, time_bucket: str = "general", anchor_category: Any = "general", item_id: Optional[int] = None) -> tuple[str, str, int]:
        if isinstance(anchor_category, int) and item_id is None:
            tb = "general"
            ac = (time_bucket or "general").lower()
            iid = int(anchor_category)
            return (tb, ac, iid)
        tb = (time_bucket or "general").lower()
        ac = (str(anchor_category) if anchor_category else "general").lower()
        iid = int(item_id or 0)
        return (tb, ac, iid)

    @classmethod
    def get_prior(
        cls,
        time_bucket: str = "general",
        anchor_category: Any = "general",
        item_id: Optional[int] = None,
    ) -> tuple[float, float]:
        key = cls._normalize_key(time_bucket, anchor_category, item_id)
        if key not in cls._priors:
            # Baseline prior: Beta(1.5, 3.0) assuming ~33% uninformative CTR
            cls._priors[key] = [1.5, 3.0]
        alpha, beta = cls._priors[key]
        return alpha, beta

    @classmethod
    def sample_theta(
        cls,
        time_bucket: str = "general",
        anchor_category: Any = "general",
        item_id: Optional[int] = None,
        deterministic: bool = True,
    ) -> float:
        """
        Deterministic expected success probability E[theta] = alpha / (alpha + beta).
        Discards random jitter to protect kitchen operations and inventory flow.
        """
        alpha, beta = cls.get_prior(time_bucket, anchor_category, item_id)
        if deterministic:
            return float(alpha / (alpha + beta))
        theta = random.betavariate(alpha, beta)
        return float(theta)

    @classmethod
    def record_interaction(
        cls,
        time_bucket: str = "general",
        anchor_category: Any = "general",
        item_id: Optional[int] = None,
        converted: bool = False,
        weight: float = 1.0,
    ) -> None:
        """
        Bayesian posterior update:
        Converted (clicked / added to cart) -> alpha <- alpha + weight
        Not converted (presented but ignored / dismissed) -> beta <- beta + weight
        """
        key = cls._normalize_key(time_bucket, anchor_category, item_id)
        cls.get_prior(time_bucket, anchor_category, item_id)
        if converted:
            cls._priors[key][0] += weight
        else:
            cls._priors[key][1] += weight

    @classmethod
    def get_arm_stats(
        cls,
        time_bucket: str = "general",
        anchor_category: Any = "general",
        item_id: Optional[int] = None,
    ) -> dict[str, float]:
        alpha, beta = cls.get_prior(time_bucket, anchor_category, item_id)
        expected_ctr = alpha / (alpha + beta)
        variance = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1))
        return {
            "alpha": alpha,
            "beta": beta,
            "expected_ctr": round(expected_ctr, 4),
            "variance": round(variance, 6),
        }
