"""
app/intelligence/recommendation/job_config.py
Job Code Registry — v7 §12, §16

Every recommendation request carries a named job_code that declares:
- Which generators participate (with per-source quotas from generator_quotas table)
- Latency execution tier: LIGHT (Discovery pages) | FULL (Product/Cart) | NARROW (Substitute/Upgrade)
- MMR lambda (diversity weight): higher = more relevance-weighted; lower = more diverse
- LLM cognitive reasoner enabled: only FULL tier
- Fallback graph level order (§17)

This is the single source of truth for pipeline behavior per request type.
Changing a job's tier or generator set here propagates everywhere automatically.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

LatencyTier = Literal["LIGHT", "FULL", "NARROW"]


@dataclass(frozen=True)
class JobConfig:
    job_code: str
    latency_tier: LatencyTier
    generators: list[str]  # Ordered list of generator names that participate
    mmr_lambda: float      # MMR relevance weight (0.0=max diversity, 1.0=pure relevance)
    llm_enabled: bool      # Whether LLM cognitive synergy analysis runs
    top_k: int             # Final recommendation slots to fill
    description: str       # Human-readable description for debugging
    fallback_order: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # §17 fallback levels


# ── JOB REGISTRY ─────────────────────────────────────────────────────────────
# DISCOVERY: Home page and category browsing. Speed matters most.
# FULL generators available: ["co_purchase", "semantic_fit", "popularity", "exploration"]
# LIGHT tier skips LLM and reads bandit posteriors from cache.

JOB_REGISTRY: dict[str, JobConfig] = {
    "DISCOVERY": JobConfig(
        job_code="DISCOVERY",
        latency_tier="LIGHT",
        generators=["popularity", "semantic_fit"],
        mmr_lambda=0.75,   # More relevance-weighted; discovery shelf is meant to be browsable
        llm_enabled=False,  # Skip LLM for Home/Category pages — sub-50ms target
        top_k=6,
        description="Home page and category hub — speed-first, popularity + semantic fit only",
    ),
    "MEAL_COMPLETION": JobConfig(
        job_code="MEAL_COMPLETION",
        latency_tier="FULL",
        generators=["co_purchase", "semantic_fit", "popularity", "exploration"],
        mmr_lambda=0.60,   # Balanced — meal shelves need relevance AND diversity
        llm_enabled=True,
        top_k=4,
        description="Product detail modal — anchor-driven 3-slot complementary bundling",
    ),
    "CLOSURE": JobConfig(
        job_code="CLOSURE",
        latency_tier="FULL",
        generators=["co_purchase", "semantic_fit", "popularity", "exploration"],
        mmr_lambda=0.50,   # Strong diversity — cart shelf should never show two thick shakes
        llm_enabled=True,
        top_k=3,
        description="Cart/Checkout page — basket completion and impulse micro-additions",
    ),
    "SUBSTITUTE": JobConfig(
        job_code="SUBSTITUTE",
        latency_tier="NARROW",
        generators=["semantic_fit", "popularity"],
        mmr_lambda=0.80,   # High relevance — substitute must be clearly related to removed item
        llm_enabled=False,
        top_k=2,
        description="Winback recovery — substitute for removed item at lower price point",
        fallback_order=[2, 3, 4],  # No co_purchase fallback for substitute — narrow by design
    ),
    "UPGRADE": JobConfig(
        job_code="UPGRADE",
        latency_tier="NARROW",
        generators=[],  # UPGRADE uses meal_upgrade_rules table directly — no general generators
        mmr_lambda=1.0,
        llm_enabled=False,
        top_k=2,
        description="Meal builder upgrade — fries flavor swap, drink size upgrade",
        fallback_order=[3, 4],
    ),
    "PRODUCT_CROSSSELL": JobConfig(
        job_code="PRODUCT_CROSSSELL",
        latency_tier="FULL",
        generators=["co_purchase", "semantic_fit", "popularity", "exploration"],
        mmr_lambda=0.55,   # Strong diversity to guarantee 1 Drink + 1 Side + 1 Treat
        llm_enabled=True,
        top_k=3,
        description="Product detail page 'Pairs Best With' — strict 3-slot MMR diversity",
    ),
}


def get_job(job_code: str) -> JobConfig:
    """Returns the JobConfig for the given job_code. Raises KeyError if unknown."""
    if job_code not in JOB_REGISTRY:
        raise KeyError(f"Unknown job_code '{job_code}'. Valid codes: {list(JOB_REGISTRY.keys())}")
    return JOB_REGISTRY[job_code]


# ── GENERATOR QUOTAS IN-MEMORY CACHE ─────────────────────────────────────────
# Mirrors the generator_quotas table. Used by QuotaBoundedRetriever.
# Structure: {job_code: {generator: (max_candidates, min_candidates)}}

GENERATOR_QUOTAS: dict[str, dict[str, tuple[int, int]]] = {
    "DISCOVERY":         {"co_purchase": (4, 0), "semantic_fit": (6, 0), "popularity": (6, 2), "exploration": (3, 0)},
    "MEAL_COMPLETION":   {"co_purchase": (6, 0), "semantic_fit": (8, 0), "popularity": (4, 1), "exploration": (2, 0)},
    "CLOSURE":           {"co_purchase": (3, 0), "semantic_fit": (4, 0), "popularity": (6, 2), "exploration": (1, 0)},
    "SUBSTITUTE":        {"co_purchase": (0, 0), "semantic_fit": (3, 0), "popularity": (4, 1), "exploration": (0, 0)},
    "PRODUCT_CROSSSELL": {"co_purchase": (6, 0), "semantic_fit": (8, 0), "popularity": (4, 1), "exploration": (2, 0)},
    "UPGRADE":           {"co_purchase": (0, 0), "semantic_fit": (0, 0), "popularity": (0, 0), "exploration": (0, 0)},
}


# ── MMR LAMBDA PER JOB ──────────────────────────────────────────────────────
# Extracted for convenience; same values as JobConfig.mmr_lambda.
JOB_MMR_LAMBDA: dict[str, float] = {
    job_code: cfg.mmr_lambda
    for job_code, cfg in JOB_REGISTRY.items()
}
