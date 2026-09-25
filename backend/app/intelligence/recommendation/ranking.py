"""
app/intelligence/recommendation/ranking.py
Stage 3 & 4: Statistical & Cognitive Ranking Engine (v2.1)
Fuses:
1. Base Signals (Inventory urgency, Popularity priors, Session affinity, Co-occurrence)
2. Price Proximity & Consumer Price Anchoring (Damping > 1.5x anchor, budget boost)
3. Sensory Contrast & Palate Fatigue (Sensory-Specific Satiety)
4. Biological Contexting (Circadian Clock Cravings)
5. Goal Gradient Threshold (Cart Gamification / Reward Unlocking)
6. Session Learner Mindset (Adaptive Persona & Negative Fatigue)
7. Cognitive LLM Synergy (Grok Contextual Multipliers)
8. MMR Category Slot Diversity (1 Side + 1 Drink + 1 Dessert)
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import Candidate, SignalScore
from app.domain.session.entities import SessionState
from app.intelligence.recommendation.diversity import MMRDiversity
from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
from app.intelligence.recommendation.heuristics.goal_gradient import GoalGradientAnalyzer
from app.intelligence.recommendation.heuristics.sensory_contrast import SensoryContrastAnalyzer
from app.intelligence.recommendation.signals.crosssell_signal import CrossSellSignal
from app.intelligence.recommendation.signals.inventory_signal import InventorySignal
from app.intelligence.recommendation.signals.popularity_signal import PopularitySignal
from app.intelligence.recommendation.signals.session_signal import SessionSignal


class StatisticalRanker:
    def __init__(self):
        self.inventory_signal = InventorySignal(weight=0.20)
        self.popularity_signal = PopularitySignal(weight=0.25)
        self.session_signal = SessionSignal(weight=0.25)
        self.crosssell_signal = CrossSellSignal(weight=0.30)
        self.diversity = MMRDiversity()

    def score_candidates(
        self,
        candidates: list[MenuItem],
        session: SessionState,
        cart_item_ids: set[int],
        cross_sell_ids: set[int],
        anchor_item_name: str | None = None,
        anchor_category: str | None = None,
        anchor_price: Decimal | None = None,
        cart_total: Decimal | None = None,
        reward_threshold: Decimal | None = None,
        reward_name: str = "Free Delivery",
        cognitive_multipliers: dict[int, float] | None = None,
        category_dismissal_counts: dict[str, int] | None = None,
        customer_persona: str = "Standard_Explorer",
        circadian_hour: int | None = None,
    ) -> list[Candidate]:
        scored: list[Candidate] = []
        cog_mults = cognitive_multipliers or {}
        dismiss_counts = category_dismissal_counts or {}

        for item in candidates:
            # 1. Base Multi-Objective Signals
            inv_score = self.inventory_signal.score(item)
            pop_score = self.popularity_signal.score(item)
            sess_score = self.session_signal.score(item, session, cart_item_ids)
            cross_score = self.crosssell_signal.score(item, cross_sell_ids)

            scores = [inv_score, pop_score, sess_score, cross_score]
            base_score = (
                inv_score.raw_score * inv_score.weight
                + pop_score.raw_score * pop_score.weight
                + sess_score.raw_score * sess_score.weight
                + cross_score.raw_score * cross_score.weight
            )

            # 2. Price Proximity Constraint & Consumer Price Anchoring
            item_price = item.price.amount if hasattr(item.price, "amount") else Decimal(str(item.price))
            price_damping = 1.0
            price_bonus = 0.0

            if anchor_price is not None and anchor_price > Decimal("0"):
                ratio = float(item_price / anchor_price)
                cand_cat_raw = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
                is_drink_or_dessert = any(k in cand_cat_raw for k in ["drink", "beverage", "dessert"])

                # Requirement 2: Premium Anchor Elasticity
                # If anchor_price >= 169, completely bypass price proximity penalty for Drink or Dessert
                if anchor_price >= Decimal("169.00") and is_drink_or_dessert:
                    price_damping = 1.0
                elif ratio > 1.5:
                    price_damping = max(0.15, 1.0 - (ratio - 1.5) * 0.9)
                    scores.append(SignalScore(
                        signal_name="price_proximity_penalty",
                        raw_score=price_damping,
                        weight=0.20,
                        explanation=f"Price exceeds 1.5x anchor (ratio {ratio:.2f}x)",
                    ))

                if anchor_price <= Decimal("160.00") and item_price <= Decimal("100.00"):
                    price_bonus += 0.35
                    scores.append(SignalScore(
                        signal_name="budget_anchor_affinity",
                        raw_score=1.0,
                        weight=0.15,
                        explanation="Budget anchor boosts budget companion",
                    ))
                elif anchor_price >= Decimal("250.00") and item_price >= Decimal("120.00"):
                    price_bonus += 0.20

            # 3. Sensory Contrast & Palate Fatigue (Neuro-Gastronomy)
            sensory_mult = 1.0
            if anchor_item_name and anchor_category:
                sensory_mult, sensory_reason = SensoryContrastAnalyzer.evaluate_contrast_multiplier(
                    anchor_item_name=anchor_item_name,
                    anchor_category=anchor_category,
                    candidate_item=item,
                )
                if sensory_mult != 1.0:
                    scores.append(SignalScore(
                        signal_name="sensory_contrast",
                        raw_score=sensory_mult,
                        weight=0.20,
                        explanation=sensory_reason,
                    ))

            # 4. Biological Contexting (Circadian Clock Cravings)
            circadian_mult, circadian_reason = CircadianCravingAnalyzer.evaluate_circadian_multiplier(
                candidate_item=item,
                hour=circadian_hour,
            )
            if circadian_mult != 1.0:
                scores.append(SignalScore(
                    signal_name="circadian_craving",
                    raw_score=circadian_mult,
                    weight=0.15,
                    explanation=circadian_reason,
                ))

            # 5. Goal Gradient Threshold (Cart Gamification)
            goal_bonus = 0.0
            framing_hint = None
            if cart_total is not None and reward_threshold is not None:
                goal_bonus, framing_hint = GoalGradientAnalyzer.evaluate_goal_gradient(
                    cart_total=cart_total,
                    candidate_item=item,
                    reward_threshold=reward_threshold,
                    reward_name=reward_name,
                )
                if goal_bonus > 0.0:
                    scores.append(SignalScore(
                        signal_name="goal_gradient_boost",
                        raw_score=1.0,
                        weight=0.25,
                        explanation=framing_hint or "Goal gradient threshold fit",
                    ))

            # 6. Session Learning & Adaptive Persona Weighting
            cat_norm = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
            cat_dismissals = dismiss_counts.get(cat_norm, 0)
            fatigue_damping = max(0.35, 1.0 - (cat_dismissals * 0.25))

            persona_bonus = 0.0
            if "Budget" in customer_persona and item_price <= Decimal("100.00"):
                persona_bonus = 0.25
            elif "Indulgent" in customer_persona and (item_price >= Decimal("150.00") or getattr(item, "section", "") in ("Whoppers", "Premium Burgers")):
                persona_bonus = 0.25

            # 7. Cognitive LLM Synergy Multiplier
            cog_mult = cog_mults.get(item.id, 1.0)

            # 8. Commercial Margin Multiplier
            margin_mult = 1.0
            item_name_lower = (item.name or "").lower()
            item_desc_lower = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}".lower()
            item_text = f"{item_name_lower} {item_desc_lower}"
            if any(w in item_text for w in ["packaged drinking water", "bottled water", "mineral water", "kinley", "aquafina"]) or (
                "water" in item_name_lower and not any(f in item_name_lower for f in ["watermelon", "watering"])
            ):
                margin_mult = 0.85
            elif any(s in item_text for s in ["coca-cola", "coke", "sprite", "fizz", "fanta", "thums up", "pepsi", "mirinda", "soda"]):
                margin_mult = 1.2

            # ── Final Statistical Fusion ───────────────────────────────────────
            combined_base = base_score + price_bonus + goal_bonus + persona_bonus
            final_score = (combined_base * price_damping * sensory_mult * circadian_mult * fatigue_damping * margin_mult) * cog_mult

            # Requirement 3: Universal Side Commercial Boost
            if any(w in item_name_lower for w in ["nugget", "nuggets", "fries", "french fries"]):
                final_score *= 1.25

            # Requirement 5: Thermal Contrast (The Hot/Hot Ban)
            if circadian_hour is not None and circadian_hour < 11:
                is_morning = True
            else:
                from datetime import datetime
                is_morning = datetime.now().hour < 11

            if not is_morning and anchor_category == "burger":
                from app.intelligence.recommendation.scoring import get_item_temperature
                if get_item_temperature(item) >= 4 and any(k in item_text for k in ["coffee", "latte", "cappuccino", "tea"]):
                    final_score *= 0.50

            cand = Candidate(item=item, scores=scores)
            cand._cached_total_score = final_score  # type: ignore
            cand._framing_hint = framing_hint  # type: ignore
            scored.append(cand)

        scored.sort(key=lambda c: getattr(c, "_cached_total_score", c.weighted_score), reverse=True)
        return scored

    @staticmethod
    def is_heavy_dairy_beverage(item: Any) -> bool:
        """
        Dual-Role Saturation:
        Identifies heavy, high-dairy beverages:
        category == 'drink' AND (dairy_content >= 0.7 or name containing 'Shake', 'Frappe', 'Float').
        When present in cart, fulfills BOTH Drink and Dessert pillars.
        """
        if not item:
            return False

        if isinstance(item, dict):
            name_str = str(item.get("name") or item.get("item_name") or "").lower()
            desc_str = str(item.get("short_description") or item.get("description") or "").lower()
            cat_str = str(item.get("category") or "").lower()
            item_id = item.get("id") or item.get("item_id")
        else:
            name_str = str(getattr(item, "name", "") or "").lower()
            desc_str = str(getattr(item, "short_description", "") or "").lower()
            cat_str = str(item.category.value if hasattr(item.category, "value") else getattr(item, "category", "")).lower()
            item_id = getattr(item, "id", None)

        if "drink" not in cat_str and "beverage" not in cat_str:
            return False

        text = f"{name_str} {desc_str}"
        if any(w in text for w in ["shake", "frappe", "float"]):
            return True

        from app.intelligence.recommendation.data_quality_gate import CulinaryTagger
        if item_id:
            prof = CulinaryTagger.extract_profile(item_id, name_str, desc_str)
            if prof.dairy_content >= 0.7:
                return True
        return False

    @staticmethod
    def classify_beverage_subrole(item: MenuItem) -> str:
        """
        Classifies beverages into:
        - 'sweet_indulgence': heavy milk, thick shake, frappe, float, ice-cream dessert drinks.
        - 'carbonated_hydration': carbonated/acidic hydration (soda, cola, fizz, sprite, juice, water).
        """
        name = (item.name or "").lower()
        desc = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}".lower()
        text = f"{name} {desc}"

        if any(w in text for w in ["shake", "frappe", "float", "ice cream", "softie", "cream", "milk", "latte", "cappuccino", "hot chocolate", "mousse"]):
            return "sweet_indulgence"
        if any(w in text for w in ["fizz", "soda", "cola", "coke", "sprite", "fanta", "mirinda", "thums up", "pepsi", "lemonade", "tea", "water", "americano", "juice", "citrus"]):
            return "carbonated_hydration"
        return "carbonated_hydration"

    @staticmethod
    def classify_dessert_subrole(item: MenuItem) -> str:
        """
        Classifies desserts into:
        - 'cold_dairy': softie, sundae, shake, ice cream, mousse, float, cold, cone.
        - 'hot_baked': lava cup, waffle, pie, baked, pastry, warm brownie/cake, cookie, muffin, tart.
        """
        name = (item.name or "").lower()
        desc = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}".lower()
        text = f"{name} {desc}"

        # 1. Check strong name signals for hot/baked desserts
        if any(w in name for w in ["lava", "waffle", "pie", "cake", "brownie", "pastry", "cookie", "muffin", "tart"]):
            return "hot_baked"
        # 2. Check cold dairy signals (sundaes, softies, ice creams, shakes)
        if any(w in text for w in ["softie", "sundae", "shake", "ice cream", "mousse", "float", "cone", "mcflurry"]):
            return "cold_dairy"
        # 3. Check general baked/warm dessert signals in text
        if any(w in text for w in ["lava", "waffle", "pie", "baked", "cake", "brownie", "pastry", "cookie", "muffin", "tart"]):
            return "hot_baked"
        return "cold_dairy"

    def apply_slot_diversity(
        self,
        scored_candidates: list[Candidate],
        target_categories: list[str],
        suppressed_categories: set[str],
        limit: int = 4,
    ) -> list[MenuItem]:
        cat_buckets: dict[str, list[Candidate]] = {
            "burger": [],
            "drink": [],
            "side": [],
            "dessert": [],
        }

        for cand in scored_candidates:
            cat_raw = str(cand.item.category.value if hasattr(cand.item.category, "value") else cand.item.category).lower()
            cat_norm = "burger" if "burger" in cat_raw else ("drink" if "drink" in cat_raw else ("side" if "side" in cat_raw else ("dessert" if "dessert" in cat_raw else "side")))
            cat_buckets[cat_norm].append(cand)

        for c in cat_buckets:
            cat_buckets[c].sort(key=lambda x: getattr(x, "_cached_total_score", x.weighted_score), reverse=True)

        recommendations: list[MenuItem] = []
        chosen_ids: set[int] = set()
        chosen_drink_subroles: set[str] = set()
        chosen_dessert_subroles: list[str] = []
        assigned_base_ingredients: set[str] = set()
        assigned_dominant_flavors: set[str] = set()

        def _is_beverage_acceptable(cand_item: MenuItem, cat_key: str) -> bool:
            cand_cat_raw = str(cand_item.category.value if hasattr(cand_item.category, "value") else cand_item.category).lower()
            if cat_key == "drink" or "drink" in cand_cat_raw or "beverage" in cand_cat_raw:
                subrole = self.classify_beverage_subrole(cand_item)
                # Enforce that candidate slots balance between hydration and indulgence:
                # Never show two heavy milk/ice-cream drinks together.
                if subrole == "sweet_indulgence" and "sweet_indulgence" in chosen_drink_subroles:
                    return False
            return True

        def _is_dessert_acceptable(cand_item: MenuItem, cat_key: str) -> bool:
            cand_cat_raw = str(cand_item.category.value if hasattr(cand_item.category, "value") else cand_item.category).lower()
            if cat_key == "dessert" or "dessert" in cand_cat_raw:
                subrole = self.classify_dessert_subrole(cand_item)
                # If we already have 2 cold_dairy desserts, do not accept a 3rd cold_dairy if a hot_baked alternative exists
                if subrole == "cold_dairy":
                    cold_count = sum(1 for r in chosen_dessert_subroles if r == "cold_dairy")
                    if cold_count >= 2:
                        has_hot_baked = any(
                            cand.item.id not in chosen_ids and self.classify_dessert_subrole(cand.item) == "hot_baked"
                            for cand in cat_buckets.get("dessert", [])
                        )
                        if has_hot_baked:
                            return False
            return True

        def _is_intra_tray_diverse(cand_item: MenuItem) -> bool:
            """
            TASK 2: INTRA-TRAY DIVERSITY
            Prevents 'Vanilla + Vanilla' or identical base ingredients within the same tray.
            """
            from app.intelligence.recommendation.constraints import AntiRedundancyConstraint
            from app.intelligence.recommendation.data_quality_gate import CulinaryTagger

            base_ing = AntiRedundancyConstraint.extract_base_ingredient(cand_item)
            if base_ing and base_ing in assigned_base_ingredients:
                return False

            flavor = CulinaryTagger.get_dominant_flavor(cand_item)
            if flavor and flavor in assigned_dominant_flavors:
                return False

            return True

        def _record_item_chosen(cand_item: MenuItem, cat_key: str) -> None:
            cand_cat_raw = str(cand_item.category.value if hasattr(cand_item.category, "value") else cand_item.category).lower()
            if cat_key == "drink" or "drink" in cand_cat_raw or "beverage" in cand_cat_raw:
                subrole = self.classify_beverage_subrole(cand_item)
                chosen_drink_subroles.add(subrole)
            if cat_key == "dessert" or "dessert" in cand_cat_raw:
                subrole = self.classify_dessert_subrole(cand_item)
                chosen_dessert_subroles.append(subrole)

            from app.intelligence.recommendation.constraints import AntiRedundancyConstraint
            from app.intelligence.recommendation.data_quality_gate import CulinaryTagger
            base_ing = AntiRedundancyConstraint.extract_base_ingredient(cand_item)
            if base_ing:
                assigned_base_ingredients.add(base_ing)
            flavor = CulinaryTagger.get_dominant_flavor(cand_item)
            if flavor:
                assigned_dominant_flavors.add(flavor)

        # PASS 1: Slot Diversity across target gap categories with intra-tray diversity
        for cat in target_categories:
            if len(recommendations) >= limit:
                break
            for cand in cat_buckets.get(cat, []):
                if (
                    cand.item.id not in chosen_ids
                    and _is_beverage_acceptable(cand.item, cat)
                    and _is_dessert_acceptable(cand.item, cat)
                    and _is_intra_tray_diverse(cand.item)
                ):
                    cand.item._framing_hint = getattr(cand, "_framing_hint", None)  # type: ignore
                    recommendations.append(cand.item)
                    chosen_ids.add(cand.item.id)
                    _record_item_chosen(cand.item, cat)
                    break

        # PASS 2: Secondary choices from target categories with intra-tray diversity
        if len(recommendations) < limit:
            for cat in target_categories:
                if len(recommendations) >= limit:
                    break
                for cand in cat_buckets.get(cat, []):
                    if (
                        cand.item.id not in chosen_ids
                        and _is_beverage_acceptable(cand.item, cat)
                        and _is_dessert_acceptable(cand.item, cat)
                        and _is_intra_tray_diverse(cand.item)
                    ):
                        cand.item._framing_hint = getattr(cand, "_framing_hint", None)  # type: ignore
                        recommendations.append(cand.item)
                        chosen_ids.add(cand.item.id)
                        _record_item_chosen(cand.item, cat)
                        break

        # PASS 3: Unsuppressed fallback with intra-tray diversity
        if len(recommendations) < limit:
            unsuppressed = [c for c in ["dessert", "side", "burger", "drink"] if c not in suppressed_categories]
            for cat in unsuppressed:
                if len(recommendations) >= limit:
                    break
                for cand in cat_buckets.get(cat, []):
                    if (
                        cand.item.id not in chosen_ids
                        and _is_beverage_acceptable(cand.item, cat)
                        and _is_dessert_acceptable(cand.item, cat)
                        and _is_intra_tray_diverse(cand.item)
                    ):
                        cand.item._framing_hint = getattr(cand, "_framing_hint", None)  # type: ignore
                        recommendations.append(cand.item)
                        chosen_ids.add(cand.item.id)
                        _record_item_chosen(cand.item, cat)
                        break

        # PASS 4: Relax intra-tray diversity only if still under limit to prevent blank slots
        if len(recommendations) < limit:
            for cat in ["side", "drink", "dessert", "burger"]:
                if len(recommendations) >= limit:
                    break
                for cand in cat_buckets.get(cat, []):
                    if cand.item.id not in chosen_ids:
                        cand.item._framing_hint = getattr(cand, "_framing_hint", None)  # type: ignore
                        recommendations.append(cand.item)
                        chosen_ids.add(cand.item.id)
                        _record_item_chosen(cand.item, cat)
                        if len(recommendations) >= limit:
                            break

        # Invariant Guarantee: If shelf dedicates multiple slots to desserts and has >= 3 desserts,
        # it MUST NOT fill all 3 slots with cold_dairy; force at least one slot to be hot_baked if available.
        dessert_indices = [
            i for i, it in enumerate(recommendations)
            if "dessert" in str(it.category.value if hasattr(it.category, "value") else it.category).lower()
        ]
        if len(dessert_indices) >= 3:
            all_cold = all(
                self.classify_dessert_subrole(recommendations[i]) == "cold_dairy"
                for i in dessert_indices
            )
            if all_cold:
                hot_baked_cand = next(
                    (cand for cand in cat_buckets.get("dessert", [])
                     if cand.item.id not in chosen_ids and self.classify_dessert_subrole(cand.item) == "hot_baked"),
                    None
                )
                if hot_baked_cand:
                    replace_idx = dessert_indices[-1]
                    recommendations[replace_idx] = hot_baked_cand.item
                    chosen_ids.add(hot_baked_cand.item.id)

        return recommendations[:limit]
