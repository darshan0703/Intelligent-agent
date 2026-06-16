CATEGORY_ALIASES = {
    "burger": "burger",
    "burgers": "burger",
    "whopper": "burger",
    "sandwich": "burger",

    "drink": "beverage",
    "drinks": "beverage",
    "beverage": "beverage",
    "beverages": "beverage",
    "coffee": "beverage",
    "tea": "beverage",
    "juice": "beverage",
    "cola": "beverage",
    "shake": "beverage",

    "dessert": "dessert",
    "desserts": "dessert",
    "sundae": "dessert",
    "ice cream": "dessert",
    "brownie": "dessert",
    "choco": "dessert",
    "vanilla": "dessert",

    "side": "side",
    "sides": "side",
    "fries": "side",
    "nuggets": "side",
    "rings": "side"
}


def infer_category_from_text(text):
    text = text.lower()

    for word, category in CATEGORY_ALIASES.items():
        if word in text:
            return category

    return None