"""
app/intelligence/recommendation/diversity.py
Sub-Role-Aware MMR Diversity Re-ranking — v7 §13

v6 used coarse category+food_type similarity, which still allowed five near-duplicate
items (e.g., five thick shakes, all high-scoring) to appear in the top-K.

v7 fix: similarity is computed on sub_role + attribute vector, so two items with
the same sub_role (e.g., both are 'thick_shake') have similarity=0.9 and the MMR
penalty forces the second one out of the selection set.

lambda (λ) is job-specific from JOB_MMR_LAMBDA (job_config.py):
  CLOSURE (cart): λ=0.50 — strong diversity, the 3-slot shelf should almost never
                            show two thick_shake items in the same request.
  DISCOVERY (home/cat): λ=0.75 — more relevance-weighted, browsable shelf.
  MEAL_COMPLETION: λ=0.60 — balanced.

MMR formula:
  selected = []
  while len(selected) < K:
      next = argmax_c [ λ · relevance(c) − (1−λ) · max_similarity(c, selected) ]
      selected.append(next)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import Candidate


# ── DECLARATIVE SUB-ROLE REGISTRY & HOST GATING CONFIG ────────────────────────
# Defines granular sub-roles and declarative business constraints (e.g., condiment host gating).
# Adding a new sub-role requires a config row here, never an ad-hoc code if-statement.

@dataclass
class SubRoleDefinition:
    sub_role: str
    category: str
    keywords: list[str] = field(default_factory=list)
    requires_host: bool = False
    allowed_hosts: list[str] = field(default_factory=list)
    is_condiment: bool = False


SUB_ROLE_REGISTRY: dict[str, SubRoleDefinition] = {
    # Drinks
    "thick_shake": SubRoleDefinition("thick_shake", "drink", ["shake", "thick shake"]),
    "frozen_coffee": SubRoleDefinition("frozen_coffee", "drink", ["frappe", "frappuccino"]),
    "hot_coffee": SubRoleDefinition("hot_coffee", "drink", ["espresso", "americano", "latte", "cappuccino", "mocha"]),
    "cold_coffee": SubRoleDefinition("cold_coffee", "drink", ["cold coffee", "iced latte", "iced americano"]),
    "soda_float": SubRoleDefinition("soda_float", "drink", ["float"]),
    "specialty_fizz": SubRoleDefinition("specialty_fizz", "drink", ["fizz", "tropical", "masala fizz"]),
    "carbonated_soda": SubRoleDefinition("carbonated_soda", "drink", ["coke", "coca cola", "sprite", "fanta", "thums up", "pepsi"]),
    "hot_chocolate": SubRoleDefinition("hot_chocolate", "drink", ["hot chocolate"]),
    # Sides
    "fries": SubRoleDefinition("fries", "side", ["fries", "peri peri fries", "saucy fries"]),
    "nuggets": SubRoleDefinition("nuggets", "side", ["nugget"]),
    "wings": SubRoleDefinition("wings", "side", ["wing"]),
    "hashbrown": SubRoleDefinition("hashbrown", "side", ["hashbrown"]),
    "strips": SubRoleDefinition("strips", "side", ["strip", "veggie strip"]),
    "boneless_chicken": SubRoleDefinition("boneless_chicken", "side", ["boneless"]),
    # Condiments (Dips & Sauces) - Data-driven host requirement:
    "dip": SubRoleDefinition(
        sub_role="dip",
        category="side",
        keywords=["dip", "sauce", "chilli sauce", "oregano", "hell dip", "mayo"],
        requires_host=True,
        allowed_hosts=["fries", "nuggets", "wings", "hashbrown", "strips", "boneless_chicken"],
        is_condiment=True,
    ),
    # Desserts
    "soft_serve": SubRoleDefinition("soft_serve", "dessert", ["softie", "soft serve"]),
    "sundae": SubRoleDefinition("sundae", "dessert", ["sundae"]),
    "warm_dessert": SubRoleDefinition("warm_dessert", "dessert", ["lava", "molten"]),
    "chilled_dessert": SubRoleDefinition("chilled_dessert", "dessert", ["mousse"]),
    # Burgers / Mains
    "whopper": SubRoleDefinition("whopper", "burger", ["whopper"]),
    "paneer_burger": SubRoleDefinition("paneer_burger", "burger", ["paneer royale", "paneer"]),
    "peri_peri_burger": SubRoleDefinition("peri_peri_burger", "burger", ["peri peri"]),
    "crispy_burger": SubRoleDefinition("crispy_burger", "burger", ["crispy veg", "crispy chicken", "bk veggie", "bk chicken"]),
    "taco": SubRoleDefinition("taco", "burger", ["taco"]),
    "wrap": SubRoleDefinition("wrap", "burger", ["wrap"]),
    "makhani_burger": SubRoleDefinition("makhani_burger", "burger", ["makhani"]),
    "puff": SubRoleDefinition("puff", "burger", ["pizza puff"]),
}


def get_sub_role(item: MenuItem | str) -> str:
    """
    Returns the granular sub_role for an item based on its name or metadata.
    """
    name_lower = (item.name if hasattr(item, "name") else str(item)).lower()
    for sub_role, defn in SUB_ROLE_REGISTRY.items():
        if any(kw in name_lower for kw in defn.keywords):
            return sub_role
    if hasattr(item, "category"):
        cat = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
        return f"{cat}_general"
    return "general"


def is_condiment_gated(item: MenuItem, context_items: list[Any]) -> bool:
    """
    Evaluates whether an item is a condiment requiring a host food item.
    Returns True if the item is GATED (ineligible/blocked because no valid host is present).
    Returns False if the item is NOT gated (either does not require a host, or a valid host is present).
    """
    sub_role = get_sub_role(item)
    defn = SUB_ROLE_REGISTRY.get(sub_role)
    if not defn or not defn.requires_host:
        return False  # Not a condiment, eligible without host

    # Check for presence of an allowed host in context
    for other in context_items:
        if other is None:
            continue
        if isinstance(other, dict):
            o_name = other.get("name") or other.get("item_name", "")
        else:
            o_name = getattr(other, "name", getattr(other, "item_name", ""))
        o_sub = get_sub_role(o_name)
        if o_sub in defn.allowed_hosts:
            return False  # Host present -> unlocked!

    return True  # No host present -> gated!


def compute_similarity(a: MenuItem, b: MenuItem) -> float:
    """
    Computes similarity between two items for MMR diversity penalty.
    Uses sub_role + category as the attribute space.

    Returns [0.0, 1.0] where 1.0 = extremely similar (near-duplicate in recommendation slot).
    """
    sub_role_a = get_sub_role(a)
    sub_role_b = get_sub_role(b)

    if sub_role_a == sub_role_b:
        return 0.90  # Same sub_role = very likely slot duplicates

    cat_a = str(a.category.value if hasattr(a.category, "value") else a.category).lower()
    cat_b = str(b.category.value if hasattr(b.category, "value") else b.category).lower()
    if cat_a == cat_b:
        return 0.50  # Same category, different sub_role = moderate similarity

    return 0.10  # Different category = very low similarity, good diversity


class MMRDiversity:
    """
    Maximal Marginal Relevance re-ranking with sub_role-aware similarity.

    Formula: next = argmax_c [ λ · relevance(c) − (1−λ) · max_similarity(c, selected) ]

    λ is tuned per job_code:
      CLOSURE (cart/checkout): 0.50 — aggressive diversity to guarantee role variety
      MEAL_COMPLETION: 0.60 — balanced
      DISCOVERY (home/category): 0.75 — relevance-first, browsable shelf
    """

    def rerank(
        self,
        candidates: list[Candidate],
        top_k: int = 8,
        lambda_param: float = 0.70,
        job_code: str = "",
    ) -> list[Candidate]:
        """
        Re-ranks candidates using MMR.
        If job_code provided, looks up the job-specific λ from JOB_MMR_LAMBDA.
        """
        # Import here to avoid circular at module load time
        from app.intelligence.recommendation.job_config import JOB_MMR_LAMBDA
        if job_code and job_code in JOB_MMR_LAMBDA:
            lambda_param = JOB_MMR_LAMBDA[job_code]

        if not candidates or len(candidates) <= top_k:
            return sorted(candidates, key=lambda c: c.weighted_score, reverse=True)

        selected: list[Candidate] = []
        remaining = list(candidates)
        remaining.sort(key=lambda c: c.weighted_score, reverse=True)

        # Always select the highest-relevance candidate first
        selected.append(remaining.pop(0))

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_mmr = -999.0

            for i, cand in enumerate(remaining):
                relevance = cand.weighted_score
                # Max similarity to any already-selected item (sub_role-aware)
                max_sim = max(
                    compute_similarity(cand.item, s.item)
                    for s in selected
                )
                mmr_score = lambda_param * relevance - (1.0 - lambda_param) * max_sim
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected
