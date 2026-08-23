from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Inventory


engine = create_engine(
    "postgresql://darshan@localhost/restaurant_ai"
)

Session = sessionmaker(bind=engine)

BRANCH_ID = 1

def complete_order(cart):
    session = Session()

    try:
        requirements = []

        for item in cart:
            quantity = item["quantity"]

            if item["type"] == "meal":
                requirements.append(
                    (item["main_item"]["id"], quantity)
                )
                requirements.append(
                    (item["side"]["id"], quantity)
                )
                requirements.append(
                    (item["drink"]["id"], quantity)
                )
            else:
                requirements.append(
                    (item["id"], quantity)
                )

        # Check all inventory first
        for item_id, quantity in requirements:
            inventory = (
                session.query(Inventory)
                .filter(Inventory.item_id == item_id)
                .filter(Inventory.branch_id == BRANCH_ID)
                .first()
            )

            if not inventory:
                raise ValueError(
                    f"Inventory not found for item {item_id}."
                )

            if inventory.stock < quantity:
                raise ValueError(
                    f"Not enough stock for item {item_id}."
                )

        # Deduct only after every check passes
        for item_id, quantity in requirements:
            inventory = (
                session.query(Inventory)
                .filter(Inventory.item_id == item_id)
                .filter(Inventory.branch_id == BRANCH_ID)
                .first()
            )

            inventory.stock -= quantity

        session.commit()

        return {
            "success": True,
            "message": "Order completed successfully."
        }

    except Exception as e:
        session.rollback()

        return {
            "success": False,
            "message": str(e)
        }

    finally:
        session.close()