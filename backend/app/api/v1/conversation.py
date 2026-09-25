"""
app/api/v1/conversation.py
Conversational agent message processing endpoint.
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.application.cart_service import CartService
from app.application.conversation_service import ConversationService
from app.application.session_service import SessionService
from app.infrastructure.llm.hybrid_llm_adapter import HybridLLMAdapter
from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository
from app.infrastructure.repositories.session_repository import RedisSessionRepository
from app.intelligence.agent.cashier_agent import CashierAgent
from app.intelligence.recommendation.engine import HybridRecommendationEngine

router = APIRouter(prefix="", tags=["conversation"])

# Instantiate singletons for dependency wiring
_catalog = SQLAlchemyCatalogRepository()
_session_repo = RedisSessionRepository()
_session_service = SessionService(_session_repo)
_cart_service = CartService(_catalog)
_llm = HybridLLMAdapter()
_rec_engine = HybridRecommendationEngine(_catalog)
_agent = CashierAgent(_llm, _catalog, _rec_engine)

_conversation_service = ConversationService(
    session_service=_session_service,
    cart_service=_cart_service,
    catalog=_catalog,
    llm=_llm,
    agent=_agent,
)


class MessageRequest(BaseModel):
    message: str
    session_id: str | None = None
    branch_id: int = 1


@router.post("/message")
async def handle_message(req: MessageRequest):
    sid = req.session_id or "default-kiosk-session"
    res = await _conversation_service.process_message(
        session_id=sid,
        user_input=req.message,
        branch_id=req.branch_id,
    )
    screen_payload = res.data or {}
    if res.ui_action and "ui_action" not in screen_payload:
        screen_payload["ui_action"] = res.ui_action
        screen_payload["value"] = res.ui_action_value

    return {
        "message": res.message,
        "screen": res.screen,
        "ui_action": res.ui_action,
        "ui_action_value": res.ui_action_value,
        "cart": res.cart_summary,
        "data": screen_payload,
    }

