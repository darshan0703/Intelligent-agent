"""
app/api/v1/catalog.py
Menu items, category browsing, and meal upgrade options.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])
_catalog_repo = SQLAlchemyCatalogRepository()


@router.get("/menu/{category}")
async def get_category_items(category: str, branch_id: int = 1):
    items = await _catalog_repo.get_by_category(category, branch_id)
    return {
        "category": category,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "shortDescription": item.short_description,
                "longDescription": item.long_description,
                "price": float(item.price.amount),
                "foodType": str(item.food_type) if item.food_type else None,
                "servingType": str(item.serving_type) if item.serving_type else None,
                "image": item.image,
                "meal_image": item.meal_image,
                "is_meal_available": item.is_meal_available,
                "stock": item.inventory.stock if item.inventory else 0,
            }
            for item in items
        ],
    }


@router.get("/sections/{category}")
async def get_category_sections(category: str, branch_id: int = 1):
    return await _catalog_repo.get_sections(category, branch_id)


@router.get("/product/{item_id}")
async def get_product(item_id: int, branch_id: int = 1):
    item = await _catalog_repo.get_by_id(item_id, branch_id)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": item.id,
        "name": item.name,
        "price": float(item.price.amount),
        "category": str(item.category),
        "foodType": str(item.food_type) if item.food_type else None,
        "shortDescription": item.short_description,
        "longDescription": item.long_description,
        "image": item.image,
        "meal_image": item.meal_image,
        "is_meal_available": item.is_meal_available,
        "stock": item.inventory.stock if item.inventory else 0,
    }


@router.get("/meal/{item_id}/options")
async def get_meal_options(item_id: int):
    options = await _catalog_repo.get_meal_options(item_id)
    if not options:
        return {"success": False, "is_meal_available": False, "message": "Meal options not available"}
    return {"success": True, **options}
