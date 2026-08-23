from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import MenuItem, Inventory

engine = create_engine(
    "postgresql://darshan@localhost/restaurant_ai"
)

Session = sessionmaker(bind=engine)

BRANCH_ID = 1


# ==========================================================
# COMMON SERIALIZER
# ==========================================================

def serialize_menu_item(menu_item, inventory):
    return {
        "id": menu_item.id,
        "name": menu_item.name,
        "shortDescription": menu_item.short_description,
        "longDescription": menu_item.long_description,
        "price": float(menu_item.price),
        "image": menu_item.image,
        "meal_image": menu_item.meal_image,

        "type": (
            menu_item.serving_type
            if menu_item.category == "drink"
            else menu_item.food_type
        ),

        "foodType": menu_item.food_type,

        # NEW
        "is_meal_available": menu_item.is_meal_available,

        "stock": inventory.stock,
        "expiry": inventory.expiry_date,
        "category": menu_item.category,
    }

# ==========================================================
# MENU SECTIONS
# ==========================================================

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

        sections[menu_item.section]["products"].append(
            serialize_menu_item(menu_item, inventory)
        )

    session.close()

    return list(sections.values())


# ==========================================================
# AVAILABLE ITEMS
# ==========================================================

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
        serialize_menu_item(menu_item, inventory)
        for menu_item, inventory in items
    ]

    session.close()

    return result


# ==========================================================
# CATEGORY ITEMS
# ==========================================================

def get_category(category):

    session = Session()

    query = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .filter(MenuItem.is_available == True)
        .filter(Inventory.stock > 0)
    )

    if category in ["veg", "non_veg"]:
        query = query.filter(MenuItem.food_type.ilike(category))
    else:
        query = query.filter(MenuItem.category.ilike(category))

    items = query.all()

    result = [
        serialize_menu_item(menu_item, inventory)
        for menu_item, inventory in items
    ]

    session.close()

    return result


# ==========================================================
# ADD TO CART
# ==========================================================

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

    session.close()

    return {
        "success": True,
        "item": serialize_menu_item(menu_item, inventory)
    }

def deduct_inventory(item_id, quantity):
    session = Session()

    inventory = (
        session.query(Inventory)
        .filter(Inventory.item_id == item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .first()
    )

    if not inventory:
        session.close()
        return {
            "success": False,
            "message": "Inventory record not found."
        }

    if inventory.stock < quantity:
        session.close()
        return {
            "success": False,
            "message": "Not enough stock."
        }

    inventory.stock -= quantity

    session.commit()

    remaining_stock = inventory.stock

    session.close()

    return {
        "success": True,
        "remaining_stock": remaining_stock
    }

def get_product(item_name):

    session = Session()

    item = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .filter(MenuItem.name.ilike(item_name))
        .filter(MenuItem.is_available == True)
        .first()
    )

    if not item:
        session.close()
        return None

    menu_item, inventory = item

    product = {
        "id": menu_item.id,
        "name": menu_item.name,
        "shortDescription": menu_item.short_description,
        "longDescription": menu_item.long_description,
        "price": float(menu_item.price),
        "image": menu_item.image,
        "type": (
            menu_item.serving_type
            if menu_item.category == "drink"
            else menu_item.food_type
        ),
        "foodType": menu_item.food_type,
        "category": menu_item.category,
        "is_meal_available": menu_item.is_meal_available,
        "stock": inventory.stock,
        "expiry": inventory.expiry_date
    }

    session.close()

    return product
