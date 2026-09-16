import os

base_dir = r"C:\Users\Hemanth Raju N\Downloads\Working Model\TheAtom\backend\app"

files = {}

# 1. infrastructure/db/models.py
files["infrastructure/db/models.py"] = '''"""
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
'''

# 2. infrastructure/db/connection.py
files["infrastructure/db/connection.py"] = '''"""
app/infrastructure/db/connection.py
Async database engine, session factory, and transaction management.
"""
from __future__ import annotations
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config.settings import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=settings.db_pool_pre_ping,
            echo=settings.db_echo,
        )
    return _async_engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db_engine() -> None:
    global _async_engine
    if _async_engine is not None:
        logger.info("closing_db_engine")
        await _async_engine.dispose()
        _async_engine = None


def get_sync_engine():
    settings = get_settings()
    return create_engine(settings.sync_database_url)
'''

# 3. infrastructure/cache/redis_client.py
files["infrastructure/cache/redis_client.py"] = '''"""
app/infrastructure/cache/redis_client.py
Async Redis client with graceful fallback for resilience.
"""
from __future__ import annotations
import json
from typing import Any
import redis.asyncio as aioredis
from app.config.settings import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis | None:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        try:
            client = aioredis.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True,
            )
            # Test connectivity with short timeout
            await client.ping()
            _redis_client = client
            logger.info("redis_connected", url=settings.redis_url)
        except Exception as exc:
            logger.warning("redis_unavailable_fallback_active", error=str(exc))
            _redis_client = None
    return _redis_client


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        logger.info("closing_redis_client")
        await _redis_client.aclose()
        _redis_client = None


async def set_json(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    client = await get_redis_client()
    if not client:
        return False
    try:
        data = json.dumps(value)
        await client.set(key, data, ex=ttl_seconds)
        return True
    except Exception as exc:
        logger.warning("redis_set_failed", key=key, error=str(exc))
        return False


async def get_json(key: str) -> Any | None:
    client = await get_redis_client()
    if not client:
        return None
    try:
        val = await client.get(key)
        if val is None:
            return None
        return json.loads(val)
    except Exception as exc:
        logger.warning("redis_get_failed", key=key, error=str(exc))
        return None
'''

# 4. infrastructure/llm/groq_adapter.py
files["infrastructure/llm/groq_adapter.py"] = '''"""
app/infrastructure/llm/groq_adapter.py
Groq LLM adapter implementing LanguageModelPort.
LangChain dependencies are strictly contained inside this adapter.
"""
from __future__ import annotations
import time
from typing import Any, TypeVar
from pydantic import BaseModel
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config.settings import get_settings
from app.observability.logging import get_logger
from app.ports.llm_port import LanguageModelPort

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class GroqAdapter(LanguageModelPort):
    def __init__(self, model_name: str | None = None, temperature: float | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.groq_default_model
        self.temperature = temperature if temperature is not None else settings.groq_temperature
        self.api_key = settings.groq_api_key

        self._llm = ChatGroq(
            model=self.model_name,
            temperature=self.temperature,
            groq_api_key=self.api_key,
            max_tokens=settings.groq_max_tokens,
            timeout=settings.groq_timeout_seconds,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def structured_complete(self, prompt: str, output_schema: type[T], **kwargs: Any) -> T:
        start_time = time.monotonic()
        structured_llm = self._llm.with_structured_output(output_schema)
        try:
            result = await structured_llm.ainvoke(prompt)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("llm_structured_success", model=self.model_name, schema=output_schema.__name__, duration_ms=duration_ms)
            return result
        except Exception as exc:
            logger.error("llm_structured_failed", model=self.model_name, schema=output_schema.__name__, error=str(exc))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        start_time = time.monotonic()
        try:
            response = await self._llm.ainvoke(prompt)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info("llm_generate_success", model=self.model_name, duration_ms=duration_ms)
            return str(response.content)
        except Exception as exc:
            logger.error("llm_generate_failed", model=self.model_name, error=str(exc))
            raise

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"role": "assistant", "content": "Tools routed"}
'''

# 5. infrastructure/repositories/catalog_repository.py
files["infrastructure/repositories/catalog_repository.py"] = '''"""
app/infrastructure/repositories/catalog_repository.py
Async SQLAlchemy implementation of CatalogRepository protocol.
Always enforces branch inventory checks and Decimal financial precision.
"""
from __future__ import annotations
from decimal import Decimal
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from app.domain.catalog.entities import InventorySnapshot, MenuItem
from app.domain.catalog.value_objects import CategorySlug, FoodType, Price, ServingType
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import CrossSell, Inventory, MealDefault, MealUpgradeRule, MenuItem as MenuItemORM
from app.ports.catalog_port import CatalogRepository


class SQLAlchemyCatalogRepository(CatalogRepository):
    def __init__(self, branch_id: int = 1):
        self.default_branch_id = branch_id
        self._session_maker = get_async_session_maker()

    def _to_domain(self, orm: MenuItemORM, inv: Inventory | None = None) -> MenuItem:
        snapshot = None
        if inv is not None:
            snapshot = InventorySnapshot(
                item_id=orm.id,
                branch_id=inv.branch_id,
                stock=inv.stock,
                expiry_date=inv.expiry_date,
            )

        return MenuItem(
            id=orm.id,
            name=orm.name,
            short_description=orm.short_description,
            long_description=orm.long_description,
            price=Price(Decimal(str(orm.price))),
            category=CategorySlug(orm.category.lower()),
            food_type=FoodType(orm.food_type.lower()) if orm.food_type else None,
            serving_type=ServingType(orm.serving_type.lower()) if orm.serving_type else None,
            meal_role=orm.meal_role,
            meal_size=orm.meal_size,
            is_meal_available=orm.is_meal_available,
            is_available=orm.is_available,
            image=orm.image,
            meal_image=orm.meal_image,
            section=orm.section,
            section_order=orm.section_order,
            display_order=orm.display_order,
            inventory=snapshot,
        )

    async def get_by_category(self, category: str, branch_id: int) -> list[MenuItem]:
        target_branch = branch_id or self.default_branch_id
        cat_lower = category.lower()
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.item_id)
                .where(
                    Inventory.branch_id == target_branch,
                    MenuItemORM.is_available.is_(True),
                    Inventory.stock > 0,
                )
            )
            if cat_lower in ("veg", "non_veg", "non veg"):
                stmt = stmt.where(MenuItemORM.food_type.ilike(cat_lower))
            else:
                stmt = stmt.where(MenuItemORM.category.ilike(cat_lower))

            stmt = stmt.order_by(MenuItemORM.section_order.nulls_last(), MenuItemORM.display_order.nulls_last())
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_all_available(self, branch_id: int) -> list[MenuItem]:
        target_branch = branch_id or self.default_branch_id
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.item_id)
                .where(
                    Inventory.branch_id == target_branch,
                    MenuItemORM.is_available.is_(True),
                    Inventory.stock > 0,
                )
                .order_by(MenuItemORM.display_order.nulls_last())
            )
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_by_id(self, item_id: int, branch_id: int) -> MenuItem | None:
        target_branch = branch_id or self.default_branch_id
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.item_id)
                .where(MenuItemORM.id == item_id, Inventory.branch_id == target_branch)
            )
            res = await session.execute(stmt)
            row = res.first()
            if not row:
                return None
            return self._to_domain(row[0], row[1])

    async def search_by_name(self, name: str, branch_id: int) -> list[MenuItem]:
        target_branch = branch_id or self.default_branch_id
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.item_id)
                .where(
                    MenuItemORM.name.ilike(f"%{name}%"),
                    Inventory.branch_id == target_branch,
                    MenuItemORM.is_available.is_(True),
                )
            )
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_cross_sells(self, item_id: int, limit: int = 4) -> list[MenuItem]:
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(CrossSell, MenuItemORM.id == CrossSell.recommended_item_id)
                .join(Inventory, MenuItemORM.id == Inventory.item_id)
                .where(
                    CrossSell.source_item_id == item_id,
                    Inventory.branch_id == self.default_branch_id,
                    Inventory.stock > 0,
                    MenuItemORM.is_available.is_(True),
                )
                .order_by(CrossSell.priority.asc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_meal_options(self, item_id: int) -> dict | None:
        async with self._session_maker() as session:
            burger_orm = await session.get(MenuItemORM, item_id)
            if not burger_orm or not burger_orm.is_meal_available:
                return None

            defaults_res = await session.execute(select(MealDefault))
            defaults = {d.meal_size: d for d in defaults_res.scalars().all()}

            rules_res = await session.execute(select(MealUpgradeRule).where(MealUpgradeRule.item_id == item_id))
            rules = {r.meal_size: r for r in rules_res.scalars().all()}

            return {
                "item_id": item_id,
                "is_meal_available": True,
                "burger_name": burger_orm.name,
                "burger_price": float(burger_orm.price),
                "defaults": {k: {"side_id": v.default_side_id, "drink_id": v.default_drink_id} for k, v in defaults.items()},
                "upgrade_rules": {k: float(v.extra_price) for k, v in rules.items()},
            }

    async def get_sections(self, category: str, branch_id: int) -> list[dict]:
        items = await self.get_by_category(category, branch_id)
        sections: dict[str, list[dict]] = {}
        for item in items:
            sec_name = item.section or "Featured"
            if sec_name not in sections:
                sections[sec_name] = []
            sections[sec_name].append({
                "id": item.id,
                "name": item.name,
                "price": str(item.price.amount),
                "category": str(item.category),
                "foodType": str(item.food_type) if item.food_type else None,
                "image": item.image,
                "meal_image": item.meal_image,
                "is_meal_available": item.is_meal_available,
                "stock": item.inventory.stock if item.inventory else 0,
            })
        return [{"title": k, "products": v} for k, v in sections.items()]
'''

# 6. infrastructure/repositories/session_repository.py
files["infrastructure/repositories/session_repository.py"] = '''"""
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
'''

# 7. infrastructure/repositories/order_repository.py
files["infrastructure/repositories/order_repository.py"] = '''"""
app/infrastructure/repositories/order_repository.py
Async SQLAlchemy Order repository with atomic inventory deduction via row locking.
"""
from __future__ import annotations
from decimal import Decimal
from sqlalchemy import select
from app.domain.catalog.value_objects import Price
from app.domain.order.entities import Order, OrderLine, OrderStatus
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import Inventory, OrderLineModel, OrderModel
from app.ports.order_port import OrderRepository


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self):
        self._session_maker = get_async_session_maker()

    async def create(self, order: Order) -> Order:
        async with self._session_maker() as session:
            async with session.begin():
                orm_order = OrderModel(
                    id=order.order_id,
                    session_id=order.session_id,
                    tenant_id=order.tenant_id,
                    branch_id=order.branch_id,
                    status=order.status.value,
                    payment_method=order.payment_method,
                    total_amount=order.total.amount,
                    created_at=order.created_at,
                )
                session.add(orm_order)
                for line in order.lines:
                    orm_line = OrderLineModel(
                        order_id=order.order_id,
                        item_id=line.item_id,
                        item_name=line.item_name,
                        quantity=line.quantity,
                        unit_price=line.unit_price.amount,
                        line_type=line.line_type,
                    )
                    session.add(orm_line)
        return order

    async def get(self, order_id: str) -> Order | None:
        async with self._session_maker() as session:
            orm_order = await session.get(OrderModel, order_id)
            if not orm_order:
                return None
            lines_res = await session.execute(select(OrderLineModel).where(OrderLineModel.order_id == order_id))
            lines = [
                OrderLine(
                    item_id=l.item_id,
                    item_name=l.item_name,
                    quantity=l.quantity,
                    unit_price=Price(Decimal(str(l.unit_price))),
                    line_type=l.line_type,
                )
                for l in lines_res.scalars().all()
            ]
            return Order(
                order_id=orm_order.id,
                session_id=orm_order.session_id,
                tenant_id=orm_order.tenant_id,
                branch_id=orm_order.branch_id,
                lines=lines,
                status=OrderStatus(orm_order.status),
                payment_method=orm_order.payment_method,
                created_at=orm_order.created_at,
            )

    async def update_status(self, order_id: str, status: OrderStatus) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                order = await session.get(OrderModel, order_id)
                if order:
                    order.status = status.value

    async def deduct_inventory(self, branch_id: int, item_id: int, quantity: int) -> bool:
        async with self._session_maker() as session:
            async with session.begin():
                stmt = (
                    select(Inventory)
                    .where(Inventory.branch_id == branch_id, Inventory.item_id == item_id)
                    .with_for_update()
                )
                res = await session.execute(stmt)
                inv = res.scalar_one_or_none()
                if not inv or inv.stock < quantity:
                    return False
                inv.stock -= quantity
                return True
'''

for rel_path, content in files.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Generated: {rel_path}")

print("Batch 2 completed successfully.")
