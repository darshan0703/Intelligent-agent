import os
import sys
from decimal import Decimal
from datetime import date, timedelta
from dotenv import load_dotenv

# Ensure backend root is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.config.settings import get_settings
from app.infrastructure.db.models import (
    Base,
    Brand,
    Branch,
    MenuItem,
    Inventory,
    CrossSell,
    MealDefault,
    MealUpgradeRule,
)

def seed_database():
    settings = get_settings()
    engine = create_engine(settings.sync_database_url)

    print("Creating tables if they do not exist...")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        # 1. Brand & Branch
        brand = session.execute(select(Brand).where(Brand.name == "Burger King India")).scalar_one_or_none()
        if not brand:
            brand = Brand(name="Burger King India")
            session.add(brand)
            session.flush()
            print(f"Created Brand: {brand.name}")

        branch = session.execute(select(Branch).where(Branch.brand_id == brand.id)).scalar_one_or_none()
        if not branch:
            branch = Branch(name="Burger King - Mumbai Central", brand_id=brand.id)
            session.add(branch)
            session.flush()
            print(f"Created Branch: {branch.name}")

        branch_id = branch.id

        # 2. Menu Items
        menu_data = [
            # Burgers
            {
                "name": "Whopper",
                "short_description": "Our signature flame-grilled beef burger with sesame bun.",
                "long_description": "Flame-grilled patty with fresh lettuce, onions, juicy tomatoes, and creamy mayo.",
                "price": Decimal("179.00"),
                "category": "burger",
                "food_type": "non_veg",
                "section": "Flame-Grilled Burgers",
                "meal_role": "main",
                "is_meal_available": True,
                "stock": 45,
                "days_expiry": 14,
                "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500&auto=format&fit=crop&q=60",
                "meal_image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Whopper Jr.",
                "short_description": "Everything you love about the Whopper, perfectly sized.",
                "long_description": "A smaller flame-grilled patty served with fresh lettuce, tomatoes, and mayo.",
                "price": Decimal("119.00"),
                "category": "burger",
                "food_type": "non_veg",
                "section": "Flame-Grilled Burgers",
                "meal_role": "main",
                "is_meal_available": True,
                "stock": 60,
                "days_expiry": 14,
                "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=500&auto=format&fit=crop&q=60",
                "meal_image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Whopper Deluxe",
                "short_description": "Double patty, melted cheese, and smoky bacon sauce.",
                "long_description": "Two flame-grilled patties, double cheese slices, crispy lettuce, pickles, and signature sauces.",
                "price": Decimal("249.00"),
                "category": "burger",
                "food_type": "non_veg",
                "section": "Premium Whoppers",
                "meal_role": "main",
                "is_meal_available": True,
                "stock": 25,
                "days_expiry": 10,
                "image": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=500&auto=format&fit=crop&q=60",
                "meal_image": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Crispy Chicken Burger",
                "short_description": "Golden crispy chicken patty with tangy mayo in a toasted bun.",
                "long_description": "Tender chicken breast coated in seasoned crispy batter with garden fresh lettuce.",
                "price": Decimal("139.00"),
                "category": "burger",
                "food_type": "non_veg",
                "section": "Crispy Selection",
                "meal_role": "main",
                "is_meal_available": True,
                "stock": 50,
                "days_expiry": 12,
                "image": "https://images.unsplash.com/photo-1625813506062-0aeb1d7a094b?w=500&auto=format&fit=crop&q=60",
                "meal_image": "https://images.unsplash.com/photo-1625813506062-0aeb1d7a094b?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Veg Whopper",
                "short_description": "Crunchy herb patty loaded with veggies and creamy sauce.",
                "long_description": "A wholesome vegetarian patty made from farm-fresh greens and potatoes, grilled to perfection.",
                "price": Decimal("159.00"),
                "category": "burger",
                "food_type": "veg",
                "section": "Flame-Grilled Burgers",
                "meal_role": "main",
                "is_meal_available": True,
                "stock": 40,
                "days_expiry": 15,
                "image": "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500&auto=format&fit=crop&q=60",
                "meal_image": "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500&auto=format&fit=crop&q=60",
            },
            # Sides
            {
                "name": "Classic Fries",
                "short_description": "Crispy golden french fries sprinkled with sea salt.",
                "long_description": "Freshly cut potatoes fried to golden perfection, crispy outside and fluffy inside.",
                "price": Decimal("89.00"),
                "category": "side",
                "food_type": "veg",
                "section": "Fries & Sides",
                "meal_role": "side",
                "is_meal_available": False,
                "stock": 100,
                "days_expiry": 30,
                "image": "https://images.unsplash.com/photo-1576107232684-1279f3908594?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "King Peri Peri Fries",
                "short_description": "Golden fries tossed with spicy African peri peri seasoning.",
                "long_description": "Our signature fries served with a fiery peri peri seasoning pouch for custom shaking.",
                "price": Decimal("109.00"),
                "category": "side",
                "food_type": "veg",
                "section": "Fries & Sides",
                "meal_role": "side",
                "is_meal_available": False,
                "stock": 80,
                "days_expiry": 30,
                "image": "https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Onion Rings",
                "short_description": "Crispy battered onion rings fried until crunchy.",
                "long_description": "Sweet whole onion slices in crunchy batter with herbs.",
                "price": Decimal("99.00"),
                "category": "side",
                "food_type": "veg",
                "section": "Fries & Sides",
                "meal_role": "side",
                "is_meal_available": False,
                "stock": 50,
                "days_expiry": 20,
                "image": "https://images.unsplash.com/photo-1639024471287-032f6670a3c2?w=500&auto=format&fit=crop&q=60",
            },
            # Drinks
            {
                "name": "Coke",
                "short_description": "Chilled, bubbly Coca-Cola served with ice.",
                "long_description": "Classic fountain Coca-Cola, perfectly carbonated and refreshing.",
                "price": Decimal("69.00"),
                "category": "drink",
                "serving_type": "cold",
                "section": "Beverages",
                "meal_role": "drink",
                "is_meal_available": False,
                "stock": 200,
                "days_expiry": 60,
                "image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Cold Coffee",
                "short_description": "Rich creamy iced coffee blended with milk.",
                "long_description": "Freshly brewed espresso shaken with chilled milk and sweetened vanilla syrup.",
                "price": Decimal("99.00"),
                "category": "drink",
                "serving_type": "cold",
                "section": "Beverages",
                "meal_role": "drink",
                "is_meal_available": False,
                "stock": 40,
                "days_expiry": 7,
                "image": "https://images.unsplash.com/photo-1517701604599-bb29b565090c?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "Café Latte",
                "short_description": "Hot velvety espresso with steamed milk froth.",
                "long_description": "Espresso roast topped with silky microfoam milk.",
                "price": Decimal("109.00"),
                "category": "drink",
                "serving_type": "hot",
                "section": "Hot Beverages",
                "meal_role": "drink",
                "is_meal_available": False,
                "stock": 35,
                "days_expiry": 14,
                "image": "https://images.unsplash.com/photo-1570968915860-54d5c301fa9f?w=500&auto=format&fit=crop&q=60",
            },
            # Desserts
            {
                "name": "Chocolate Sundae",
                "short_description": "Creamy soft serve drizzled with warm chocolate fudge.",
                "long_description": "Velvety vanilla soft serve topped with rich Belgian chocolate drizzle.",
                "price": Decimal("79.00"),
                "category": "dessert",
                "food_type": "veg",
                "section": "Sundaes",
                "is_meal_available": False,
                "stock": 40,
                "days_expiry": 10,
                "image": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=500&auto=format&fit=crop&q=60",
            },
            {
                "name": "BK Fusion Sundae",
                "short_description": "Soft serve swirled with crushed Oreo biscuits.",
                "long_description": "Thick soft serve blended with crunchy chocolate cookies and sweet sauce.",
                "price": Decimal("99.00"),
                "category": "dessert",
                "food_type": "veg",
                "section": "Sundaes",
                "is_meal_available": False,
                "stock": 30,
                "days_expiry": 10,
                "image": "https://images.unsplash.com/photo-1579954115545-a95591f28bfc?w=500&auto=format&fit=crop&q=60",
            },
        ]

        items_by_name = {}
        for data in menu_data:
            existing = session.execute(select(MenuItem).where(MenuItem.name == data["name"])).scalar_one_or_none()
            if not existing:
                item = MenuItem(
                    name=data["name"],
                    short_description=data.get("short_description"),
                    long_description=data.get("long_description"),
                    price=data["price"],
                    category=data["category"],
                    food_type=data.get("food_type"),
                    serving_type=data.get("serving_type"),
                    section=data.get("section"),
                    meal_role=data.get("meal_role"),
                    is_meal_available=data.get("is_meal_available", False),
                    is_available=True,
                    image=data.get("image"),
                    meal_image=data.get("meal_image"),
                )
                session.add(item)
                session.flush()
                items_by_name[item.name] = item

                inv = Inventory(
                    branch_id=branch_id,
                    item_id=item.id,
                    stock=data["stock"],
                    expiry_date=date.today() + timedelta(days=data["days_expiry"]),
                )
                session.add(inv)
                print(f"Seeded: {item.name} (ID: {item.id}, Stock: {inv.stock})")
            else:
                items_by_name[existing.name] = existing

        # 3. Meal Defaults
        fries = items_by_name.get("Classic Fries")
        coke = items_by_name.get("Coke")
        peri_peri = items_by_name.get("King Peri Peri Fries")

        if fries and coke:
            existing_med = session.execute(select(MealDefault).where(MealDefault.meal_size == "medium")).scalar_one_or_none()
            if not existing_med:
                session.add(MealDefault(meal_size="medium", default_side_id=fries.id, default_drink_id=coke.id))
            existing_lrg = session.execute(select(MealDefault).where(MealDefault.meal_size == "large")).scalar_one_or_none()
            if not existing_lrg:
                session.add(MealDefault(meal_size="large", default_side_id=peri_peri.id if peri_peri else fries.id, default_drink_id=coke.id))

        # 4. Meal Upgrade Rules for burgers
        for name, item in items_by_name.items():
            if item.is_meal_available:
                rule_med = session.execute(
                    select(MealUpgradeRule).where(MealUpgradeRule.item_id == item.id, MealUpgradeRule.meal_size == "medium")
                ).scalar_one_or_none()
                if not rule_med:
                    session.add(MealUpgradeRule(item_id=item.id, meal_size="medium", extra_price=Decimal("120.00")))

                rule_lrg = session.execute(
                    select(MealUpgradeRule).where(MealUpgradeRule.item_id == item.id, MealUpgradeRule.meal_size == "large")
                ).scalar_one_or_none()
                if not rule_lrg:
                    session.add(MealUpgradeRule(item_id=item.id, meal_size="large", extra_price=Decimal("150.00")))

        # 5. Cross Sells
        whopper = items_by_name.get("Whopper")
        if whopper and fries and coke:
            session.add(CrossSell(source_item_id=whopper.id, recommended_item_id=fries.id, priority=1))
            session.add(CrossSell(source_item_id=whopper.id, recommended_item_id=coke.id, priority=2))

        session.commit()
        print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
