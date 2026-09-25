"""
app/ports/catalog_port.py
Repository protocol for accessing menu catalog and inventory data.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.catalog.entities import MenuItem

@runtime_checkable
class CatalogRepository(Protocol):
    async def get_by_category(self, category: str, branch_id: int) -> list[MenuItem]:
        ...

    async def get_all_available(self, branch_id: int) -> list[MenuItem]:
        ...

    async def get_by_id(self, item_id: int, branch_id: int) -> MenuItem | None:
        ...

    async def get_live_stock(self, item_id: int, branch_id: int = 1) -> int:
        ...

    async def search_by_name(self, name: str, branch_id: int) -> list[MenuItem]:
        ...

    async def get_cross_sells(self, item_id: int, limit: int = 4) -> list[MenuItem]:
        ...

    async def get_meal_options(self, item_id: int) -> dict | None:
        ...

    async def get_sections(self, category: str, branch_id: int) -> list[dict]:
        ...
