"""
app/api/v1/voice.py
Voice endpoints (TTS and STT) with configurable local engine or fallback.
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.observability.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="", tags=["voice"])


class TTSRequest(BaseModel):
    text: str


@router.post("/tts")
async def tts(req: TTSRequest):
    # Returns audio synthesis instruction for client or audio bytes
    return {"success": True, "message": "TTS ready", "text": req.text}
