from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import MenuItem, Inventory

engine = create_engine(
    "postgresql://darshan@localhost/restaurant_ai"
)

Session = sessionmaker(bind=engine)

BRANCH_ID = 1


def get_menu_sections(category):

    session = Session()

    items = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .filter(MenuItem.category == category)
        .filter(MenuItem.is_available == True)
        .filter(Inventory.stock > 0)
        .order_by(
            MenuItem.section_order,
            MenuItem.display_order
        )
        .all()
    )

    sections = {}

    for menu_item, inventory in items:

        if menu_item.section not in sections:
            sections[menu_item.section] = {
                "id": menu_item.section.lower().replace(" ", "-"),
                "title": menu_item.section,
                "products": []
            }

        sections[menu_item.section]["products"].append({

            "id": menu_item.id,
            "name": menu_item.name,
            "shortDescription": menu_item.short_description,
            "longDescription": menu_item.long_description,
            "price": float(menu_item.price),
            "image": menu_item.image,
            "type": (
              menu_item.serving_type
              if category == "drink"
             else menu_item.food_type
            ),

            "foodType": menu_item.food_type,

        })

    session.close()

    return list(sections.values())

def get_available():

    session = Session()

    items = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .filter(MenuItem.is_available == True)
        .filter(Inventory.stock > 0)
        .all()
    )

    result = [
        {
            "name": item.MenuItem.name,
            "price": float(item.MenuItem.price),
            "stock": item.Inventory.stock,
            "expiry": item.Inventory.expiry_date,
            "category": item.MenuItem.category,
            "food_type": item.MenuItem.food_type
        }
        for item in items
    ]

    session.close()

    return result

def get_category(category):

    session = Session()

    query = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .filter(Inventory.stock > 0)
    )

    if category in ["veg", "non_veg"]:
        query = query.filter(MenuItem.food_type.ilike(category))
    else:
        query = query.filter(MenuItem.category.ilike(category))

    items = query.all()

    result = [
        {
            "name": item.MenuItem.name,
            "price": float(item.MenuItem.price),
            "stock": item.Inventory.stock,
            "expiry": item.Inventory.expiry_date,
            "category": item.MenuItem.category,
            "food_type": item.MenuItem.food_type
        }
        for item in items
    ]

    session.close()

    return result

def add_to_cart(item_name):

    session = Session()

    item = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(MenuItem.name.ilike(item_name))
        .filter(Inventory.branch_id == BRANCH_ID)
        .first()
    )

    if not item:
        session.close()
        return {
            "success": False,
            "message": "Item not found."
        }

    menu_item, inventory = item

    if inventory.stock <= 0:
        session.close()
        return {
            "success": False,
            "message": "Item out of stock."
        }

    # ❌ Don't deduct inventory here.
    # Inventory will only be updated during checkout.

    price = float(menu_item.price)

    session.close()

    return {
        "success": True,
        "item": menu_item.name,
        "price": price
    }
