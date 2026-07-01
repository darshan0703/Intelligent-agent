from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import MenuItem, Inventory

from burgers import burgerSections
from drinks import drinkSections
from desserts import dessertSections
from sides import sidesSections

engine = create_engine(
    "postgresql://darshan@localhost/restaurant_ai"
)

Session = sessionmaker(bind=engine)
session = Session()


def normalize_food_type(food_type):

    if not food_type:
        return "veg"

    food_type = food_type.lower()

    if food_type in ["nonveg", "non veg", "non_veg"]:
        return "non veg"

    return "veg"


def import_category(sections, category):

    section_order = 1

    for section in sections:

        display_order = 1

        print(f"\nImporting {category} -> {section['title']}")

        for product in section["products"]:

            existing = (
                session.query(MenuItem)
                .filter_by(name=product["name"])
                .first()
            )

            if existing:

                print(f"Skipping {product['name']}")
                continue

            item = MenuItem(

                name=product["name"],

                short_description=product["shortDescription"],

                long_description=product["longDescription"],

                price=product["price"],

                image=product["image"],

                category=category,

                section=section["title"],

                food_type=normalize_food_type(
                    product.get(
                        "food_type",
                        product.get("type")
                    )
                ),

                serving_type=product.get("type"),

                display_order=display_order,

                section_order=section_order,

                is_meal_available=(
                    category == "burger"
                ),

                is_available=True

            )

            session.add(item)

            session.flush()

            inventory = Inventory(

                branch_id=1,

                item_id=item.id,

                stock=20,

                expiry_date=date(2026, 12, 31)

            )

            session.add(inventory)

            session.commit()

            print(f"✓ Added {item.name}")

            display_order += 1

        section_order += 1


if __name__ == "__main__":

    print("\n========== IMPORTING MENU ==========")

    import_category(
        burgerSections,
        "burger"
    )

    import_category(
        drinkSections,
        "drink"
    )

    import_category(
        dessertSections,    
        "dessert"
    )

    import_category(
        sidesSections,
        "side"
    )

    session.close()

    print("\n✅ Complete menu imported successfully.")