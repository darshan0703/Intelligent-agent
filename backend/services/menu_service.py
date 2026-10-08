from repositories.menu_repository import (
    get_menu_sections,
    get_available as repo_get_available,
    get_category as repo_get_category,
    add_to_cart,
    get_product as repo_get_product
)
from services.meal_service import get_meal_options

def get_menu(category, preference=None, cart=None):
    from state import conversation_context
    from services.menu_organizer import organize_menu_sections

    if cart is None:
        cart = conversation_context.get("cart", [])
    if preference is None:
        preference = conversation_context.get("food_preference")

    raw_sections = get_menu_sections(category, preference=preference)
    return organize_menu_sections(category, raw_sections, preference=preference, cart=cart)

def get_available():
    return repo_get_available()

def get_category(category):
    return repo_get_category(category)

def add_item(item_name):
    return add_to_cart(item_name)

def get_product(item_name):
    return repo_get_product(item_name)

