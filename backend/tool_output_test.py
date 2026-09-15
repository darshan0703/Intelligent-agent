from unicodedata import category

from tools.restaurant_tools import (
    search_menu,
    get_menu_item_details,
    get_recommendations,
)

print("=== search_menu ===")
result = search_menu.invoke({
    "category": "burger"
})
print(result)

print("\n=== get_menu_item_details ===")
result = get_menu_item_details.invoke({
    "item_name": "Veg Whopper"
})
print(result)

print("\n=== get_recommendations ===")
result = get_recommendations.invoke({
    "category": "burger",
    "food_type": "veg"
})
print(result)



 