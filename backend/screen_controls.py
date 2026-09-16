from schemas import ScreenTypes


SCREEN_CONTROLS = {

    # ==========================================
    # RECOMMENDED BURGERS
    # ==========================================

    ScreenTypes.RECOMMENDED_BURGERS: [
        "filter",
        "view_more",
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # RECOMMENDED DRINKS
    # ==========================================

    ScreenTypes.RECOMMENDED_DRINKS: [
        "view_more",
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # RECOMMENDED SIDES
    # ==========================================

    ScreenTypes.RECOMMENDED_SIDES: [
        "view_more",
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # RECOMMENDED DESSERTS
    # ==========================================

    ScreenTypes.RECOMMENDED_DESSERTS: [
        "view_more",
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # FULL BURGER MENU
    # ==========================================

    ScreenTypes.FULL_BURGER_MENU: [
        "filter",
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # FULL DRINK MENU
    # ==========================================

    ScreenTypes.FULL_DRINK_MENU: [
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # FULL SIDE MENU
    # ==========================================

    ScreenTypes.FULL_SIDE_MENU: [
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # FULL DESSERT MENU
    # ==========================================

    ScreenTypes.FULL_DESSERT_MENU: [
        "open_cart",
        "select_product",
        "go_back",
    ],


    # ==========================================
    # PRODUCT DETAILS
    # ==========================================

    ScreenTypes.PRODUCT_DETAILS: [
        "add_to_cart",
        "open_cart",
        "go_back",
    ],


    # ==========================================
    # MEAL CONVERSION
    # ==========================================

    ScreenTypes.MEAL_CONVERSION: [
        "accept_meal",
        "decline_meal",
        "go_back",
    ],


    # ==========================================
    # CART
    # ==========================================

    ScreenTypes.CART: [
        "increase_quantity",
        "decrease_quantity",
        "remove_item",
        "checkout",
        "go_back",
    ],

    ScreenTypes.CATEGORY_SELECTION: [
    "open_cart",
    ]
}


def get_screen_controls(screen):
    return SCREEN_CONTROLS.get(screen, [])