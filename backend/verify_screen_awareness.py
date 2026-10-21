import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def norm_text(s):
    if not s:
        return ""
    return " ".join(str(s).lower().split())

def post(endpoint, data):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())

client_seq = 0
session_id = None

def client_sync(screen, extra=None):
    global client_seq
    client_seq += 10
    payload = {"screen": screen, "seq": client_seq, "session_id": session_id}
    if extra:
        payload.update(extra)
    return post("/screen", payload)

print("=== STARTING THEATOM SCREEN-AWARENESS & CONTEXT VERIFICATION ===")

# -------------------------------------------------------------
# Scenario 10: New session initialization
# -------------------------------------------------------------
print("\n--- Test Scenario 10: Session Start & Clean State ---")
start_res = post("/session/start", {})
assert start_res.get("success") is True
session_id = start_res.get("session_id")
print("Session started successfully:", session_id)

sync_res = client_sync("category_selection")
assert sync_res.get("screen") == "category_selection"
assert "open_cart" in sync_res.get("available_controls", [])
assert sync_res.get("selected_product") is None
print("Initial category screen synced: active product:", sync_res.get("selected_product"))
time.sleep(1)

# -------------------------------------------------------------
# Scenario 2: "Have in a burger" from category selection
# -------------------------------------------------------------
print("\n--- Test Scenario 2: 'Have in a burger' from category_selection ---")
burger_res = post("/message", {"message": "Have in a burger"})
print("Response screen:", burger_res.get("screen"))
print("Response message:", burger_res.get("message"))
assert burger_res.get("screen") in ["recommended_burgers", "burger_menu"]
assert burger_res.get("data", {}).get("ui_action") != "add_to_cart"
cart_data = get("/cart")
assert len(cart_data.get("cart", [])) == 0, "Cart should be empty after category navigation"
print("PASS: Entered burger browsing flow without adding item to cart.")
time.sleep(1)

# -------------------------------------------------------------
# Specific-Product Guard: Verify modified/specific burger requests don't route as generic category
# -------------------------------------------------------------
print("\n--- Test Specific-Product Guard in Category Parser ---")
guard_res = post("/message", {"message": "I want a spicy chicken burger"})
print("Guard response message:", guard_res.get("message"))
assert guard_res.get("data", {}).get("ui_action") != "open_category", "Must not fast-path modified product request to generic category"
print("PASS: Specific-product guard prevented generic category fast-path.")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 6 & 1: Select Crispy Veg, check active product
# -------------------------------------------------------------
print("\n--- Test Scenario 6: Select Crispy Veg on Product Page ---")
prod_res = post("/message", {"message": "I want Crispy Veg"})
print("Response screen:", prod_res.get("screen"))
print("Response message:", prod_res.get("message"))
assert prod_res.get("screen") == "product"
time.sleep(1)

# Ask what product did I select
query_prod = post("/message", {"message": "What product did I select?"})
print("Query active product message:", query_prod.get("message"))
assert "crispy veg" in norm_text(query_prod.get("message", "")), "Should identify Crispy Veg as selected product"
print("PASS: Authoritative active product recognized as Crispy Veg.")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 5: Valid add_to_cart on product page
# -------------------------------------------------------------
print("\n--- Test Scenario 5: 'Add it to my cart' on product screen ---")
# First decline meal offer if open
decline_res = post("/message", {"message": "No thanks, just the burger"})
print("Decline message:", decline_res.get("message"))
time.sleep(1)

add_res = post("/message", {"message": "Add it to my cart"})
print("Add to cart response:", add_res)
assert add_res.get("data", {}).get("ui_action") == "add_to_cart", "Should trigger add_to_cart ui_action"
print("PASS: 'Add it to my cart' executed successfully on product page.")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 1 & 7: Go back to categories & ask what screen am I on
# -------------------------------------------------------------
print("\n--- Test Scenario 1 & 7: 'Go back' and check current screen ---")
back_res = post("/message", {"message": "Go back"})
print("Go back response:", back_res)
assert back_res.get("data", {}).get("ui_action") == "go_back"
assert back_res.get("screen") == "category_selection"
time.sleep(1)

# Frontend confirms arrival at category_selection
sync_back = client_sync("category_selection")
assert sync_back.get("screen") == "category_selection"
assert sync_back.get("selected_product") is None, "Selected product must be None when on category_selection"

# Ask what screen am I on
screen_query = post("/message", {"message": "What screen am I on?"})
print("Screen query response:", screen_query.get("message"))
assert "category" in norm_text(screen_query.get("message", "")) or "menu" in norm_text(screen_query.get("message", ""))
assert "product page" not in norm_text(screen_query.get("message", ""))
print("PASS: Assistant authoritatively confirmed category selection screen.")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 3: Retain historical context for previous item
# -------------------------------------------------------------
print("\n--- Test Scenario 3: Historical context for earlier item ---")
hist_query = post("/message", {"message": "What product was discussed earlier?"})
print("Historical query response:", hist_query.get("message"))
assert "crispy veg" in norm_text(hist_query.get("message", ""))
print("PASS: Historical conversational memory retained Crispy Veg.")
time.sleep(1)

# -------------------------------------------------------------
# No Restoration from Historical Memory on Product Screen
# -------------------------------------------------------------
print("\n--- Test No Restoration of selected_product from last_item ---")
# If a screen sync arrives for "product" WITHOUT product info, it must NOT restore selected_product from last_item
sync_anon_prod = client_sync("product")
print("Anonymous product screen sync:", sync_anon_prod)
assert sync_anon_prod.get("screen") == "product"
assert sync_anon_prod.get("selected_product") is None, "Must NOT restore selected_product from last_item"
print("PASS: Missing active selection is NOT inferred or restored from historical memory.")

# Return back to category_selection
client_sync("category_selection")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 4: "Add it to my cart" after navigating away
# -------------------------------------------------------------
print("\n--- Test Scenario 4: 'Add it to my cart' from category_selection ---")
stale_add = post("/message", {"message": "Add it to my cart"})
print("Stale add response:", stale_add.get("message"))
assert stale_add.get("data", {}).get("ui_action") != "add_to_cart", "Must NOT execute add_to_cart from category_selection"
# Check message doesn't falsely claim it added the item
resp_msg = norm_text(stale_add.get("message", ""))
assert "added" not in resp_msg or "select" in resp_msg or "cannot" in resp_msg or "not available" in resp_msg or "menu" in resp_msg
print("PASS: System safely prevented stale add_to_cart from category_selection.")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 8: Attempt unavailable action
# -------------------------------------------------------------
print("\n--- Test Scenario 8: Unavailable action rejection ---")
filter_res = post("/message", {"message": "Show only veg items"})
print("Filter on categories response:", filter_res.get("message"))
assert filter_res.get("data", {}).get("ui_action") != "filter_veg", "Cannot filter on category_selection"
print("PASS: Unavailable action rejected and not executed.")
time.sleep(1)

# -------------------------------------------------------------
# Scenario 10: Session-aware & Stale Sequence Protection
# -------------------------------------------------------------
print("\n--- Test Scenario 10: Session-aware & Stale Sync Protection ---")
# 1. Stale sequence within same session (e.g. seq: 2 when current is client_seq >= 40)
stale_sync = post("/screen", {"screen": "product", "seq": 2, "session_id": session_id, "product": "Stale Item"})
print("Stale sync response:", stale_sync)
assert stale_sync.get("stale_ignored") is True or stale_sync.get("screen") == "category_selection"

# 2. Mismatched session id from old/stale session
old_session_sync = post("/screen", {"screen": "product", "seq": 9999, "session_id": "old-expired-session-id"})
print("Old session sync response:", old_session_sync)
assert old_session_sync.get("stale_ignored") is True or old_session_sync.get("screen") == "category_selection"

# Verify current screen did NOT revert to product
check_state = client_sync("category_selection")
assert check_state.get("screen") == "category_selection"
assert check_state.get("selected_product") is None
print("PASS: Stale and cross-session screen updates were safely ignored.")

print("\n=== ALL VERIFICATION SCENARIOS PASSED SUCCESSFULLY! ===")
