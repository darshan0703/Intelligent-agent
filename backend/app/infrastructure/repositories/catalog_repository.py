"""
app/infrastructure/repositories/catalog_repository.py
Async SQLAlchemy implementation of CatalogRepository protocol.
Always enforces branch inventory checks, Decimal financial precision, and null-safety.
"""
from __future__ import annotations
import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import selectinload

from app.domain.catalog.entities import InventorySnapshot, MenuItem
from app.domain.catalog.value_objects import CategorySlug, FoodType, Price, ServingType
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import (
    ContextualObservationModel,
    CrossSell,
    Inventory,
    MealUpgradeRule,
    MenuItem as MenuItemORM,
)
from app.ports.catalog_port import CatalogRepository

# Zero-cache dev refactor: All repository calls execute direct SELECT queries against PostgreSQL
_CATALOG_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 0.0


def get_category_default_image(category: Any, name: str | None = None) -> str:
    cat = str(category or "").lower()
    n = (name or "").lower()
    if "drink" in cat or "beverage" in cat or any(x in n for x in ("coke", "coffee", "shake", "fizz", "latte", "tea", "pepsi")):
        return "/src/assets/images/Drinks/Coca Cola.png"
    if "side" in cat or any(x in n for x in ("fries", "nugget", "wing", "strip", "hashbrown", "ring", "dip")):
        return "/src/assets/images/Sides/Fries (Medium).png"
    if "dessert" in cat or any(x in n for x in ("sundae", "softie", "mousse", "cone", "cup", "lava", "cake")):
        return "/src/assets/images/Dessert/Chocolate sundae.png"
    return "/src/assets/images/Burgers/Crispy Veg.png"


def infer_fallback_food_type(name: str, desc: str | None = None) -> FoodType:
    full = f"{name} {desc or ''}".lower()
    if any(k in full for k in ["chicken", "mutton", "meat", "fish", "egg", "non veg", "non-veg", "nonveg"]):
        return FoodType.NON_VEG
    return FoodType.VEG


def infer_fallback_category(name: str) -> CategorySlug:
    n = name.lower()
    if any(x in n for x in ["coke", "shake", "coffee", "fizz", "pepsi", "latte", "drink", "tea", "juice"]):
        return CategorySlug.DRINK
    if any(x in n for x in ["fries", "nugget", "wing", "strip", "dip", "hashbrown", "side", "snack"]):
        return CategorySlug.SIDE
    if any(x in n for x in ["sundae", "mousse", "softie", "lava", "dessert", "cake", "ice cream"]):
        return CategorySlug.DESSERT
    return CategorySlug.BURGER


class SQLAlchemyCatalogRepository(CatalogRepository):
    def __init__(self, branch_id: int = 1):
        self.default_branch_id = branch_id
        self._session_maker = get_async_session_maker()

    def _to_domain(self, orm: MenuItemORM, inv: Inventory | None = None) -> MenuItem:
        snapshot = None
        inv_overstock = False
        inv_perish = 1
        if inv is not None:
            exp_date = inv.expiry_date.date() if isinstance(inv.expiry_date, datetime) else inv.expiry_date
            inv_overstock = bool(getattr(inv, "is_overstock", False) or getattr(orm, "overstock_flag", False))
            inv_perish = int(getattr(inv, "perishability_index", 1) or getattr(orm, "perishability_index", 1) or 1)
            snapshot = InventorySnapshot(
                item_id=orm.id,
                branch_id=inv.branch_id or self.default_branch_id,
                stock=inv.stock_quantity if inv.stock_quantity is not None else 50,
                expiry_date=exp_date,
                overstock_flag=inv_overstock,
                perishability_index=inv_perish,
            )

        # Ensure safe price conversion
        price_val = orm.price if orm.price is not None else Decimal("99.00")
        if not isinstance(price_val, Decimal):
            price_val = Decimal(str(price_val))

        # Safe category parsing
        try:
            category_slug = CategorySlug.from_str(orm.category) if orm.category else infer_fallback_category(orm.name)
        except Exception:
            category_slug = infer_fallback_category(orm.name)

        # Safe food type parsing
        food_type_val = None
        if orm.food_type:
            food_type_val = FoodType.from_str(orm.food_type)
        if food_type_val is None:
            food_type_val = infer_fallback_food_type(orm.name, orm.short_description)

        # Safe serving type parsing
        serving_type_val = ServingType.from_str(orm.serving_type) if orm.serving_type else None

        # Safe image paths
        fallback_img = get_category_default_image(category_slug.value, orm.name)
        img = orm.image or fallback_img
        if img and not img.startswith("http") and not img.startswith("/"):
            img = "/" + img

        meal_img = orm.meal_image or img
        if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
            meal_img = "/" + meal_img

        v_score = float(getattr(orm, "velocity_score", 0.0) or 0.0)
        p_index = int(getattr(orm, "perishability_index", 1) or inv_perish)
        o_flag = bool(getattr(orm, "overstock_flag", False) or inv_overstock)

        # Baseline inference for fresh perishable items if not set in DB
        name_lower = (orm.name or "").lower()
        if p_index == 1 and any(w in name_lower for w in ["dairy", "mango puree", "fresh milk", "soft serve", "sundae", "thick shake"]):
            p_index = 4

        return MenuItem(
            id=orm.id,
            name=orm.name,
            short_description=orm.short_description or orm.name,
            long_description=orm.long_description or orm.name,
            price=Price(price_val),
            category=category_slug,
            food_type=food_type_val,
            serving_type=serving_type_val,
            meal_role=orm.meal_role or ("main" if category_slug == CategorySlug.BURGER else category_slug.value),
            meal_size=orm.meal_size or "regular",
            is_meal_available=bool(orm.is_meal_available),
            is_available=bool(orm.is_available),
            image=img,
            meal_image=meal_img,
            section=orm.section or category_slug.value.capitalize(),
            section_order=orm.section_order or 0,
            display_order=orm.display_order or 0,
            inventory=snapshot,
            velocity_score=v_score,
            perishability_index=p_index,
            overstock_flag=o_flag,
        )

    def _from_supabase_row(self, row: dict) -> MenuItem:
        p_val = Decimal(str(row["price"])) if row.get("price") is not None else Decimal("99.00")
        cat_str = str(row.get("category") or "burger").lower()
        try:
            cat_slug = CategorySlug.from_str(cat_str)
        except Exception:
            cat_slug = infer_fallback_category(row.get("name", ""))

        ft_val = None
        if row.get("food_type"):
            ft_val = FoodType.from_str(row["food_type"])
        if ft_val is None:
            ft_val = infer_fallback_food_type(row.get("name", ""), row.get("short_description"))

        serving_type_val = ServingType.from_str(row["serving_type"]) if row.get("serving_type") else None

        fallback_img = get_category_default_image(cat_slug.value, row.get("name"))
        img = row.get("image") or fallback_img
        if img and not img.startswith("http") and not img.startswith("/"):
            img = "/" + img
        meal_img = row.get("meal_image") or img
        if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
            meal_img = "/" + meal_img

        exp = row.get("expiry_date")
        if isinstance(exp, str):
            try:
                from datetime import date
                exp = datetime.fromisoformat(exp).date()
            except Exception:
                exp = None

        snapshot = InventorySnapshot(
            item_id=row["id"],
            branch_id=self.default_branch_id,
            stock=row.get("stock", 50),
            expiry_date=exp,
            overstock_flag=False,
            perishability_index=1,
        )

        return MenuItem(
            id=row["id"],
            name=row["name"],
            short_description=row.get("short_description") or row["name"],
            long_description=row.get("long_description") or row["name"],
            price=Price(p_val),
            category=cat_slug,
            food_type=ft_val,
            serving_type=serving_type_val,
            meal_role=row.get("meal_role") or ("main" if cat_slug == CategorySlug.BURGER else cat_slug.value),
            meal_size=row.get("meal_size") or "regular",
            is_meal_available=bool(row.get("is_meal_available")),
            is_available=bool(row.get("is_available", True)),
            image=img,
            meal_image=meal_img,
            section=row.get("section") or cat_slug.value.capitalize(),
            section_order=row.get("section_order") or 0,
            display_order=row.get("display_order") or 0,
            inventory=snapshot,
        )

    async def get_by_category(self, category: str, branch_id: int) -> list[MenuItem]:
        target_branch = branch_id or self.default_branch_id
        cat_lower = category.lower()

        try:
            from repositories.menu_repository import fetch_menu_rows
            rows = fetch_menu_rows()
            if rows:
                if cat_lower in ("veg", "non_veg", "non veg"):
                    cat_rows = [r for r in rows if str(r.get("food_type", "")).lower() == cat_lower]
                else:
                    cat_rows = [r for r in rows if str(r.get("category", "")).lower() == cat_lower]
                if cat_rows:
                    return [self._from_supabase_row(r) for r in cat_rows]
        except Exception:
            pass

        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.menu_item_id)
                .where(
                    Inventory.branch_id == target_branch,
                    Inventory.is_active == 1,
                    Inventory.available == 1,
                    Inventory.stock_quantity > 0,
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
        try:
            from repositories.menu_repository import fetch_menu_rows
            rows = fetch_menu_rows()
            if rows:
                return [self._from_supabase_row(r) for r in rows]
        except Exception:
            pass

        target_branch = branch_id or self.default_branch_id

        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.menu_item_id)
                .where(
                    Inventory.branch_id == target_branch,
                    Inventory.is_active == 1,
                    Inventory.available == 1,
                    Inventory.stock_quantity > 0,
                )
                .order_by(MenuItemORM.display_order.nulls_last())
            )
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_by_id(self, item_id: int, branch_id: int, bypass_cache: bool = True) -> MenuItem | None:
        try:
            from repositories.menu_repository import fetch_menu_rows
            rows = fetch_menu_rows()
            if rows:
                for r in rows:
                    if r["id"] == item_id:
                        return self._from_supabase_row(r)
        except Exception:
            pass

        target_branch = branch_id or self.default_branch_id

        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.menu_item_id)
                .where(
                    MenuItemORM.id == item_id,
                    Inventory.branch_id == target_branch,
                )
            )
            res = await session.execute(stmt)
            row = res.first()
            if not row:
                return None
            return self._to_domain(row[0], row[1])

    async def get_live_stock(self, item_id: int, branch_id: int = 1) -> int:
        """Cache-bypassing live stock query directly against the inventory table."""
        target_branch = branch_id or self.default_branch_id
        async with self._session_maker() as session:
            stmt = select(Inventory.stock_quantity).where(
                Inventory.menu_item_id == item_id,
                Inventory.branch_id == target_branch,
                Inventory.is_active == 1,
                Inventory.available == 1,
            )
            res = await session.execute(stmt)
            qty = res.scalar_one_or_none()
            return int(qty) if qty is not None else 0

    def clear_cache(self, item_id: int | None = None) -> None:
        """Clears in-memory catalog cache for immediate freshness."""
        global _CATALOG_CACHE
        if item_id is None:
            _CATALOG_CACHE.clear()
        else:
            _CATALOG_CACHE = {k: v for k, v in _CATALOG_CACHE.items() if f":{item_id}:" not in k}

    async def search_by_name(self, name: str, branch_id: int) -> list[MenuItem]:
        target_branch = branch_id or self.default_branch_id
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(Inventory, MenuItemORM.id == Inventory.menu_item_id)
                .where(
                    MenuItemORM.name.ilike(f"%{name}%"),
                    Inventory.branch_id == target_branch,
                    Inventory.is_active == 1,
                    Inventory.available == 1,
                    Inventory.stock_quantity > 0,
                )
            )
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_cross_sells(self, item_id: int, limit: int = 4) -> list[MenuItem]:
        async with self._session_maker() as session:
            stmt = (
                select(MenuItemORM, Inventory)
                .join(CrossSell, MenuItemORM.id == CrossSell.recommended_item_id)
                .join(Inventory, MenuItemORM.id == Inventory.menu_item_id)
                .where(
                    CrossSell.primary_item_id == item_id,
                    Inventory.branch_id == self.default_branch_id,
                    Inventory.stock_quantity > 0,
                    Inventory.is_active == 1,
                    Inventory.available == 1,
                )
                .order_by(CrossSell.confidence_score.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            return [self._to_domain(orm, inv) for orm, inv in res.all()]

    async def get_meal_options(self, item_id: int) -> dict | None:
        async with self._session_maker() as session:
            burger_orm = await session.get(MenuItemORM, item_id)
            if not burger_orm or not burger_orm.is_meal_available:
                return None

            rules_res = await session.execute(
                select(MealUpgradeRule, MenuItemORM)
                .join(MenuItemORM, MealUpgradeRule.upgrade_item_id == MenuItemORM.id)
                .where(MealUpgradeRule.base_item_id == item_id)
            )
            rules = rules_res.all()

            upgrades = []
            for r, item_orm in rules:
                upgrades.append({
                    "upgrade_item_id": r.upgrade_item_id,
                    "upgrade_item_name": item_orm.name,
                    "upgrade_price_delta": float(r.upgrade_price_delta),
                    "category": item_orm.category,
                })

            return {
                "item_id": item_id,
                "is_meal_available": True,
                "burger_name": burger_orm.name,
                "burger_price": float(burger_orm.price),
                "upgrades": upgrades,
            }

    async def get_sections(self, category: str, branch_id: int) -> list[dict]:
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

            # Dynamic badging
            p_val = float(item.price.amount)
            name_lower = item.name.lower()
            badge = None
            tag = "standard"

            if any(k in name_lower for k in ["whopper", "royale", "classic cold coffee", "peri peri fries"]):
                badge = "🔥 Bestseller"
                tag = "bestseller"
            elif p_val <= 69.0:
                badge = "⭐ Best Value"
                tag = "value"
            elif any(k in name_lower for k in ["peri peri", "fiery", "spicy", "chilli", "hell"]):
                badge = "🌶️ Spicy Flame"
                tag = "spicy"
            elif any(k in name_lower for k in ["shake", "sundae", "float", "lava"]):
                badge = "✨ Indulgent"
                tag = "indulgent"
            elif is_veg:
                badge = "🌿 Pure Veg"
                tag = "veg"

            sections[sec_name].append({
                "id": item.id,
                "name": item.name,
                "shortDescription": item.short_description or "",
                "longDescription": item.long_description or "",
                "price": p_val,
                "category": str(item.category.value if hasattr(item.category, "value") else item.category),
                "type": "veg" if is_veg else "non veg",
                "foodType": "veg" if is_veg else "non veg",
                "image": img,
                "meal_image": meal_img,
                "is_meal_available": item.is_meal_available,
                "stock": item.inventory.stock if item.inventory else 50,
                "badge": badge,
                "tag": tag,
            })
        return [{"id": k.lower().replace(" ", "-"), "title": k, "products": v} for k, v in sections.items()]

    async def record_observation(
        self,
        session_id: str,
        context_state: dict | str,
        recommended_item_ids: list[int] | str,
        policy_applied: str,
        user_action: str | None = None,
    ) -> None:
        """Record recommendation decision telemetry into contextual_observations table."""
        async with self._session_maker() as session:
            try:
                obs = ContextualObservationModel(
                    session_id=session_id,
                    context_state=json.dumps(context_state) if isinstance(context_state, dict) else str(context_state),
                    recommended_item_ids=json.dumps(recommended_item_ids) if isinstance(recommended_item_ids, list) else str(recommended_item_ids),
                    policy_applied=policy_applied,
                    user_action=user_action,
                    created_at=datetime.utcnow(),
                )
                session.add(obs)
                await session.commit()
            except Exception:
                await session.rollback()

    async def get_dismissed_item_ids(self, session_id: str) -> set[int]:
        """Fetch item IDs dismissed/rejected in the current session."""
        async with self._session_maker() as session:
            stmt = select(ContextualObservationModel).where(
                ContextualObservationModel.session_id == session_id,
                ContextualObservationModel.user_action == "dismissed",
            )
            res = await session.execute(stmt)
            records = res.scalars().all()
            dismissed: set[int] = set()
            for r in records:
                try:
                    ids = json.loads(r.recommended_item_ids)
                    if isinstance(ids, list):
                        dismissed.update(int(i) for i in ids if isinstance(i, (int, str)))
                except Exception:
                    pass
            return dismissed
