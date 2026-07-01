from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import MenuItem

from burgers import burgerSections
from drinks import drinkSections
from sides import sidesSections
from desserts import dessertSections


engine = create_engine(
    "postgresql://darshan@localhost/restaurant_ai"
)

Session = sessionmaker(bind=engine)

session = Session()

def migrate_category(menu_sections, category):

    print(f"\nMigrating {category}...")

    for section_order, section in enumerate(menu_sections, start=1):

        display_order = 1

        for product in section["products"]:

            item = (
                session.query(MenuItem)
                .filter_by(name=product["name"])
                .first()
            )

            if not item:
                print(f"❌ {product['name']} not found")
                continue

            item.category = category
            item.section = section["title"]
            item.section_order = section_order
            item.display_order = display_order

            if "foodType" in product:
                item.food_type = product["foodType"]
            elif "food_type" in product:
                item.food_type = product["food_type"]
            else:
                item.food_type = product["type"]

            display_order += 1

            print(f"✓ Updated {item.name}")

    session.commit()

if __name__ == "__main__":

    print("\n========== MIGRATING MENU ==========")

    migrate_category(
        burgerSections,
        "burger"
    )

    migrate_category(
        drinkSections,
        "drink"
    )

    migrate_category(
        sidesSections,
        "side"
    )

    migrate_category(
        dessertSections,
        "dessert"
    )

    session.close()

    print("\n✅ Menu migration completed.")