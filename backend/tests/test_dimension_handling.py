"""
Regression tests for voice interpretation of dimensions and measurements.
Verifies that:
1. Spoken dimensions (such as '8 feet 8, 11 feet 8.') are parsed into structured representations.
2. The system does not invent menu items, quantities, or cart modifications from dimensions.
3. A clear, concise clarifying question is returned.
4. Normal menu orders (burgers, drinks, sides, etc.) remain intact.
"""

import pytest
from unittest.mock import MagicMock
from services.dimension_parser import (
    parse_spoken_dimensions,
    is_dimension_query,
    build_dimension_clarification_response,
)
from state import conversation_context
from screen_controls import ScreenTypes


def test_parse_spoken_dimensions_compound():
    """Verify '8 feet 8, 11 feet 8.' produces structured measurement list with explicit units."""
    utterance = "8 feet 8, 11 feet 8."
    dims = parse_spoken_dimensions(utterance)

    assert len(dims) == 2
    assert dims[0]["feet"] == 8.0
    assert dims[0]["inches"] == 8.0
    assert dims[0]["unit"] == "feet_inches"
    assert dims[0]["raw"] == "8 feet 8"

    assert dims[1]["feet"] == 11.0
    assert dims[1]["inches"] == 8.0
    assert dims[1]["unit"] == "feet_inches"
    assert dims[1]["raw"] == "11 feet 8"


def test_parse_spoken_dimensions_single_and_units():
    """Verify parsing single dimension units (inches, meters, feet)."""
    assert is_dimension_query("12 inches") is True
    res_inches = parse_spoken_dimensions("12 inches")
    assert len(res_inches) == 1
    assert res_inches[0]["value"] == 12.0
    assert res_inches[0]["unit"] == "inches"

    assert is_dimension_query("5 meters") is True
    res_meters = parse_spoken_dimensions("5 meters")
    assert len(res_meters) == 1
    assert res_meters[0]["value"] == 5.0
    assert res_meters[0]["unit"] == "meters"


def test_regular_food_queries_not_flagged_as_dimensions():
    """Verify that regular menu items, drinks, and categories are not flagged as dimensions."""
    non_dimension_queries = [
        "Veg Whopper",
        "Can I get a chicken burger?",
        "Add fries and coke",
        "Two Peri Peri Chicken burgers",
        "Chocolate Sundae",
        "Show me burgers",
        "Checkout",
        "Yes make it a meal",
    ]
    for q in non_dimension_queries:
        assert is_dimension_query(q) is False, f"Expected '{q}' not to be identified as a dimension"
        assert parse_spoken_dimensions(q) == []


def test_dimension_utterance_does_not_modify_cart_or_invent_product():
    """
    Verify that an observed dimension utterance '8 feet 8, 11 feet 8.'
    does not invent a product, does not add to cart, and returns a helpful clarifying response.
    """
    initial_cart = [{"type": "item", "id": 7, "quantity": 1}]
    conversation_context["cart"] = list(initial_cart)
    conversation_context["current_screen"] = ScreenTypes.HOME

    dims = parse_spoken_dimensions("8 feet 8, 11 feet 8.")
    assert len(dims) == 2

    clarification = build_dimension_clarification_response(dims, ScreenTypes.HOME)
    assert "dimensions or physical measurements" in clarification.lower()
    assert "burger" in clarification.lower()

    # Cart remains untouched
    assert conversation_context["cart"] == initial_cart
    assert len(conversation_context["cart"]) == 1
    # No quantity invented
    assert conversation_context.get("screen_quantity") != 8
    assert conversation_context.get("screen_quantity") != 11
