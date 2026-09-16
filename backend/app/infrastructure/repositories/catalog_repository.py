"""
app/infrastructure/repositories/catalog_repository.py
Async SQLAlchemy implementation of CatalogRepository protocol.
Always enforces branch inventory checks and Decimal financial precision.
"""
from __future__ import annotations
import time
from decimal import Decimal
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from app.domain.catalog.entities import InventorySnapshot, MenuItem
from app.domain.catalog.value_objects import CategorySlug, FoodType, Price, ServingType
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import CrossSell, Inventory, MealDefault, MealUpgradeRule, MenuItem as MenuItemORM
from app.ports.catalog_port import CatalogRepository

_CATALOG_CACHE: dict[str, tuple[float, any]] = {}
_CACHE_TTL_SECONDS = 300.0


def get_category_default_image(category: any, name: str | None = None) -> str:
    cat = str(category or "").lower()
    n = (name or "").lower()
    if "drink" in cat or "beverage" in cat or any(x in n for x in ("coke", "coffee", "shake", "fizz", "latte", "tea")):
        return "/src/assets/images/Drinks/Coca Cola.png"
    if "side" in cat or any(x in n for x in ("fries", "nugget", "wing", "strip", "hashbrown", "ring")):
        return "/src/assets/images/Sides/Fries (Medium).png"
    if "dessert" in cat or any(x in n for x in ("sundae", "softie", "mousse", "cone", "cup")):
        return "/src/assets/images/Dessert/Chocolate sundae.png"
    return "/src/assets/images/Burgers/Crispy Veg.png"


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
            category=CategorySlug.from_str(orm.category),
            food_type=FoodType.from_str(orm.food_type) if orm.food_type else None,
            serving_type=ServingType.from_str(orm.serving_type) if orm.serving_type else None,
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
        cache_key = f"cat:{cat_lower}:{target_branch}"
        cached = _CATALOG_CACHE.get(cache_key)
        if cached and (time.time() - cached[0] < _CACHE_TTL_SECONDS):
            return cached[1]

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
            result = [self._to_domain(orm, inv) for orm, inv in res.all()]
            _CATALOG_CACHE[cache_key] = (time.time(), result)
            return result

    async def get_all_available(self, branch_id: int) -> list[MenuItem]:
        target_branch = branch_id or self.default_branch_id
        cache_key = f"all:{target_branch}"
        cached = _CATALOG_CACHE.get(cache_key)
        if cached and (time.time() - cached[0] < _CACHE_TTL_SECONDS):
            return cached[1]

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
            result = [self._to_domain(orm, inv) for orm, inv in res.all()]
            _CATALOG_CACHE[cache_key] = (time.time(), result)
            return result

    async def get_by_id(self, item_id: int, branch_id: int) -> MenuItem | None:
        target_branch = branch_id or self.default_branch_id
        cache_key = f"id:{item_id}:{target_branch}"
        cached = _CATALOG_CACHE.get(cache_key)
        if cached and (time.time() - cached[0] < _CACHE_TTL_SECONDS):
            return cached[1]

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
            result = self._to_domain(row[0], row[1])
            _CATALOG_CACHE[cache_key] = (time.time(), result)
            return result

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
        cache_key = f"cross:{item_id}:{limit}"
        cached = _CATALOG_CACHE.get(cache_key)
        if cached and (time.time() - cached[0] < _CACHE_TTL_SECONDS):
            return cached[1]

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
            result = [self._to_domain(orm, inv) for orm, inv in res.all()]
            _CATALOG_CACHE[cache_key] = (time.time(), result)
            return result

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
        cache_key = f"sections:{category}:{branch_id}"
        cached = _CATALOG_CACHE.get(cache_key)
        if cached and (time.time() - cached[0] < _CACHE_TTL_SECONDS):
            return cached[1]

        items = await self.get_by_category(category, branch_id)
        sections: dict[str, list[dict]] = {}
        for item in items:
            sec_name = item.section or "Featured"
            if sec_name not in sections:
                sections[sec_name] = []
            is_veg = False
            if item.food_type:
                ft = str(item.food_type.value if hasattr(item.food_type, "value") else item.food_type).lower()
                is_veg = "veg" in ft and "non" not in ft

            fallback = get_category_default_image(item.category, item.name)
            img = item.image or fallback
            if img and not img.startswith("http") and not img.startswith("/"):
                img = "/" + img
            meal_img = item.meal_image or img
            if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
                meal_img = "/" + meal_img

            sections[sec_name].append({
                "id": item.id,
                "name": item.name,
                "shortDescription": item.short_description or "",
                "longDescription": item.long_description or "",
                "price": float(item.price.amount),
                "category": str(item.category.value if hasattr(item.category, "value") else item.category),
                "type": "veg" if is_veg else "non veg",
                "foodType": "veg" if is_veg else "non veg",
                "image": img,
                "meal_image": meal_img,
                "is_meal_available": item.is_meal_available,
                "stock": item.inventory.stock if item.inventory else 50,
            })
        result = [{"id": k.lower().replace(" ", "-"), "title": k, "products": v} for k, v in sections.items()]
        _CATALOG_CACHE[cache_key] = (time.time(), result)
        return result

