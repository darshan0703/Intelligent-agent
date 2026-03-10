from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import MenuItem, Inventory, Branch
from datetime import date

engine = create_engine("postgresql://darshan@localhost/restaurant_ai")
Session = sessionmaker(bind=engine)

BRANCH_ID = 1  # For now, prototype branch

def get_available_menu():
    session = Session()
    items = (
        session.query(MenuItem, Inventory)
        .join(Inventory, MenuItem.id == Inventory.item_id)
        .filter(Inventory.branch_id == BRANCH_ID)
        .filter(MenuItem.is_available == True)
        .filter(Inventory.stock > 0)
        .filter(Inventory.expiry_date >= date.today())
        .all()
    )

    result = [
        {
            "name": item.MenuItem.name,
            "price": float(item.MenuItem.price),
            "stock": item.Inventory.stock,
            "expiry": item.Inventory.expiry_date
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
        return {"success": False, "message": "Item not found."}

    menu_item, inventory = item

    if inventory.stock <= 0:
        session.close()
        return {"success": False, "message": "Item out of stock."}

    inventory.stock -= 1
    session.commit()

    price = float(menu_item.price)

    session.close()

    return {"success": True, "item": menu_item.name, "price": price}