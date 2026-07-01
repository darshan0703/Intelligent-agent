from datetime import datetime
from langchain.tools import tool
from services.menu_service import (
    get_menu,
    get_available,
    get_category,
    add_item
)
@tool
def fetch_menu():
    """Fetch available menu items"""
    return get_available()

@tool
def add_item_to_cart(item_name: str):
     """
    Add an item to the customer's cart using the exact menu item name.
    Returns success status and item price.
    """
     return add_to_cart(item_name)