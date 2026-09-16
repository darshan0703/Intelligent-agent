"""
app/api/v1/session.py
Session lifecycle and screen synchronization endpoints.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.application.session_service import SessionService
from app.infrastructure.repositories.session_repository import RedisSessionRepository

router = APIRouter(prefix="/session", tags=["session"])
_session_repo = RedisSessionRepository()
_session_service = SessionService(_session_repo)


class StartSessionRequest(BaseModel):
    tenant_id: str = "default"
    channel: str = "kiosk"
    screen: str = "home"


class SyncScreenRequest(BaseModel):
    screen: str
    available_controls: list[str] = []


@router.post("/start")
async def start_session(req: StartSessionRequest | None = None):
    tenant = req.tenant_id if req else "default"
    channel = req.channel if req else "kiosk"
    initial_screen = req.screen if req else "home"

    session = await _session_service.start_session(tenant_id=tenant, channel=channel, initial_screen=initial_screen)
    return {
        "success": True,
        "session_id": session.session_id,
        "screen": session.current_screen.name if session.current_screen else "home",
        "message": "Welcome to Burger King India! How can I help you today?",
        "voice_enabled": True,
    }


@router.post("/{session_id}/screen")
async def sync_screen(session_id: str, req: SyncScreenRequest):
    session = await _session_service.sync_screen(
        session_id=session_id,
        screen_name=req.screen,
        available_controls=req.available_controls,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "success": True,
        "screen": session.current_screen.name if session.current_screen else req.screen,
        "available_controls": session.current_screen.available_controls if session.current_screen else [],
    }


@router.delete("/{session_id}")
async def end_session(session_id: str):
    await _session_service.end_session(session_id)
    return {"success": True, "message": "Session ended"}
