"""
tests/unit/test_domain.py
Unit tests for domain entities, Decimal money precision, and cart invariants.
"""
from decimal import Decimal
import pytest
from app.domain.catalog.value_objects import Price, CategorySlug, FoodType, ServingType
from app.domain.catalog.entities import MenuItem, InventorySnapshot
from app.domain.cart.entities import Cart, CartLine, MealComposition


def test_price_decimal_precision():
    p1 = Price(Decimal("119.99"))
    p2 = Price(Decimal("59.01"))
    total = p1.add(p2)
    assert total.amount == Decimal("179.00")
    assert str(total) == "179.00"

    # Must reject float
    with pytest.raises(TypeError):
        Price(19.99)  # type: ignore


def test_cart_operations():
    cart = Cart(session_id="test-session")
    item = MenuItem(
        id=1,
        name="Whopper",
        price=Price(Decimal("179.00")),
        category=CategorySlug.BURGER,
        food_type=FoodType.NON_VEG,
        inventory=InventorySnapshot(item_id=1, branch_id=1, stock=10),
    )

    cart.add_item(item, quantity=2)
    assert cart.item_count == 2
    assert cart.subtotal.amount == Decimal("358.00")

    # Adding same item increases quantity
    cart.add_item(item, quantity=1)
    assert cart.item_count == 3
    assert cart.subtotal.amount == Decimal("537.00")

    # Removing item
    cart.remove_item(item_id=1, quantity=1)
    assert cart.item_count == 2
    assert cart.subtotal.amount == Decimal("358.00")

    cart.clear()
    assert cart.item_count == 0
    assert cart.subtotal.amount == Decimal("0.00")


def test_meal_composition():
    meal = MealComposition(
        size="medium",
        main_item_id=1,
        main_item_name="Whopper",
        side_id=10,
        side_name="Classic Fries",
        drink_id=20,
        drink_name="Coke",
        burger_price=Price(Decimal("179.00")),
        upgrade_price=Price(Decimal("120.00")),
        side_extra=Price(Decimal("20.00")),
        drink_extra=Price(Decimal("0.00")),
    )
    assert meal.total_price.amount == Decimal("319.00")
