from repositories.menu_repository import (
    get_menu_sections,
    get_available as repo_get_available,
    get_category as repo_get_category,
    add_to_cart
)


def get_menu(category):
    return get_menu_sections(category)

def get_available():
    return repo_get_available()

def get_category(category):
    return repo_get_category(category)

def add_item(item_name):
    return add_to_cart(item_name)