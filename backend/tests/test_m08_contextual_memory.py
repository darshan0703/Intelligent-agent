"""
backend/tests/test_m08_contextual_memory.py
Unit tests for Module B1: Contextual Observation Memory Store
"""

import pytest
from services.modules.m08_contextual_memory import (
    record_observation,
    record_meal_rejection,
    is_meal_offer_dismissed,
    get_active_rejections,
    record_item_view,
    ensure_memory_structures,
)


def test_meal_rejection_scoped_to_item():
    context = {}
    ensure_memory_structures(context)

    # Reject meal for item 12 (Veg Makhani)
    record_meal_rejection(context, item_id=12)

    # Item 12 meal offer MUST be dismissed
    assert is_meal_offer_dismissed(context, item_id=12) is True
    assert is_meal_offer_dismissed(context, item_id="12") is True

    # Item 15 (Veg Whopper) meal offer MUST NOT be dismissed
    assert is_meal_offer_dismissed(context, item_id=15) is False
    assert is_meal_offer_dismissed(context, item_id=99) is False


def test_active_rejections_tracking():
    context = {}
    record_observation(context, subject="recommendation", predicate="item_rejected", value="65", scope="item")
    record_meal_rejection(context, item_id=12)

    rejections = get_active_rejections(context)
    assert "65" in rejections
    assert "12" in rejections
    assert "99" not in rejections


def test_view_history_recording():
    context = {}
    record_item_view(context, item_id=12, item_name="Veg Makhani")
    record_item_view(context, item_id=15, item_name="Veg Whopper")

    assert len(context["view_history"]) == 2
    assert context["view_history"][0]["item_name"] == "Veg Makhani"
    assert context["view_history"][1]["item_name"] == "Veg Whopper"
