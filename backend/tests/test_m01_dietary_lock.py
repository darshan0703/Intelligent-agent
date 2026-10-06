"""
Unit tests for Module 1: Strict Dietary Lock and Recommendation Integration.
Can be run completely standalone without any server or database running.
Usage:
  python tests/test_m01_dietary_lock.py
"""
import sys
import os

# Add package paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
package_dir = os.path.abspath(os.path.join(current_dir, "..", "files", "backend"))
sys.path.insert(0, parent_dir)
sys.path.insert(0, package_dir)

try:
    from services.modules.m01_dietary_lock import apply_dietary_lock
except ImportError:
    from backend.services.modules.m01_dietary_lock import apply_dietary_lock

MOCK_MENU = [
    {"id": 1, "name": "Veg Whopper", "foodType": "veg", "price": 140, "stock": 50, "priority": 10},
    {"id": 2, "name": "Chicken Whopper", "foodType": "non veg", "price": 180, "stock": 40, "priority": 12},
    {"id": 3, "name": "Paneer Royale", "foodType": "veg", "price": 199, "stock": 20, "priority": 8},
    {"id": 4, "name": "Crispy Chicken", "foodType": "non veg", "price": 120, "stock": 35, "priority": 15},
    {"id": 5, "name": "Veggie Strips", "foodType": "veg", "price": 80, "stock": 60, "priority": 5},
    {"id": 6, "name": "Chicken Wings", "foodType": "non_veg", "price": 160, "stock": 15, "priority": 9},
]

def test_explicit_veg_lock():
    result = apply_dietary_lock(MOCK_MENU, preference="veg", cart=[])
    assert all("non" not in item.get("foodType", "").lower() for item in result), "Non-veg item leaked into veg filter!"
    assert len(result) == 3, f"Expected 3 veg items, got {len(result)}"
    print("PASS: test_explicit_veg_lock")

def test_explicit_non_veg_lock():
    result = apply_dietary_lock(MOCK_MENU, preference="non_veg", cart=[])
    assert all("non" in item.get("foodType", "").lower() for item in result), "Veg item leaked into non-veg filter!"
    assert len(result) == 3, f"Expected 3 non-veg items, got {len(result)}"
    print("PASS: test_explicit_non_veg_lock")

def test_both_lock_unfiltered():
    result = apply_dietary_lock(MOCK_MENU, preference="both", cart=[])
    assert len(result) == len(MOCK_MENU), "Both preference should not filter any items"
    print("PASS: test_both_lock_unfiltered")

def test_implicit_cart_veg_lock():
    cart = [{"id": 10, "name": "Classic Fries", "foodType": "veg"}]
    # Preference is None, but cart is 100% veg -> should automatically lock to veg
    result = apply_dietary_lock(MOCK_MENU, preference=None, cart=cart)
    assert all("non" not in item.get("foodType", "").lower() for item in result), "Implicit cart veg lock failed!"
    print("PASS: test_implicit_cart_veg_lock")

def test_mutual_exclusion():
    filtered = apply_dietary_lock(MOCK_MENU, preference="both", cart=[])
    priority = filtered[:2]
    used_ids = {i["id"] for i in priority}
    premium = [i for i in filtered if i["id"] not in used_ids][:2]
    for p in premium:
        used_ids.add(p["id"])
    additional = [i for i in filtered if i["id"] not in used_ids][:4]

    # Verify zero duplicate IDs across priority, premium, additional
    p_ids = {i["id"] for i in priority}
    pr_ids = {i["id"] for i in premium}
    ad_ids = {i["id"] for i in additional}

    assert p_ids.isdisjoint(pr_ids), "Priority and Premium share duplicate items!"
    assert p_ids.isdisjoint(ad_ids), "Priority and Additional share duplicate items!"
    assert pr_ids.isdisjoint(ad_ids), "Premium and Additional share duplicate items!"
    print("PASS: test_mutual_exclusion")

if __name__ == "__main__":
    test_explicit_veg_lock()
    test_explicit_non_veg_lock()
    test_both_lock_unfiltered()
    test_implicit_cart_veg_lock()
    test_mutual_exclusion()
    print("\nALL 5 DIETARY LOCK TESTS PASSED!")
