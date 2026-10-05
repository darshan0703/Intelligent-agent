"""
Unit tests for Module 7: Absolute Cart Exclusion
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
module_dir = os.path.abspath(os.path.join(current_dir, "..", "files", "backend"))
sys.path.insert(0, backend_dir)
sys.path.insert(0, module_dir)

try:
    from services.modules.m07_cart_exclusion import exclude_cart_items
except ImportError:
    from backend.services.modules.m07_cart_exclusion import exclude_cart_items

def test_cart_exclusion_by_id():
    cart = [{"id": 101, "name": "Veg Whopper"}]
    candidates = [
        {"id": 101, "name": "Veg Whopper"},
        {"id": 102, "name": "Peri Peri Fries"},
    ]
    survivors = exclude_cart_items(candidates, cart)
    assert len(survivors) == 1, f"Expected 1 survivor, got {len(survivors)}"
    assert survivors[0]["id"] == 102
    print("PASS: test_cart_exclusion_by_id")

def test_cart_exclusion_by_name():
    cart = [{"name": "Classic Fries"}]
    candidates = [
        {"id": 201, "name": "Classic Fries "},  # trailing space normalized
        {"id": 202, "name": "Cold Coffee"},
    ]
    survivors = exclude_cart_items(candidates, cart)
    assert len(survivors) == 1
    assert survivors[0]["id"] == 202
    print("PASS: test_cart_exclusion_by_name")

if __name__ == "__main__":
    test_cart_exclusion_by_id()
    test_cart_exclusion_by_name()
    print("\nALL CART EXCLUSION TESTS PASSED!")
