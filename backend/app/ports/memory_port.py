"""
app/ports/memory_port.py
Repository protocol for scoped contextual observations.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.session.memory import ContextualObservation

@runtime_checkable
class MemoryStore(Protocol):
    async def add_observation(self, obs: ContextualObservation) -> None:
        ...

    async def get_observations(
        self,
        session_id: str,
        subject: str | None = None,
        scope: str | None = None,
    ) -> list[ContextualObservation]:
        ...

    async def invalidate(self, session_id: str, subject: str, predicate: str) -> None:
        ...
