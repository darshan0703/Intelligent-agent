from pydantic import BaseModel
from typing import Optional, Dict, Any


# ==========================
# USER → BACKEND
# ==========================

class OrderIntent(BaseModel):
    action: str
    item_name: Optional[str] = None
    category: Optional[str] = None
    food_type: Optional[str] = None
    quantity: Optional[int] = 1


# ==========================
# BACKEND → FRONTEND
# ==========================

class KioskResponse(BaseModel):
    screen: str
    message: Optional[str] = None
    data: Dict[str, Any] = {}


# ==========================
# COMMON SCREEN TYPES
# ==========================

class ScreenTypes:

    # Startup
    HOME = "home"

    # Clarification
    BURGER_TYPE_SELECTION = "burger_type_selection"

    # Recommended category screens
    RECOMMENDED_BURGERS = "recommended_burgers"
    RECOMMENDED_DRINKS = "recommended_drinks"
    RECOMMENDED_SIDES = "recommended_sides"
    RECOMMENDED_DESSERTS = "recommended_desserts"

    # Full category menus
    FULL_BURGER_MENU = "full_burger_menu"
    FULL_DRINK_MENU = "full_drink_menu"
    FULL_SIDE_MENU = "full_side_menu"
    FULL_DESSERT_MENU = "full_dessert_menu"

    # Product screen
    PRODUCT_DETAILS = "product_details"

    # Order flow
    UPSELL = "upsell"
    CART = "cart"
    CHECKOUT = "checkout"
    PAYMENT = "payment"

    # Completion
    ORDER_COMPLETE = "order_complete"

    HOME = "home"

    BURGER_TYPE_SELECTION = "burger_type_selection"

    BURGER_MENU = "burger_menu"

    DRINK_MENU = "drink_menu"

    SIDE_MENU = "side_menu"

    DESSERT_MENU = "dessert_menu"

    PRODUCT_DETAILS = "product_details"

    CART = "cart"

    UPSELL = "upsell"

    CHECKOUT = "checkout"

    PAYMENT = "payment"

    ORDER_COMPLETE = "order_complete"