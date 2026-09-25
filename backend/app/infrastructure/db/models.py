"""
app/infrastructure/db/models.py
SQLAlchemy 2.0 ORM models for TheAtom commercial database.
Uses modern DeclarativeBase, Mapped, and mapped_column.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    branches: Mapped[list[Branch]] = relationship("Branch", back_populates="brand", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Brand id={self.id} name={self.name}>"


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)

    brand: Mapped[Brand] = relationship("Brand", back_populates="branches")

    def __repr__(self) -> str:
        return f"<Branch id={self.id} name={self.name}>"


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meal_image: Mapped[str | None] = mapped_column(String(500), nullable=True)

    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    food_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_meal_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    section_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    serving_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    meal_role: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 'main', 'side', 'drink'
    meal_size: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_meal_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    velocity_score: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    perishability_index: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)
    overstock_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    inventory_records: Mapped[list[Inventory]] = relationship("Inventory", back_populates="item")

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} name={self.name} price={self.price}>"


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True, index=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_overstock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    perishability_index: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)

    item: Mapped[MenuItem] = relationship("MenuItem", back_populates="inventory_records")


class CrossSell(Base):
    __tablename__ = "cross_sell"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    primary_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    recommended_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, default=1.0, nullable=True)


class MealUpgradeRule(Base):
    __tablename__ = "meal_upgrade_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    upgrade_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    upgrade_price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))


class ContextualObservationModel(Base):
    __tablename__ = "contextual_observations"

    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    predicate: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(50), nullable=True, default="session")
    context_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, default=1.0)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True, default="inferred")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Legacy telemetry compatibility fields
    context_state: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
    recommended_item_ids: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    policy_applied: Mapped[str | None] = mapped_column(String(100), nullable=True, default="general")
    user_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="cash")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OrderLineModel(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_type: Mapped[str] = mapped_column(String(50), nullable=False, default="item")


class UserModel(Base):
    """
    v4 Identity Model: users table.
    Identity key for WhatsApp (phone_number) and Web login.
    """
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sessions: Mapped[list[SessionModel]] = relationship("SessionModel", back_populates="user")


class SessionModel(Base):
    """
    v4 Identity Model: sessions table.
    session_id is generated by client (UUID v4) and persisted in localStorage/kiosk storage.
    user_id is NULLABLE FK (null for anonymous sessions today, stitched when user logs in via WhatsApp/Web).
    """
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    mindset_state: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    cart_state: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    user: Mapped[UserModel | None] = relationship("UserModel", back_populates="sessions")


