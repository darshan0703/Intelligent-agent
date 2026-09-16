"""
app/ports/recommendation_port.py
Protocol for recommendation engine.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.session.entities import SessionState
from app.domain.recommendation.entities import RecommendationSet

@runtime_checkable
class RecommendationEngine(Protocol):
    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None,
        food_type: str | None,
        branch_id: int,
    ) -> RecommendationSet:
        ...
