"""
app/intelligence/agent/tools/catalog_tools.py
Tool implementations for menu catalog querying and recommendations.
"""
from __future__ import annotations
from typing import Any
from app.ports.catalog_port import CatalogRepository
from app.ports.recommendation_port import RecommendationEngine
from app.domain.session.entities import SessionState


class CatalogTools:
    def __init__(self, catalog: CatalogRepository, rec_engine: RecommendationEngine):
        self.catalog = catalog
        self.rec_engine = rec_engine

    async def get_menu_category(self, category: str, branch_id: int = 1) -> dict[str, Any]:
        items = await self.catalog.get_by_category(category, branch_id)
        return {
            "category": category,
            "count": len(items),
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "price": str(item.price.amount),
                    "food_type": str(item.food_type) if item.food_type else None,
                    "in_stock": item.in_stock,
                }
                for item in items
            ],
        }

    async def get_product_details(self, item_name: str, branch_id: int = 1) -> dict[str, Any]:
        matches = await self.catalog.search_by_name(item_name, branch_id)
        if not matches:
            return {"found": False, "message": f"Product '{item_name}' not found."}
        item = matches[0]
        return {
            "found": True,
            "id": item.id,
            "name": item.name,
            "price": str(item.price.amount),
            "category": str(item.category),
            "food_type": str(item.food_type) if item.food_type else None,
            "short_description": item.short_description,
            "in_stock": item.in_stock,
            "is_meal_available": item.is_meal_available,
        }

    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None = None,
        food_type: str | None = None,
        branch_id: int = 1,
    ) -> dict[str, Any]:
        rec_set = await self.rec_engine.get_recommendations(
            session=session,
            category=category,
            food_type=food_type,
            branch_id=branch_id,
        )
        return {
            "priority": [
                {
                    "id": c.item.id,
                    "name": c.item.name,
                    "price": str(c.item.price.amount),
                    "explanation": c.explanation,
                }
                for c in rec_set.priority
            ],
            "premium": [
                {
                    "id": c.item.id,
                    "name": c.item.name,
                    "price": str(c.item.price.amount),
                }
                for c in rec_set.premium
            ],
        }
