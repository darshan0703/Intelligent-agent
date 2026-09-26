"""
engine.py
Clean RecommendationEngine implementation using pipeline_runner and modules.
Zero legacy monolith dependencies.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from app.domain.catalog.entities import MenuItem
from app.domain.session.entities import SessionState
from app.domain.recommendation.entities import Candidate, RecommendationSet, SignalScore
from app.ports.catalog_port import CatalogRepository
from app.intelligence.recommendation.constraints import ConstraintFilter
from app.intelligence.recommendation.pipeline_runner import run_recommendation_pipeline

ACTION_WEIGHT = 1.0


class HybridRecommendationEngine:
    """
    Lightweight engine adapter implementing RecommendationEngine protocol.
    Delegates all candidate scoring, filtering, and mutual exclusion to pipeline_runner.py.
    """
    def __init__(self, catalog: CatalogRepository) -> None:
        self.catalog = catalog
        self.constraint_filter = ConstraintFilter()

    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None = None,
        food_type: str | None = None,
        branch_id: int = 1,
    ) -> RecommendationSet:
        if category:
            items = await self.catalog.get_by_category(category, branch_id)
        else:
            items = await self.catalog.get_all_available(branch_id)

        items_dict = []
        for i in items:
            p_val = float(i.price.amount if hasattr(i.price, "amount") else i.price)
            items_dict.append({
                "id": i.id,
                "name": i.name,
                "price": p_val,
                "category": str(i.category.value if hasattr(i.category, "value") else i.category).lower(),
                "foodType": str(i.food_type.value if hasattr(i.food_type, "value") else i.food_type).lower() if i.food_type else "",
                "_raw_item": i,
            })

        pref = food_type or session.food_preference
        res = run_recommendation_pipeline(items_dict, preference=pref)

        def to_candidates(dicts: list[dict]) -> list[Candidate]:
            cands = []
            for d in dicts:
                raw = d.get("_raw_item")
                if raw:
                    cands.append(Candidate(
                        item=raw,
                        scores=[SignalScore(signal_name="modular_pipeline", raw_score=d.get("computed_score", 1.0), weight=1.0, explanation="Scored via pipeline runner")],
                    ))
            return cands

        return RecommendationSet(
            session_id=session.session_id,
            context=f"category:{category}" if category else "general",
            priority=to_candidates(res["priority"]),
            premium=to_candidates(res["premium"]),
            additional=to_candidates(res["additional"]),
            generated_at=datetime.now(timezone.utc),
            signals_used=["m01_to_m13_modular_pipeline"],
        )

    async def get_contextual_recommendations(
        self,
        session: SessionState,
        payload: dict,
        branch_id: int = 1,
        limit: int = 4,
    ) -> list[MenuItem]:
        all_items = await self.catalog.get_all_available(branch_id)
        items_dict = []
        for i in all_items:
            p_val = float(i.price.amount if hasattr(i.price, "amount") else i.price)
            items_dict.append({
                "id": i.id,
                "name": i.name,
                "price": p_val,
                "category": str(i.category.value if hasattr(i.category, "value") else i.category).lower(),
                "foodType": str(i.food_type.value if hasattr(i.food_type, "value") else i.food_type).lower() if i.food_type else "",
                "_raw_item": i,
            })

        pref = payload.get("preference") or session.food_preference
        res = run_recommendation_pipeline(items_dict, preference=pref)
        combined = res["priority"] + res["premium"] + res["additional"]
        return [c["_raw_item"] for c in combined if "_raw_item" in c][:limit]
