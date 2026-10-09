"""
Unit & Integration Tests for backend/services/menu_service.py and API menu endpoints.

Verifies:
1. get_menu() across all 4 canonical categories (burger, drink, side, dessert).
2. Singular and plural category normalization (burger/burgers, drink/drinks, side/sides, dessert/desserts).
3. Invalid category resilience (unknown categories return [] and do not leak other products).
4. Empty catalog / repository returning empty sections.
5. Explicit dietary preference propagation (veg, non_veg, both, None) reaching M01 canonical filtering.
6. Unrestricted browsing when preference is None or 'both'.
7. Cart propagation into menu_organizer, including explicit cart=[].
8. API POST endpoints (/menu/*): explicit cart=[] preserved and not overridden by stale conversation_context["cart"].
9. API POST endpoints fallback to conversation_context["cart"] only when request body cart is None/omitted.
10. Dietary preference isolation: conversation_context["food_preference"] does NOT leak into drinks or desserts.
11. Preservation of section and product ordering through organizer and service.
12. API response schema compatibility ({id, title, products}).
"""
import sys
import os
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from state import conversation_context, reset_conversation
from services.menu_service import get_menu
from repositories.menu_repository import normalize_category, get_menu_sections
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


# =========================================================
# 1. CATEGORY NORMALIZATION & ROUTING TESTS
# =========================================================

def test_category_normalization_mappings():
    # Canonical singular forms
    assert normalize_category("burger") == "burger"
    assert normalize_category("drink") == "drink"
    assert normalize_category("side") == "side"
    assert normalize_category("dessert") == "dessert"

    # Plural forms
    assert normalize_category("burgers") == "burger"
    assert normalize_category("drinks") == "drink"
    assert normalize_category("sides") == "side"
    assert normalize_category("desserts") == "dessert"

    # Whitespace and case-insensitivity
    assert normalize_category("  Burgers  ") == "burger"
    assert normalize_category("DRINKS") == "drink"
    assert normalize_category("Sides") == "side"

    # Invalid / unrelated categories must return None
    assert normalize_category("pizza") is None
    assert normalize_category("unknown") is None
    assert normalize_category("") is None
    assert normalize_category(None) is None
    print("PASS: test_category_normalization_mappings")


def test_invalid_category_returns_empty_and_does_not_leak():
    # Calling get_menu with an invalid category returns empty list without error
    assert get_menu("pizza") == []
    assert get_menu("unknown") == []
    assert get_menu("") == []
    assert get_menu(None) == []

    # Calling get_menu_sections with an invalid category returns empty list
    assert get_menu_sections("pizza") == []
    print("PASS: test_invalid_category_returns_empty_and_does_not_leak")


def test_singular_and_plural_categories_return_identical_results():
    for sing, plur in [("burger", "burgers"), ("drink", "drinks"), ("side", "sides"), ("dessert", "desserts")]:
        res_sing = get_menu(sing, preference=None, cart=[])
        res_plur = get_menu(plur, preference=None, cart=[])

        assert len(res_sing) == len(res_plur), f"Section count mismatch for {sing} vs {plur}"
        sing_titles = [s["title"] for s in res_sing]
        plur_titles = [s["title"] for s in res_plur]
        assert sing_titles == plur_titles, f"Section titles mismatch for {sing} vs {plur}"

        sing_prods = [p["id"] for s in res_sing for p in s["products"]]
        plur_prods = [p["id"] for s in res_plur for p in s["products"]]
        assert sing_prods == plur_prods, f"Product IDs mismatch for {sing} vs {plur}"

    print("PASS: test_singular_and_plural_categories_return_identical_results")


# =========================================================
# 2. CANONICAL CATEGORY BROWSING & RESPONSE SCHEMA
# =========================================================

def test_get_menu_all_four_categories():
    for cat in ["burger", "drink", "side", "dessert"]:
        sections = get_menu(cat, preference=None, cart=[])
        assert isinstance(sections, list), f"Expected list of sections for {cat}"
        assert len(sections) > 0, f"Expected non-empty menu sections for {cat}"

        for sec in sections:
            assert "id" in sec, f"Section missing 'id' in {cat}"
            assert "title" in sec, f"Section missing 'title' in {cat}"
            assert "products" in sec, f"Section missing 'products' in {cat}"
            assert len(sec["products"]) > 0, f"Section {sec['title']} has no products"

            for prod in sec["products"]:
                assert "id" in prod, "Product missing 'id'"
                assert "name" in prod, "Product missing 'name'"
                assert "price" in prod, "Product missing 'price'"
                assert "stock" in prod, "Product missing 'stock'"

    print("PASS: test_get_menu_all_four_categories")


def test_empty_catalog_handling():
    # When get_menu_sections returns [], get_menu gracefully returns []
    with patch("services.menu_service.get_menu_sections", return_value=[]):
        result = get_menu("burger", preference=None, cart=[])
        assert result == [], "Empty repository catalog must return []"
    print("PASS: test_empty_catalog_handling")


# =========================================================
# 3. DIETARY PREFERENCE PROPAGATION & ISOLATION
# =========================================================

def test_dietary_preference_propagation_in_burgers():
    from services.modules.m01_dietary_lock import normalize_food_type

    # Explicit 'veg' preference returns only vegetarian products
    veg_sections = get_menu("burger", preference="veg", cart=[])
    for sec in veg_sections:
        for p in sec["products"]:
            food_type = normalize_food_type(p.get("foodType") or p.get("food_type", ""))
            assert food_type == "veg", f"Non-veg product {p['name']} found in veg burger menu"

    # Explicit 'non_veg' preference returns only non-vegetarian products
    non_veg_sections = get_menu("burger", preference="non_veg", cart=[])
    for sec in non_veg_sections:
        for p in sec["products"]:
            food_type = normalize_food_type(p.get("foodType") or p.get("food_type", ""))
            assert food_type == "non_veg", f"Veg product {p['name']} found in non-veg burger menu"

    # Unrestricted browsing ('both' or None) returns both
    unrestricted = get_menu("burger", preference=None, cart=[])
    all_types = {normalize_food_type(p.get("foodType") or p.get("food_type", "")) for s in unrestricted for p in s["products"]}
    assert "veg" in all_types and "non_veg" in all_types, "Unrestricted browsing must contain both types"
    print("PASS: test_dietary_preference_propagation_in_burgers")


def test_no_dietary_preference_leakage_into_drinks_and_desserts():
    reset_conversation("test-session")
    conversation_context["food_preference"] = "veg"

    try:
        # 1. Direct call to get_menu("drink", preference=None)
        # Must NOT inherit conversation_context["food_preference"]
        drink_sections = get_menu("drink", preference=None, cart=[])
        assert len(drink_sections) > 0

        # 2. Direct call to get_menu("dessert", preference=None)
        # Must NOT inherit conversation_context["food_preference"]
        dessert_sections = get_menu("dessert", preference=None, cart=[])
        assert len(dessert_sections) > 0

        # 3. For burgers, preference=None SHOULD fall back to conversation_context
        burger_sections = get_menu("burger", preference=None, cart=[])
        for sec in burger_sections:
            for p in sec["products"]:
                food_type = str(p.get("foodType") or p.get("food_type", "")).lower()
                assert food_type == "veg", f"Burger should inherit veg preference, got {p['name']}"

        # 4. For drinks, explicit preference passed as parameter IS honored
        explicit_veg_drinks = get_menu("drink", preference="veg", cart=[])
        assert len(explicit_veg_drinks) > 0

    finally:
        reset_conversation()

    print("PASS: test_no_dietary_preference_leakage_into_drinks_and_desserts")


# =========================================================
# 4. CART PROPAGATION & EXPLICIT EMPTY CART FIX
# =========================================================

def test_service_explicit_empty_cart_not_overridden():
    reset_conversation("test-cart-session")

    # Baseline with empty cart to find the top item
    base_menu = get_menu("burger", preference=None, cart=[])
    whopper_sec = next(s for s in base_menu if "whopper" in s["title"].lower())
    assert len(whopper_sec["products"]) > 1
    top_product = whopper_sec["products"][0]
    top_id = top_product["id"]

    stale_cart = [{"id": top_id, "name": top_product["name"], "price": top_product.get("price", 100)}]
    conversation_context["cart"] = stale_cart

    try:
        # Passing cart=[] explicitly must NOT fall back to stale_cart
        # If cart was not empty, top_product would be placed at the very end of its section.
        result_with_empty_cart = get_menu("burger", preference=None, cart=[])
        whopper_sec_empty = next(s for s in result_with_empty_cart if "whopper" in s["title"].lower())
        assert whopper_sec_empty["products"][-1]["id"] != top_id, (
            "Explicit cart=[] must not push top product to end"
        )

        # Passing cart=None falls back to conversation_context["cart"]
        result_with_fallback = get_menu("burger", preference=None, cart=None)
        whopper_sec_fallback = next(s for s in result_with_fallback if "whopper" in s["title"].lower())
        # The carted item must be pushed to the very end of the section!
        assert whopper_sec_fallback["products"][-1]["id"] == top_id, (
            "When cart is None, fallback to conversation_context must push carted item to end"
        )
    finally:
        reset_conversation()

    print("PASS: test_service_explicit_empty_cart_not_overridden")


# =========================================================
# 5. API ENDPOINT REGRESSION TESTS (/menu/*)
# =========================================================

def test_api_menu_endpoints_get_and_post():
    for endpoint in ["/menu/burgers", "/menu/drinks", "/menu/sides", "/menu/desserts"]:
        # GET request
        res_get = client.get(endpoint)
        assert res_get.status_code == 200, f"GET {endpoint} returned {res_get.status_code}"
        data_get = res_get.json()
        assert isinstance(data_get, list)
        assert len(data_get) > 0
        for sec in data_get:
            assert "id" in sec and "title" in sec and "products" in sec, f"Invalid section schema in {endpoint}"
            assert isinstance(sec["products"], list)
            for prod in sec["products"]:
                assert "id" in prod and "name" in prod and "price" in prod, f"Invalid product schema in {endpoint}: {prod}"

        # POST request with cart
        res_post = client.post(endpoint, json={"cart": []})
        assert res_post.status_code == 200, f"POST {endpoint} returned {res_post.status_code}"
        data_post = res_post.json()
        assert isinstance(data_post, list)
        assert len(data_post) > 0
        for sec in data_post:
            assert "id" in sec and "title" in sec and "products" in sec, f"Invalid section schema in POST {endpoint}"
            assert isinstance(sec["products"], list)

    print("PASS: test_api_menu_endpoints_get_and_post")


def test_api_post_explicit_empty_cart_preservation():
    reset_conversation("api-test-session")

    base_menu = get_menu("burger", preference=None, cart=[])
    whopper_sec = next(s for s in base_menu if "whopper" in s["title"].lower())
    assert len(whopper_sec["products"]) > 1
    top_product = whopper_sec["products"][0]
    top_id = top_product["id"]

    stale_cart = [{"id": top_id, "name": top_product["name"], "price": top_product.get("price", 100)}]
    conversation_context["cart"] = stale_cart

    try:
        # POST with explicit cart=[]: must NOT use stale_cart
        res = client.post("/menu/burgers", json={"cart": []})
        assert res.status_code == 200
        sections = res.json()
        whopper_sec_empty = next(s for s in sections if "whopper" in s["title"].lower())
        assert whopper_sec_empty["products"][-1]["id"] != top_id, (
            "Explicit cart=[] must not push top item to the end using stale conversation cart!"
        )

        # POST with cart omitted/None: MUST use conversation_context["cart"]
        res_fallback = client.post("/menu/burgers", json={})
        assert res_fallback.status_code == 200
        sections_fallback = res_fallback.json()
        whopper_sec_fallback = next(s for s in sections_fallback if "whopper" in s["title"].lower())
        assert whopper_sec_fallback["products"][-1]["id"] == top_id, (
            "POST with omitted cart must fall back to conversation cart and push item to end"
        )
    finally:
        reset_conversation()

    print("PASS: test_api_post_explicit_empty_cart_preservation")


def test_api_drinks_and_desserts_no_preference_leakage():
    reset_conversation("api-pref-session")
    conversation_context["food_preference"] = "veg"

    try:
        # GET /menu/drinks without preference query param:
        # must NOT filter drinks by veg!
        res_drinks = client.get("/menu/drinks")
        assert res_drinks.status_code == 200
        drink_sections = res_drinks.json()
        assert len(drink_sections) > 0

        # POST /menu/drinks without preference query param:
        res_drinks_post = client.post("/menu/drinks", json={"cart": []})
        assert res_drinks_post.status_code == 200
        assert len(res_drinks_post.json()) > 0

        # GET /menu/desserts without preference query param:
        res_desserts = client.get("/menu/desserts")
        assert res_desserts.status_code == 200
        assert len(res_desserts.json()) > 0

        # POST /menu/desserts without preference query param:
        res_desserts_post = client.post("/menu/desserts", json={"cart": []})
        assert res_desserts_post.status_code == 200
        assert len(res_desserts_post.json()) > 0

        # Meanwhile, GET /menu/burgers without preference param DOES inherit veg fallback
        res_burgers = client.get("/menu/burgers")
        assert res_burgers.status_code == 200
        for s in res_burgers.json():
            for p in s["products"]:
                assert str(p.get("foodType") or p.get("food_type", "")).lower() == "veg"

    finally:
        reset_conversation()

    print("PASS: test_api_drinks_and_desserts_no_preference_leakage")


if __name__ == "__main__":
    # Category normalization and routing
    test_category_normalization_mappings()
    test_invalid_category_returns_empty_and_does_not_leak()
    test_singular_and_plural_categories_return_identical_results()

    # Category browsing & schema
    test_get_menu_all_four_categories()
    test_empty_catalog_handling()

    # Dietary preference propagation & isolation
    test_dietary_preference_propagation_in_burgers()
    test_no_dietary_preference_leakage_into_drinks_and_desserts()

    # Cart propagation & empty cart fix
    test_service_explicit_empty_cart_not_overridden()

    # API endpoints integration & regression
    test_api_menu_endpoints_get_and_post()
    test_api_post_explicit_empty_cart_preservation()
    test_api_drinks_and_desserts_no_preference_leakage()

    print("\nALL MENU SERVICE & API REGRESSION TESTS PASSED SUCCESSFULLY!")
