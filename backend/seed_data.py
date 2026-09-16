from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Brand, Branch

engine = create_engine("postgresql://darshan@localhost/restaurant_ai")

Session = sessionmaker(bind=engine)
session = Session()

# Prevent duplicate data
brand = session.query(Brand).filter_by(name="Burger King").first()

if not brand:
    brand = Brand(name="Burger King")
    session.add(brand)
    session.commit()

branch = session.query(Branch).filter_by(name="Bangalore Branch").first()

if not branch:
    branch = Branch(
        name="Bangalore Branch",
        brand_id=brand.id
    )
    session.add(branch)
    session.commit()

print("✅ Brand and Branch created successfully.")

session.close()