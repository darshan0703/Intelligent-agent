"""
app/domain/catalog/entities.py
Pure domain entities for the catalog bounded context.
No framework imports. All money uses Decimal.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from app.domain.catalog.value_objects import CategorySlug, FoodType, Price, ServingType


@dataclass
class InventorySnapshot:
    item_id: int
    branch_id: int
    stock: int
    expiry_date: date | None = None
    overstock_flag: bool = False
    perishability_index: int = 1


@dataclass
class MenuItem:
    id: int
    name: str
    price: Price
    category: CategorySlug
    section: str | None = None
    food_type: FoodType | None = None
    serving_type: ServingType | None = None
    meal_role: str | None = None
    meal_size: str | None = None
    short_description: str | None = None
    long_description: str | None = None
    image: str | None = None
    meal_image: str | None = None
    section_order: int | None = 0
    display_order: int | None = 0
    is_meal_available: bool = False
    is_available: bool = True
    inventory: InventorySnapshot | None = None
    velocity_score: float = 0.0
    perishability_index: int = 1
    overstock_flag: bool = False
    tags: list[str] = field(default_factory=list)

    @property
    def in_stock(self) -> bool:
        if self.inventory is not None:
            return self.is_available and self.inventory.stock > 0
        return self.is_available

    @property
    def is_in_stock(self) -> bool:
        return self.in_stock

    @property
    def is_overstock(self) -> bool:
        if self.overstock_flag:
            return True
        if self.inventory and self.inventory.overstock_flag:
            return True
        return False

    @property
    def is_high_perishability(self) -> bool:
        if self.perishability_index >= 4:
            return True
        if self.inventory and self.inventory.perishability_index >= 4:
            return True
        return False

    @property
    def days_to_expiry(self) -> int | None:
        if self.inventory and self.inventory.expiry_date:
            return (self.inventory.expiry_date - date.today()).days
        return None


@dataclass
class CrossSell:
    id: int
    source_item_id: int
    recommended_item_id: int
    priority: int = 1


@dataclass
class MealDefault:
    id: int
    meal_size: str
    default_side_id: int
    default_drink_id: int


@dataclass
class MealUpgradeRule:
    id: int
    item_id: int
    meal_size: str
    extra_price: Price
    is_enabled: bool = True
