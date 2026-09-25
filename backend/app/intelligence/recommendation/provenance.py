"""
app/intelligence/recommendation/provenance.py
Product Relationship Provenance — v7 §22

When co_purchase or product_relationships asserts 'A pairs with B',
this module records WHERE that claim came from — different sources have
very different trust levels and must be auditable separately.

Source trust hierarchy:
  business_defined   -> near-certain, no revalidation needed
  observed_co_purchase -> only as good as its volume (§14 gate)
  model_inferred     -> lowest trust until evidence-backed over enough impressions
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

RelationshipSource = Literal["business_defined", "observed_co_purchase", "model_inferred"]

# Base trust weights per source type
_TRUST_WEIGHTS: dict[str, float] = {
    "business_defined": 1.0,
    "observed_co_purchase": 0.70,
    "model_inferred": 0.40,
    "popularity": 0.60,
    "semantic_fit": 0.55,
    "exploration": 0.30,
}


@dataclass
class TaggedCandidate:
    """
    A MenuItem candidate annotated with its generator source and provenance.
    Flows through the entire pipeline so every decision in the trace (§19)
    knows where each candidate came from.
    """
    item: object           # MenuItem
    source: str            # Generator name: 'co_purchase' | 'semantic_fit' | 'popularity' | 'exploration'
    provenance_type: RelationshipSource  # Trust classification
    source_confidence: float = 1.0  # Raw confidence from the source
    effective_confidence: float = 1.0  # After volume discounting (§14)

    def __post_init__(self) -> None:
        self.effective_confidence = self._compute_effective_confidence()

    def _compute_effective_confidence(self) -> float:
        base = _TRUST_WEIGHTS.get(self.source, 0.5)
        if self.provenance_type == "observed_co_purchase":
            # Volume-discount: source_confidence carries the volume ratio from DataQualityGate
            return base * max(0.1, self.source_confidence)
        return base


class RelationshipTrust:
    """
    Computes the effective trust weight for a product relationship assertion.
    Used by the retriever and the scoring pipeline.
    """

    @staticmethod
    def get_weight(source: str, volume_confidence: float = 1.0) -> float:
        """
        Returns a trust weight [0.1, 1.0] for a relationship from this source.
        A business-defined combo is near-certain (1.0).
        An observed co-purchase is only as good as its volume (multiplied by volume_confidence).
        A model-inferred relationship starts at 0.40 until evidence accumulates.
        """
        base = _TRUST_WEIGHTS.get(source, 0.50)
        if source == "observed_co_purchase":
            return max(0.10, base * volume_confidence)
        return base

    @staticmethod
    def classify_generator_source(generator_name: str) -> RelationshipSource:
        """
        Maps generator names to provenance types for trace labeling.
        """
        if generator_name == "co_purchase":
            return "observed_co_purchase"
        if generator_name in ("semantic_fit", "exploration"):
            return "model_inferred"
        # popularity and business rules are treated as observed/business evidence
        return "observed_co_purchase"
