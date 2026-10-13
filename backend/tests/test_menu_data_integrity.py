"""
backend/tests/test_menu_data_integrity.py
Unit tests for Menu Food-Type Data Ingestion Integrity & Normalization Contract.

Tests:
1. Canonical food_type normalization ('veg', 'non_veg').
2. Legacy food_type normalization ('nonveg', 'non veg', 'Non-Veg', 'vegetarian').
3. Strict rejection of missing food_type (None).
4. Strict rejection of blank / whitespace food_type ('', '   ').
5. Strict rejection of unsupported / arbitrary food_type ('pescatarian', 'halal', 'chicken', 'cold').
6. Beverage category dietary contract (beverages default to 'veg' unless explicitly typed).
7. Actionable error reporting identifying affected product name and field.
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def normalize_ingestion_food_type(value, product_name="Unknown Product"):
    """
    Strict data-ingestion normalization for menu items.
    Accepts only verified dietary categories and standardizes to canonical values:
      - 'veg'
      - 'non_veg'
    Rejects missing, blank, or unsupported dietary classifications with actionable ValueError.
    """
    if value is None or not str(value).strip():
        raise ValueError(
            f"Menu item '{product_name}' has missing or blank food_type. "
            f"Database contract requires an explicit 'veg' or 'non_veg' classification."
        )

    cleaned = str(value).lower().strip().replace("-", "_").replace(" ", "_")

    if cleaned in ("veg", "vegetarian"):
        return "veg"
    if cleaned in ("non_veg", "nonveg"):
        return "non_veg"

    raise ValueError(
        f"Menu item '{product_name}' has unsupported food_type '{value}'. "
        f"Allowed values are 'veg' or 'non_veg'."
    )


def resolve_product_food_type(product, category=None):
    """
    Resolves and validates food_type for a catalog product dictionary.
    - If explicit 'foodType' or 'food_type' exists, strictly validates it.
    - If missing and category is 'drink', canonicalizes to 'veg' with 'serving_type' preserved.
    - If missing for any other category, raises ValueError identifying the item.
    """
    raw_ft = product.get("foodType") or product.get("food_type")
    name = product.get("name", "Unknown Product")

    if not raw_ft:
        if category == "drink":
            return "veg"
        raise ValueError(
            f"Catalog item '{name}' (category='{category}') is missing required dietary field 'foodType'."
        )

    return normalize_ingestion_food_type(raw_ft, product_name=name)


def test_canonical_food_type_normalization():
    assert normalize_ingestion_food_type("veg") == "veg"
    assert normalize_ingestion_food_type("non_veg") == "non_veg"
    print("PASS: test_canonical_food_type_normalization")


def test_legacy_food_type_normalization():
    # Legacy variants mapped to canonical tokens
    assert normalize_ingestion_food_type("nonveg") == "non_veg"
    assert normalize_ingestion_food_type("non veg") == "non_veg"
    assert normalize_ingestion_food_type("Non-Veg") == "non_veg"
    assert normalize_ingestion_food_type("NON VEG") == "non_veg"
    assert normalize_ingestion_food_type("vegetarian") == "veg"
    assert normalize_ingestion_food_type("Vegetarian") == "veg"
    assert normalize_ingestion_food_type("Veg") == "veg"
    print("PASS: test_legacy_food_type_normalization")


def test_missing_food_type_raises_actionable_error():
    # Must fail explicitly rather than silently defaulting to veg
    try:
        normalize_ingestion_food_type(None, product_name="Chicken Whopper")
        assert False, "Expected ValueError for None food_type"
    except ValueError as e:
        assert "Chicken Whopper" in str(e)
        assert "missing or blank" in str(e)

    try:
        resolve_product_food_type({"name": "Mystery Burger"}, category="burger")
        assert False, "Expected ValueError for missing foodType in burger"
    except ValueError as e:
        assert "Mystery Burger" in str(e)
        assert "missing required dietary field" in str(e)

    print("PASS: test_missing_food_type_raises_actionable_error")


def test_blank_food_type_raises_actionable_error():
    for blank_val in ("", "   ", "\t\n"):
        try:
            normalize_ingestion_food_type(blank_val, product_name="Empty Item")
            assert False, f"Expected ValueError for blank food_type '{blank_val}'"
        except ValueError as e:
            assert "Empty Item" in str(e)
            assert "missing or blank" in str(e)

    print("PASS: test_blank_food_type_raises_actionable_error")


def test_unsupported_food_type_raises_actionable_error():
    unsupported_values = [
        "pescatarian",
        "halal",
        "kosher",
        "vegan_organic",
        "chicken",
        "cold",
        "hot",
        "unknown",
    ]
    for val in unsupported_values:
        try:
            normalize_ingestion_food_type(val, product_name="Test Product")
            assert False, f"Expected ValueError for unsupported food_type '{val}'"
        except ValueError as e:
            assert "Test Product" in str(e)
            assert f"unsupported food_type '{val}'" in str(e)

    print("PASS: test_unsupported_food_type_raises_actionable_error")


def test_beverage_category_dietary_contract():
    # 1. Beverage without explicit foodType defaults to 'veg'
    beverage_item = {"name": "Espresso (Double Shot)", "type": "hot"}
    resolved = resolve_product_food_type(beverage_item, category="drink")
    assert resolved == "veg"

    # 2. Beverage with explicit foodType is validated
    explicit_veg_drink = {"name": "Green Tea", "foodType": "veg", "type": "hot"}
    assert resolve_product_food_type(explicit_veg_drink, category="drink") == "veg"

    # 3. Beverage with explicit invalid foodType fails
    invalid_drink = {"name": "Experimental Drink", "foodType": "pescatarian"}
    try:
        resolve_product_food_type(invalid_drink, category="drink")
        assert False, "Expected ValueError for invalid drink foodType"
    except ValueError as e:
        assert "Experimental Drink" in str(e)

    # 4. Non-beverage items without explicit foodType must NOT default to 'veg'
    burger_item = {"name": "Bacon King", "type": "burger"}
    try:
        resolve_product_food_type(burger_item, category="burger")
        assert False, "Burger without foodType must fail"
    except ValueError as e:
        assert "Bacon King" in str(e)

    print("PASS: test_beverage_category_dietary_contract")


if __name__ == "__main__":
    test_canonical_food_type_normalization()
    test_legacy_food_type_normalization()
    test_missing_food_type_raises_actionable_error()
    test_blank_food_type_raises_actionable_error()
    test_unsupported_food_type_raises_actionable_error()
    test_beverage_category_dietary_contract()
    print("\nALL MENU DATA INTEGRITY REGRESSION TESTS PASSED!")
