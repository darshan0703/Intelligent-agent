"""
app/ports/session_port.py
Repository protocol for session state management.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.session.entities import SessionState

@runtime_checkable
class SessionRepository(Protocol):
    async def create(self, session: SessionState) -> SessionState:
        ...

    async def get(self, session_id: str) -> SessionState | None:
        ...

    async def update(self, session: SessionState) -> SessionState:
        ...

    async def delete(self, session_id: str) -> None:
        ...
