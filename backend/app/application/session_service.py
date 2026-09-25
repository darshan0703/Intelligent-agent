"""
app/application/session_service.py
Use cases for session lifecycle and screen synchronization.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from app.domain.session.entities import Screen, SessionState
from app.ports.session_port import SessionRepository


class SessionService:
    def __init__(self, session_repo: SessionRepository):
        self.repo = session_repo

    async def start_session(
        self,
        session_id: str | None = None,
        tenant_id: str = "default",
        channel: str = "kiosk",
        initial_screen: str = "home",
    ) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        session = SessionState(
            session_id=sid,
            tenant_id=tenant_id,
            channel=channel,
            current_screen=Screen(name=initial_screen, available_controls=[]),
            food_preference=None,
            last_category=None,
            last_item_id=None,
            conversation_history=[],
            created_at=datetime.utcnow(),
            last_active_at=datetime.utcnow(),
            is_active=True,
        )
        return await self.repo.create(session)

    async def get_session(self, session_id: str) -> SessionState | None:
        return await self.repo.get(session_id)

    async def sync_screen(
        self,
        session_id: str,
        screen_name: str,
        available_controls: list[str],
    ) -> SessionState | None:
        session = await self.repo.get(session_id)
        if not session:
            return None
        session.update_screen(Screen(name=screen_name, available_controls=available_controls))
        return await self.repo.update(session)

    async def end_session(self, session_id: str) -> None:
        await self.repo.delete(session_id)
