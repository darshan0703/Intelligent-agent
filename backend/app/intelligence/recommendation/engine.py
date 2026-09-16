"""
app/intelligence/recommendation/engine.py
Multi-objective recommendation engine with weighted signal fusion, MMR diversity, and tiering.
"""
from __future__ import annotations
from datetime import datetime
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import Candidate, RecommendationSet
from app.domain.session.entities import SessionState
from app.intelligence.recommendation.constraints import ConstraintFilter
from app.intelligence.recommendation.diversity import MMRDiversity
from app.intelligence.recommendation.signals.crosssell_signal import CrossSellSignal
from app.intelligence.recommendation.signals.inventory_signal import InventorySignal
from app.intelligence.recommendation.signals.popularity_signal import PopularitySignal
from app.intelligence.recommendation.signals.session_signal import SessionSignal
from app.ports.catalog_port import CatalogRepository
from app.ports.recommendation_port import RecommendationEngine as RecommendationEnginePort


class HybridRecommendationEngine(RecommendationEnginePort):
    def __init__(self, catalog: CatalogRepository):
        self.catalog = catalog
        self.inventory_signal = InventorySignal(weight=0.25)
        self.popularity_signal = PopularitySignal(weight=0.30)
        self.session_signal = SessionSignal(weight=0.25)
        self.crosssell_signal = CrossSellSignal(weight=0.20)
        self.constraint_filter = ConstraintFilter()
        self.diversity = MMRDiversity()

    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None = None,
        food_type: str | None = None,
        branch_id: int = 1,
    ) -> RecommendationSet:
        if category:
            raw_candidates = await self.catalog.get_by_category(category, branch_id)
        else:
            raw_candidates = await self.catalog.get_all_available(branch_id)

        valid_items = self.constraint_filter.filter_candidates(raw_candidates, session)
        cart_item_ids: set[int] = set()

        cross_sell_ids: set[int] = set()
        if session.last_item_id:
            pairings = await self.catalog.get_cross_sells(session.last_item_id, limit=4)
            cross_sell_ids = {p.id for p in pairings}

        scored_candidates: list[Candidate] = []
        for item in valid_items:
            scores = [
                self.inventory_signal.score(item),
                self.popularity_signal.score(item),
                self.session_signal.score(item, session, cart_item_ids),
                self.crosssell_signal.score(item, cross_sell_ids),
            ]
            scored_candidates.append(Candidate(item=item, scores=scores))

        ranked = self.diversity.rerank(scored_candidates, top_k=8)

        priority = ranked[:2]
        remaining = ranked[2:]
        premium = sorted(remaining, key=lambda c: c.item.price.amount, reverse=True)[:2]
        premium_ids = {p.item.id for p in premium}
        additional = [c for c in remaining if c.item.id not in premium_ids][:4]

        return RecommendationSet(
            session_id=session.session_id,
            context=f"category:{category}" if category else "general",
            priority=priority,
            premium=premium,
            additional=additional,
            generated_at=datetime.utcnow(),
            signals_used=["inventory_pressure", "popularity", "session_affinity", "cross_sell"],
        )

    async def get_cart_recommendations(
        self,
        session: SessionState,
        cart_lines: list,
        branch_id: int = 1,
        limit: int = 4,
    ) -> list[MenuItem]:
        """
        Human-Centric Pre-Checkout Recommendations:
        - Detects active dining pillars (Burger/Main, Drink, Side, Dessert) in the cart.
        - Calculates dining gaps from a human dining perspective (e.g., drinks require food/sides, NEVER more drinks).
        - Enforces strict Category Slot Diversity: each slot in the recommendation carousel
          comes from a distinct complementary category (e.g. 1 Drink + 1 Side + 1 Dessert).
        - Prevents mono-category repetition.
        """
        cart_item_ids = {getattr(l, "item_id", None) for l in cart_lines if getattr(l, "item_id", None) is not None}
        
        has_burger = False
        has_drink = False
        has_side = False
        has_dessert = False

        for l in cart_lines:
            cat = str(getattr(l, "category", "")).lower()
            l_type = getattr(l, "line_type", "")
            if "burger" in cat or l_type == "meal":
                has_burger = True
            if "drink" in cat or l_type == "meal":
                has_drink = True
            if "side" in cat or l_type == "meal":
                has_side = True
            if "dessert" in cat:
                has_dessert = True

        # Determine human-centric complementary category gaps and strictly suppressed categories
        suppressed_categories = set()
        if has_drink and not has_burger and not has_side:
            # Customer has only drinks: they need solid food or savory snacks, NEVER another drink!
            target_categories = ["side", "burger", "dessert"]
            suppressed_categories.add("drink")
        elif has_burger and not has_drink and not has_side:
            # Customer has a burger: classic pairing is a beverage and crispy fries
            target_categories = ["drink", "side", "dessert"]
            suppressed_categories.add("burger")
        elif has_side and not has_burger and not has_drink:
            # Customer has crispy/salty fries: needs beverage to quench thirst, or a burger for meal
            target_categories = ["drink", "burger", "dessert"]
            suppressed_categories.add("side")
        elif has_burger and has_drink and not has_side:
            target_categories = ["side", "dessert"]
            suppressed_categories.add("burger")
            suppressed_categories.add("drink")
        elif has_burger and has_side and not has_drink:
            target_categories = ["drink", "dessert"]
            suppressed_categories.add("burger")
            suppressed_categories.add("side")
        elif has_side and has_drink and not has_burger:
            target_categories = ["burger", "dessert"]
            suppressed_categories.add("side")
            suppressed_categories.add("drink")
        elif has_burger and has_side and has_drink:
            # Full meal combo: only sweet finish / dessert makes sense
            target_categories = ["dessert"]
            suppressed_categories.add("burger")
            suppressed_categories.add("side")
            suppressed_categories.add("drink")
        else:
            # Empty or browsing cart: provide balanced culinary spread across all 4 pillars
            target_categories = ["side", "drink", "dessert", "burger"]

        # Gather curated cross-sells from items currently in cart
        cross_sell_ids = set()
        for cid in cart_item_ids:
            try:
                pairs = await self.catalog.get_cross_sells(cid, limit=4)
                for p in pairs:
                    cross_sell_ids.add(p.id)
            except Exception:
                pass

        # Fetch available items and filter constraints
        raw_candidates = await self.catalog.get_all_available(branch_id)
        valid_items = self.constraint_filter.filter_candidates(raw_candidates, session)
        valid_items = [i for i in valid_items if i.id not in cart_item_ids]

        # Score candidates and partition by normalized category
        scored_by_cat: dict[str, list[tuple[float, MenuItem]]] = {
            "burger": [],
            "drink": [],
            "side": [],
            "dessert": [],
        }

        for item in valid_items:
            cat_raw = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
            cat_norm = "burger" if "burger" in cat_raw else ("drink" if "drink" in cat_raw else ("side" if "side" in cat_raw else ("dessert" if "dessert" in cat_raw else "side")))
            
            # Base signal scores
            inv_score = self.inventory_signal.score(item).raw_score
            pop_score = self.popularity_signal.score(item).raw_score
            
            # Contextual bonuses
            cross_bonus = 0.40 if item.id in cross_sell_ids else 0.0
            
            # Customer preference alignment
            pref_bonus = 0.0
            if session.food_preference:
                item_veg = "veg" in str(item.food_type).lower() if item.food_type else False
                pref_veg = session.food_preference.lower() == "veg"
                if item_veg == pref_veg:
                    pref_bonus = 0.25
                elif pref_veg and not item_veg:
                    # Strongly penalize non-veg if customer wants veg
                    pref_bonus = -1.00

            total_score = (inv_score * 0.20) + (pop_score * 0.25) + cross_bonus + pref_bonus
            scored_by_cat[cat_norm].append((total_score, item))

        # Sort each category bucket by score descending
        for cat_norm in scored_by_cat:
            scored_by_cat[cat_norm].sort(key=lambda x: x[0], reverse=True)

        recommendations: list[MenuItem] = []
        chosen_ids: set[int] = set()

        # PASS 1: Category Slot Diversity (Pick the #1 highest scoring item for each target gap)
        for cat in target_categories:
            if len(recommendations) >= limit:
                break
            for score, item in scored_by_cat.get(cat, []):
                if item.id not in chosen_ids:
                    recommendations.append(item)
                    chosen_ids.add(item.id)
                    break

        # PASS 2: If remaining slots, pick additional distinct items from target categories (e.g. 2nd side or 2nd dessert)
        if len(recommendations) < limit:
            for cat in target_categories:
                if len(recommendations) >= limit:
                    break
                for score, item in scored_by_cat.get(cat, []):
                    if item.id not in chosen_ids:
                        recommendations.append(item)
                        chosen_ids.add(item.id)
                        break

        # PASS 3: Only if target categories are exhausted, pick from unsuppressed categories
        if len(recommendations) < limit:
            unsuppressed = [c for c in ["dessert", "side", "burger", "drink"] if c not in suppressed_categories]
            for cat in unsuppressed:
                if len(recommendations) >= limit:
                    break
                for score, item in scored_by_cat.get(cat, []):
                    if item.id not in chosen_ids:
                        recommendations.append(item)
                        chosen_ids.add(item.id)
                        break

        return recommendations[:limit]

