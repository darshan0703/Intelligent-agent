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
    name = Column(String, nullable=False)
    price = Column(Numeric, nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    is_available = Column(Boolean, default=True)
    category = Column(String)


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    stock = Column(Integer, nullable=False)
    expiry_date = Column(Date)