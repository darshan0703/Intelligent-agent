"""
app/infrastructure/repositories/session_repository.py
Redis-backed session repository with memory cache fallback.
"""
from __future__ import annotations
import json
from datetime import datetime
from app.config.settings import get_settings
from app.domain.session.entities import ConversationTurn, Screen, SessionState
from app.infrastructure.cache.redis_client import get_redis_client
from app.ports.session_port import SessionRepository

_in_memory_sessions: dict[str, str] = {}


class RedisSessionRepository(SessionRepository):
    def __init__(self):
        self.settings = get_settings()

    def _serialize(self, s: SessionState) -> str:
        data = {
            "session_id": s.session_id,
            "tenant_id": s.tenant_id,
            "channel": s.channel,
            "food_preference": s.food_preference,
            "last_category": s.last_category,
            "last_item_id": s.last_item_id,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat(),
            "last_active_at": s.last_active_at.isoformat(),
            "current_screen": {
                "name": s.current_screen.name,
                "available_controls": s.current_screen.available_controls,
            } if s.current_screen else None,
            "conversation_history": [
                {
                    "role": t.role,
                    "content": t.content,
                    "timestamp": t.timestamp.isoformat(),
                    "metadata": t.metadata,
                }
                for t in s.conversation_history
            ],
        }
        return json.dumps(data)

    def _deserialize(self, raw: str) -> SessionState:
        data = json.loads(raw)
        screen = None
        if data.get("current_screen"):
            screen = Screen(
                name=data["current_screen"]["name"],
                available_controls=data["current_screen"].get("available_controls", []),
            )
        history = [
            ConversationTurn(
                role=t["role"],
                content=t["content"],
                timestamp=datetime.fromisoformat(t["timestamp"]),
                metadata=t.get("metadata", {}),
            )
            for t in data.get("conversation_history", [])
        ]
        return SessionState(
            session_id=data["session_id"],
            tenant_id=data.get("tenant_id", "default"),
            channel=data.get("channel", "kiosk"),
            current_screen=screen,
            food_preference=data.get("food_preference"),
            last_category=data.get("last_category"),
            last_item_id=data.get("last_item_id"),
            conversation_history=history,
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active_at=datetime.fromisoformat(data["last_active_at"]),
            is_active=data.get("is_active", True),
        )

    async def create(self, session: SessionState) -> SessionState:
        key = f"session:{session.session_id}"
        serialized = self._serialize(session)
        client = await get_redis_client()
        if client:
            await client.set(key, serialized, ex=self.settings.session_ttl_seconds)
        else:
            _in_memory_sessions[key] = serialized
        return session

    async def get(self, session_id: str) -> SessionState | None:
        key = f"session:{session_id}"
        client = await get_redis_client()
        if client:
            raw = await client.get(key)
        else:
            raw = _in_memory_sessions.get(key)
        if not raw:
            return None
        return self._deserialize(raw)

    async def update(self, session: SessionState) -> SessionState:
        return await self.create(session)

    async def delete(self, session_id: str) -> None:
        key = f"session:{session_id}"
        client = await get_redis_client()
        if client:
            await client.delete(key)
        _in_memory_sessions.pop(key, None)
