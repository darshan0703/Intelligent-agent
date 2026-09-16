"""
app/intelligence/memory/memory_service.py
Scoped contextual memory operations (rejections, affinities, preferences).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from app.domain.session.memory import ContextualObservation, ObservationScope, ObservationSource
from app.ports.memory_port import MemoryStore


class MemoryService:
    def __init__(self, store: MemoryStore):
        self.store = store

    async def record_meal_rejection(self, session_id: str, item_id: int, context: dict | None = None) -> None:
        obs = ContextualObservation.meal_rejection(session_id=session_id, item_id=item_id, context=context)
        await self.store.add_observation(obs)

    async def should_offer_meal(self, session_id: str, item_id: int) -> bool:
        observations = await self.store.get_observations(
            session_id=session_id,
            subject="meal_offer",
            scope="item",
        )
        for obs in observations:
            if not obs.is_expired and obs.predicate == "rejected" and obs.value == str(item_id):
                return False
        return True

    async def record_preference(
        self,
        session_id: str,
        pref_type: str,
        value: str,
        confidence: float = 1.0,
    ) -> None:
        obs = ContextualObservation(
            session_id=session_id,
            subject="preference",
            predicate=pref_type,
            value=value,
            scope=ObservationScope.SESSION,
            context={},
            confidence=confidence,
            source=ObservationSource.EXPLICIT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=2),
        )
        await self.store.add_observation(obs)
