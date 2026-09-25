"""
app/api/v1/router.py
Main v1 router aggregator.
"""
from __future__ import annotations
from fastapi import APIRouter
from app.api.v1.cart import router as cart_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.order import router as order_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.session import router as session_router
from app.api.v1.voice import router as voice_router

api_v1_router = APIRouter()

api_v1_router.include_router(session_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(cart_router)
api_v1_router.include_router(order_router)
api_v1_router.include_router(conversation_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(recommendations_router)
