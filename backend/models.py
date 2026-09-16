from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, Numeric,Date
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True)

    # Basic Information
    name = Column(String, nullable=False)
    short_description = Column(String)
    long_description = Column(String)

    # Pricing
    price = Column(Numeric, nullable=False)

    # Display
    image = Column(String)

    # Classification
    category = Column(String, nullable=False)
    section = Column(String)          
    food_type = Column(String)
    serving_type = Column(String)
    meal_role = Column(String)
    meal_size = Column(String)

    # Ordering
    section_order = Column(Integer)
    display_order = Column(Integer)   

    # Business Logic
    is_meal_available = Column(Boolean, default=False)
    is_available = Column(Boolean, default=True)

    image = Column(String)
    meal_image = Column(String)

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    stock = Column(Integer, nullable=False)
    expiry_date = Column(Date)

class CrossSell(Base):
    __tablename__ = "cross_sell"

    id = Column(Integer, primary_key=True)

    source_item_id = Column(
        Integer,
        ForeignKey("menu_items.id"),
        nullable=False
     )

    recommended_item_id = Column(
        Integer,
        ForeignKey("menu_items.id"),
        nullable=False
     )

    priority = Column(Integer, default=1)

class MealDefault(Base):
    __tablename__ = "meal_defaults"

    id = Column(Integer, primary_key=True)

    meal_size = Column(
        String,
        nullable=False,
        unique=True
    )

    default_side_id = Column(
        Integer,
        ForeignKey("menu_items.id"),
        nullable=False
    )

    default_drink_id = Column(
        Integer,
        ForeignKey("menu_items.id"),
        nullable=False
    )


class MealUpgradeRule(Base):
    __tablename__ = "meal_upgrade_rules"

    id = Column(Integer, primary_key=True)

    item_id = Column(
        Integer,
        ForeignKey("menu_items.id"),
        nullable=False
    )

    meal_size = Column(
        String,
        nullable=False
    )

    extra_price = Column(
        Numeric,
        nullable=False
    )

    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True
    )