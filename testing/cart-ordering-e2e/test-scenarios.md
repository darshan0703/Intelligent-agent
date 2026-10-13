# Cart Ordering Verification Scenarios

This document specifies the verification criteria and expected behavior for the cart-ordering fix on branch `feature/cart-ordering-fix-clean`.

---

### Behavior 1: Adding products displays correct items and quantities
- **Objective**: Verify that adding individual items through the kiosk product workflow correctly populates the cart with accurate names, quantities, line subtotals, and total cost.
- **Initial State**: Fresh session, empty cart (`0 items`, `₹ 0/-`).
- **Steps**:
  1. Add "Crispy Veg" (₹ 59).
  2. Add "Crispy Chicken" (₹ 79).
  3. Add "Chicken Makhani" (₹ 89).
- **Expected Outcome**:
  - Sidebar cart displays 3 distinct line items in chronological order: `["Crispy Veg", "Crispy Chicken", "Chicken Makhani"]`.
  - Item count equals 3 (`(3 items)`).
  - Total equals ₹ 227/- (59 + 79 + 89).

---

### Behavior 2: Increasing an item's quantity applies the intended ordering rule
- **Objective**: When an existing item's quantity is increased, it must move to the bottom of the display cart, signaling recent customer modification.
- **Initial State**: Cart items: `["Crispy Veg", "Crispy Chicken", "Chicken Makhani"]`.
- **Steps**:
  1. Navigate to `/Cart`.
  2. Click the `+` button on the first item ("Crispy Veg").
- **Expected Outcome**:
  - Quantity of "Crispy Veg" becomes 2.
  - "Crispy Veg" is moved to the bottom of the list.
  - New display order: `["Crispy Chicken", "Chicken Makhani", "Crispy Veg"]`.
  - Total updates to ₹ 286/-.

---

### Behavior 3: Removing an item does not incorrectly reorder unrelated items
- **Objective**: Deleting a cart line item must remove only that item and preserve the exact relative display ordering of remaining items without unintended jumps or reshuffling.
- **Initial State**: Cart items: `["Crispy Chicken", "Chicken Makhani", "Crispy Veg"]`.
- **Steps**:
  1. Click the remove/delete icon on "Crispy Chicken".
- **Expected Outcome**:
  - "Crispy Chicken" is removed.
  - Remaining items: `["Chicken Makhani", "Crispy Veg"]`.
  - Relative ordering of "Chicken Makhani" (1st) and "Crispy Veg" (2nd) is strictly maintained.

---

### Behavior 4: Sidebar cart ordering matches Cart Page ordering
- **Objective**: Ensure that the sidebar (`CartContainer`) and the full review screen (`CartPage`) use a single centralized ordering state rather than conflicting local calculations or diverging `sessionStorage` effects.
- **Initial State**: 3 items in cart on `/burgermenu`.
- **Steps**:
  1. Record sidebar item sequence.
  2. Navigate to `/Cart`.
  3. Record Cart Page item sequence.
- **Expected Outcome**:
  - Exact 1:1 match in item sequence between sidebar and Cart Page.

---

### Behavior 5: Rapid cart mutations do not modify the wrong item
- **Objective**: Guard against race conditions and stale index mutations when a customer rapidly clicks `+`, `−`, or remove buttons.
- **Initial State**: Cart with multiple items.
- **Steps**:
  1. Rapidly click quantity mutation buttons in quick succession (< 100ms interval).
- **Expected Outcome**:
  - The UI locks buttons via `isCartUpdating` state (`disabled={isCartUpdating}`), preventing overlapping requests from dispatching on stale array indices.
  - The final backend cart remains consistent and non-corrupted.

---

### Behavior 6: Backend-provided recommendation badges remain visible
- **Objective**: Verify Module A pre-checkout recommendations on `/Cart` display context-aware recommendation badges (e.g. "🥤 Best Drink", "🍦 Sweet Finish"), and dismiss buttons only remove the targeted card.
- **Initial State**: Cart page loaded with active cart items.
- **Steps**:
  1. Verify badge elements `.cart-rec-badge` are visible with descriptive text.
  2. Click the dismiss (`✕`) button on the first recommendation card.
- **Expected Outcome**:
  - Badges render prominently.
  - Dismissing removes only the clicked card; remaining recommendation cards stay visible.

---

### Behavior 7: Clearing the cart resets its ordering state
- **Objective**: Verify that when a cart is cleared (or a new session begins), all ordering state in React context and `sessionStorage` (`cart_item_order`, `cart_qty_snapshot`) is completely wiped.
- **Initial State**: Populated cart with ordering snapshots in `sessionStorage`.
- **Steps**:
  1. Inspect `sessionStorage.getItem('cart_item_order')` and `cart_qty_snapshot`.
  2. Return to Home screen and click "TOUCH TO START" (calling `clearCart()`).
- **Expected Outcome**:
  - `sessionStorage` keys are deleted / null.
  - Cart item count is 0.
  - Next order begins with clean ordering baseline.
