from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import MenuItem, Inventory
from burgers import burgerSections
from drinks import drinkSections
from desserts import dessertSections
from sides import sideSections

engine = create_engine("postgresql://darshan@localhost/restaurant_ai")
Session = sessionmaker(bind=engine)
session = Session()

BRANCH_ID = 1


def normalize_food_type(food_type):
    if not food_type:
        return "veg"
    ft = str(food_type).lower()
    if ft in ["nonveg", "non veg", "non_veg"]:
        return "non veg"
    return "veg"


def get_meal_role(name, category):
    if category == "burger":
        return "main"
    if name in ["Fries (Medium)", "Fries (King)"]:
        return "side"
    if name in [
        "Coca Cola (Medium)", "Coca Cola (Large)",
        "Sprite (Medium)", "Sprite (Large)",
        "Fanta (Medium)", "Fanta (Large)",
        "Thums Up (Medium)", "Thums Up (Large)",
    ]:
        return "drink"
    return None

def get_meal_size(name):
    if "(Medium)" in name:
        return "medium"

    if "(Large)" in name:
        return "large"

    if "(King)" in name:
        return "large"

    return None

def import_category(sections, category):
    section_order = 1
    for section in sections:
        display_order = 1
        print(f"Importing {category} -> {section['title']}")
        for product in section["products"]:
            item = MenuItem(
                name=product["name"],
                short_description=product["shortDescription"],
                long_description=product["longDescription"],
                price=product["price"],
                image=product["image"],
                category=category,
                section=section["title"],
                food_type=normalize_food_type(product.get("foodType", product.get("food_type", product.get("type")))),
                serving_type=product.get("type"),
                meal_role=get_meal_role(product["name"], category),
                meal_size=get_meal_size(product["name"]),
                section_order=section_order,
                display_order=display_order,
                is_meal_available=(category == "burger"),
                is_available=True,
                is_meal_only=False,
            )
            print("OBJECT:", item.name, item.food_type)

            session.add(item)
            session.flush()
            session.add(
                Inventory(
                    branch_id=BRANCH_ID,
                    item_id=item.id,
                    stock=20,
                    expiry_date=date(2026,12,31),
                )
            )
            display_order += 1
        section_order += 1


if __name__ == "__main__":
    session.query(Inventory).delete()
    session.query(MenuItem).delete()
    session.commit()

    import_category(burgerSections, "burger")
    import_category(drinkSections, "drink")
    import_category(dessertSections, "dessert")
    import_category(sideSections, "side")

    session.commit()
    session.close()

    print("Complete menu imported successfully.")
