"""
app/domain/session/entities.py
Domain entities for the session bounded context.
No framework imports — pure Python dataclasses.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class SessionPhase(str, Enum):
    GREETING = "greeting"
    BROWSING = "browsing"
    SELECTING = "selecting"
    CUSTOMIZING = "customizing"
    REVIEWING_CART = "reviewing_cart"
    CHECKOUT = "checkout"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    IDLE = "idle"


@dataclass
class Screen:
    name: str
    available_controls: list[str] = field(default_factory=list)


@dataclass
class ConversationTurn:
    role: str  # 'user' | 'assistant' | 'tool'
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CartItem:
    item_id: str
    item_name: str
    quantity: int
    unit_price: Decimal
    customizations: dict[str, Any] = field(default_factory=dict)
    line_type: str = "item"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)


@dataclass
class SessionState:
    session_id: str
    tenant_id: str = "default"
    branch_id: str = "1"
    channel: str = "kiosk"
    phase: SessionPhase = SessionPhase.GREETING
    current_screen: Screen | None = None
    food_preference: str | None = None
    last_category: str | None = None
    last_item_id: int | None = None
    cart: list[CartItem] = field(default_factory=list)
    conversation_history: list[ConversationTurn] = field(default_factory=list)
    order_id: str | None = None
    language: str = "en"
    customer_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    def update_screen(self, screen: Screen) -> None:
        self.current_screen = screen
        self.last_active_at = datetime.utcnow()

    def add_turn(self, turn: ConversationTurn) -> None:
        self.conversation_history.append(turn)
        self.last_active_at = datetime.utcnow()
