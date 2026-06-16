from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Brand, Branch, MenuItem, Inventory

engine = create_engine("postgresql://darshan@localhost/restaurant_ai")
Session = sessionmaker(bind=engine)
session = Session()

# Create Brand
brand = Brand(name="Demo Burger Brand")
session.add(brand)
session.commit()

# Create Branch
branch = Branch(name="Bangalore Branch", brand_id=brand.id)
session.add(branch)
session.commit()

# Add Menu Items
items = [
    MenuItem(name="Whopper", price=189, brand_id=brand.id),
    MenuItem(name="Whopper Jr", price=129, brand_id=brand.id),
    MenuItem(name="Fries Small", price=79, brand_id=brand.id),
    MenuItem(name="Iced Tea", price=59, brand_id=brand.id),
]

session.add_all(items)
session.commit()

# Add Inventory
for item in items:
    inventory = Inventory(branch_id=branch.id, item_id=item.id, stock=20)
    session.add(inventory)

session.commit()

print("Seed data inserted successfully.")