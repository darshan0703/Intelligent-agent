"""
Module 9: Tiered Margin Multiplier (Phase 2 Margin Optimization)
Boosts high-margin fountain sodas scaled by customer spend.
Anchor < 100: 1.10x | Anchor 100-168: 1.20x | Anchor >= 169: 1.30x
Packaged water receives a 0.85x dampener.
"""
from typing import Dict, Any

HIGH_MARGIN_SODAS = {"coke", "coca cola", "fanta", "sprite", "thums up", "pepsi"}

def score_margin_multiplier(
    candidate: Dict[str, Any],
    anchor_price: float | None
) -> float:
    name = str(candidate.get("name", "")).lower()
    price = anchor_price or 100.0

    if "water" in name:
        return 0.85

    if any(s in name for s in HIGH_MARGIN_SODAS):
        if price < 100.0:
            return 1.10
        elif price < 169.0:
            return 1.20
        else:
            return 1.30

    return 1.0
