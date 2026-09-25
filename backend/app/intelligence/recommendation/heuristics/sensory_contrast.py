"""
app/intelligence/recommendation/heuristics/sensory_contrast.py
Sensory-Specific Satiety & Flavor Contrast Matrix (Neuro-Gastronomy Heuristic)
- Prevents palate fatigue: Avoids recommending identical flavor profiles to the anchor item.
- Applies flavor contrast:
  * Spicy / Fiery Anchor -> Aggressively boosts Sweet / Cold / Dairy / Creamy to soothe palate. Damps identical spice.
  * Heavy / Fried / Cheesy Anchor -> Aggressively boosts Carbonated / Acidic / Light Citrus to cut fat.
  * Sweet / Rich Anchor -> Boosts Savory / Warm Beverages.
"""
from __future__ import annotations
from typing import Any
from app.domain.catalog.entities import MenuItem


class SensoryContrastAnalyzer:
    @staticmethod
    def classify_flavor_profile(item_name: str, category: str, desc: str = "") -> set[str]:
        text = f"{item_name} {category} {desc}".lower()
        profiles = set()

        # Spicy / Fiery / Hot
        if any(w in text for w in ["spicy", "peri peri", "fiery", "hell", "chilli", "jalapeno", "masala"]):
            profiles.add("spicy")

        # Heavy / Fried / Cheesy
        if "burger" in category.lower() or "side" in category.lower() or any(w in text for w in ["cheese", "melt", "crispy", "fried", "patty"]):
            profiles.add("heavy_savory")

        # Sweet / Rich / Indulgent
        if "dessert" in category.lower() or any(w in text for w in ["sweet", "choco", "sugar", "caramel", "vanilla"]):
            profiles.add("sweet")

        # Cold / Dairy / Soothing
        if any(w in text for w in ["shake", "coffee", "float", "ice cream", "creamy", "latte", "dairy"]):
            profiles.add("cooling_dairy")

        # Carbonated / Acidic / Refreshing
        if "drink" in category.lower() and any(w in text for w in ["fizz", "soda", "carbonated", "lemon", "tea", "cola", "sprite", "fanta"]):
            profiles.add("carbonated_refreshing")

        return profiles

    @classmethod
    def evaluate_contrast_multiplier(
        cls,
        anchor_item_name: str,
        anchor_category: str,
        candidate_item: MenuItem,
    ) -> tuple[float, str]:
        """
        Calculates contrast score multiplier and explanation based on neuro-gastronomic contrast.
        Returns (multiplier: float, rationale: str).
        """
        anchor_profiles = cls.classify_flavor_profile(anchor_item_name, anchor_category)
        cand_cat = str(candidate_item.category.value if hasattr(candidate_item.category, "value") else candidate_item.category)
        cand_profiles = cls.classify_flavor_profile(candidate_item.name, cand_cat, candidate_item.short_description or "")

        multiplier = 1.0
        reasons = []

        # 1. Spicy Anchor -> Boost Cooling/Dairy/Sweet; Damp identical spicy
        if "spicy" in anchor_profiles:
            if "cooling_dairy" in cand_profiles or "sweet" in cand_profiles:
                multiplier += 0.45
                reasons.append("Sensory contrast: Cooling/sweet complement soothes spicy palate")
            if "spicy" in cand_profiles:
                multiplier -= 0.30
                reasons.append("Sensory fatigue penalty: Avoid duplicate heavy spice")

        # 2. Heavy / Fried / Cheesy Anchor -> Boost Carbonated / Acidic Refreshment
        if "heavy_savory" in anchor_profiles:
            if "carbonated_refreshing" in cand_profiles:
                multiplier += 0.40
                reasons.append("Sensory contrast: Carbonated fizz cuts rich savory fat")

        # 3. Sweet Anchor -> Boost Savory / Hot
        if "sweet" in anchor_profiles:
            if "heavy_savory" in cand_profiles or "carbonated_refreshing" in cand_profiles:
                multiplier += 0.35
                reasons.append("Sensory contrast: Savory/refreshing resets sweet palate")

        # 4. Anti-Redundancy Constraint (Neuro-gastronomic base ingredient clash)
        from app.intelligence.recommendation.constraints import AntiRedundancyConstraint
        if AntiRedundancyConstraint.is_redundant_side(candidate_item, anchor_item_name):
            multiplier *= 0.35
            reasons.append("Anti-redundancy: Avoid pairing identical base ingredient (e.g., potato burger with potato side)")

        final_multiplier = max(0.15, min(1.60, multiplier))
        rationale = "; ".join(reasons) if reasons else "Standard sensory alignment"
        return final_multiplier, rationale
