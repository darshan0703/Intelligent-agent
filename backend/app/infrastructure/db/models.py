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
    inventory_items: Mapped[list[Inventory]] = relationship("Inventory", back_populates="branch", cascade="all, delete-orphan")

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
    serving_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    meal_role: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 'main', 'side', 'drink'
    meal_size: Mapped[str | None] = mapped_column(String(30), nullable=True)

    section_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_meal_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    inventory_records: Mapped[list[Inventory]] = relationship("Inventory", back_populates="item")

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} name={self.name} price={self.price}>"


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    branch: Mapped[Branch] = relationship("Branch", back_populates="inventory_items")
    item: Mapped[MenuItem] = relationship("MenuItem", back_populates="inventory_records")


class CrossSell(Base):
    __tablename__ = "cross_sell"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    recommended_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class MealDefault(Base):
    __tablename__ = "meal_defaults"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_size: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    default_side_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False)
    default_drink_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False)


class MealUpgradeRule(Base):
    __tablename__ = "meal_upgrade_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    meal_size: Mapped[str] = mapped_column(String(30), nullable=False)
    extra_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    branch_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lines: Mapped[list[OrderLineModel]] = relationship("OrderLineModel", back_populates="order", cascade="all, delete-orphan")


class OrderLineModel(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_type: Mapped[str] = mapped_column(String(30), default="item", nullable=False)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="lines")


class ContextualObservationModel(Base):
    __tablename__ = "contextual_observations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    context_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="explicit", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
