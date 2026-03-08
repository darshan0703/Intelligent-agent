from datetime import datetime
from langchain.tools import tool
from db_service import get_available_menu, add_to_cart
from langchain_community.tools import DuckDuckGoSearchRun

@tool
def fetch_menu():
    """Fetch available menu items"""
    return get_available_menu()

@tool
def add_item_to_cart(item_name: str):
     """
    Add an item to the customer's cart using the exact menu item name.
    Returns success status and item price.
    """
     return add_to_cart(item_name)