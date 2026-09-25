# THEATOM RECOMMENDATION ENGINE: COMPLETE MODULE-TO-FILE DEPENDENCY & ARCHITECTURE DEEP DIVE

## 1. Executive Overview & Pipeline Architecture

The **TheAtom Recommendation Engine** operates as a deterministic, zero-cache, 4-phase decision pipeline. It does **not** evaluate modules in a loose or simultaneous manner; instead, it executes in **strict sequential order**:

```
[ Incoming Request (User Click, Cart Change, or Page Load) ]
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Hard Exclusions & Saturation Gates (Pass / Fail Bouncers)    │
│   * Sequential Short-Circuit — If an item fails, it is KILLED instantly│
│   • Module 1: Strict Dietary Lock (Drop Non-Veg if Veg locked)         │
│   • Module 7: Absolute Cart Exclusion (Drop item if already in cart)   │
│   • Module 4: Dining Pillar Evaluation & Dual-Role Saturation (Shake)  │
│   • Module 8: Gatekeeper Kill-Switch (All 4 meal pillars complete)     │
│   • Module 6 (Hard Gate): Condiment Gating (Drop Dips if no host item) │
└────────────────────────────────────────────────────────────────────────┘
                          │ (Surviving Candidates Only)
                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: Budget & Margin Protection (Economic Feasibility Gates)      │
│   • Module 5: Hard Price Ceiling & Elastic Anchoring (1.5x / 2.5x max) │
│   • Module 13: Anti-Gamification (Reject fake discounts / zero-deals)  │
│   • Module 9: Margin Multiplier (Favor margin-rich companion add-ons)  │
└────────────────────────────────────────────────────────────────────────┘
                          │ (Eligible Candidates Only)
                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Sensory & Culinary Scoring (Multiplicative Composite Score)   │
│   • Module 2: Anti-Redundancy & Universal Side Overrides (Nuggets/Fries│
│   • Module 3: Flavor Anti-Clash & Cuisine Synergy                      │
│   • Module 6 (Boost): Condiment Host Boost (1.5x when finger food in)  │
│   • Module 10: Sensory Contrast (Spicy <-> Cooling Dairy) & Thermal    │
│   • Module 12 (Circadian): Morning/Lunch/Late-night phase boosts       │
│   • Velocity Bias & Yield Management Overrides                         │
└────────────────────────────────────────────────────────────────────────┘
                          │ (Scored Candidates)
                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: Real-Time Session Heuristics & MMR Variety Diversification   │
│   • Module 11: Session Fatigue / Novelty Damping                       │
│   • Heuristic A: Attribute Affinity (Click Tracker: Spice >= 4 -> 1.3x)│
│   • Heuristic B: Sub-Role Rejection (Back-Button Signal -> 0.0x Kill)  │
│   • Heuristic C: Cart Velocity (Bulk Mode: Rushed / >= 5 -> Sharing)   │
│   • Module 13: Sub-Role MMR Diversity Re-ranking (1 Drink, 1 Side, ...)│
└────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
[ Top-K Ranked, Badged JSON Response Returned to Kiosk Frontend ]
```

---

## 2. Exhaustive Module-by-Module File Dependency Deep Dive

Here is the complete dependency matrix for **all 13 Modules** and the supporting heuristics, detailing every file across frontend and backend, what code lives in each file, its purpose, what happens if you change it, and how data flows through it.

---

### MODULE 1: Strict Dietary Lock (Veg / Non-Veg Barrier)

#### Core Responsibility
Guarantees that a customer who clicks the "Veg" filter, adds committed vegetarian entrees, or reaches $\ge 10$ veg cart items **never** sees non-vegetarian products across any menu, recommendation shelf, product modal, or checkout tray.

#### All Connected Files
1. [`frontend/src/context/KioskContext.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/context/KioskContext.jsx)
2. [`frontend/src/Pages/Burgermenu.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Burgermenu.jsx) & [`Sidesmenu.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Sidesmenu.jsx)
3. [`frontend/src/Pages/Burgerrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Burgerrepage.jsx), [`Sidesrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Sidesrepage.jsx), [`Drinkrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Drinkrepage.jsx), [`Dessertrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Dessertrepage.jsx)
4. [`backend/app/application/conversation_service.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/application/conversation_service.py)
5. [`backend/app/main.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/main.py)
6. [`backend/app/api/v1/recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py)
7. [`backend/app/intelligence/recommendation/session_learner.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/session_learner.py)
8. [`backend/app/intelligence/recommendation/constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py)
9. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)
10. [`backend/app/infrastructure/db/models.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/infrastructure/db/models.py)

#### What Lives in Each File for Module 1
* **`KioskContext.jsx`**: Holds `foodPreference` state (`"both"`, `"veg"`, `"non_veg"`). Emits preference changes to backend via `POST /session/preference` and provides `setFoodPreference` to UI buttons.
* **`Burgermenu.jsx` / `Sidesmenu.jsx`**: Renders the green "Veg" and red "Non-Veg" filter pill buttons. Binds click events directly to `setFoodPreference("veg")`. In `Sidesmenu.jsx`, resets scroll to top (`scrollTop = 0`) on filter change, renders loading/empty states, and fetches `/menu/sides?preference=veg`.
* **Category Recommendation Pages (`Burgerrepage.jsx`, `Sidesrepage.jsx`, etc.)**: Watches `foodPreference` in a `useEffect` hook. Appends `?preference=veg` to recommendation fetch queries. Includes category validation (`isSideRec` / `isBurgerRec`) to reject stale foreign category data and defensive slot backfilling so all 8 cards (`card-1` through `card-8`) remain populated.
* **`conversation_service.py`**: In `_build_screen_data()`, builds separate, pure `both`, `veg`, and `non_veg` recommendation sets for all categories (`burger`, `side`, `drink`, `dessert`). Guaranteed 2 Priority, 2 Premium, and 4 Additional vegetarian items without non-veg contamination.
* **`main.py`**:
  * Function `_filter_sections_by_pref()`: Dynamically filters catalog sections for `@app.get("/menu/burgers")`, `/menu/drinks`, `/menu/sides`, and `/menu/desserts` based on `?preference=veg|non_veg` and prunes empty sections.
  * Function `_compute_dynamic_category_merchandising()`: In `build_set()`, strictly backfills vegetarian sets from the vegetarian candidate pool without falling back to `all_items`.
* **`recommendations.py`**:
  * Function `_resolve_session()`: Automatically executes `SessionLearner.set_explicit_dietary_override(session_id, food_preference)` when preference is passed.
  * Function `get_checkout_recommendations()` & `get_product_recommendations()`: Enforces `effective_dietary_lock`. If `profile.is_explicit_override` is active, preserves explicit preference across all subsequent recommendations.
  * Endpoint `POST /api/v1/recommendations/preference`: Dedicated deterministic tool entry point for LLM/voice agents and UI toggles.
  * `FINAL HARDFILTER 1`: Evaluates every scored candidate. If `effective_dietary_lock == "veg"` and `cand.food_type != "veg"`, sets `score = 0.0` and deletes the item.
* **`session_learner.py`**:
  * In `SessionMindsetProfile`, stores `dietary_lock: str | None = None` and `is_explicit_override: bool = False`.
  * Method `set_explicit_dietary_override(session_id, dietary_pref)`: Deterministic tool entry point for voice/LLM agents or UI filter toggles. Sets `profile.dietary_lock = pref` and locks `profile.is_explicit_override = True`. Once set, implicit cart inferences will never overwrite an explicit customer choice.
* **`constraints.py`**: In `OverrideHierarchy._tier4_customer_constraints`:
  ```python
  if session.food_preference == "veg":
      if "non" in food_type or any(m in name for m in ["chicken", "mutton", "fish", "wings", "nugget", "egg"]):
          return False, "tier4_dietary_veg_lock"
  ```
* **`scoring.py`**:
  * In `RecommendationContext.__post_init__()`: Auto-resolves `dietary_lock` from `session_context` or `SessionLearner`.
  * Function `module1_dietary_lock(candidate: MenuItem, dietary_lock: str | None)`: Performs word-boundary regex and `food_type` validation. If non-veg, returns `(False, "module1_dietary_lock_violation")`.
  * In `evaluate_7tier_pipeline()`: Evaluates `module1_dietary_lock` at line 1284. Candidates that fail are dropped with `continue`.
* **`models.py`**: Defines column `food_type: Mapped[str]` on `MenuItem` table (`"veg"` vs `"non_veg"`).

#### Purpose of Each File & Blast Radius
* If you edit **`conversation_service.py`**: Controls conversational voice and category navigation screen data. If broken, voice navigation or clicking category cards on Categories page serves contaminated sets or missing slots.
* If you edit **`main.py`**: Controls catalog API endpoints and merchandising recommendation engine. If broken, catalog menus ignore `?preference` queries and serve non-veg items under veg filter.
* If you edit **`constraints.py`**: Controls the retrieval bouncer. If broken, non-veg candidates enter the scoring pool.
* If you edit **`scoring.py`**: Controls the execution bouncer. If broken, scoring will calculate points for non-veg items.
* If you edit **`recommendations.py`**: Controls API boundaries. If broken, `/checkout` or `/product/{id}` endpoints will fail to reject non-veg items even if the scoring engine flagged them.
* If you edit **`session_learner.py`**: Controls memory across screen transitions. If broken, clicking "Veg" on Burger Menu is forgotten when the user moves to the Drink or Cart screen.

---

### MODULE 2: Anti-Redundancy & Universal Side Overrides

#### Core Responsibility
Prevents recommending duplicate or clashing items from the same category (e.g., suggesting a second burger when a burger is already chosen), while explicitly **exempting** universal staple finger foods (`Fries`, `Nuggets`, `Onion Rings`) so they can always be recommended alongside mains.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/ranking.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/ranking.py)
2. [`backend/app/intelligence/recommendation/constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py)
3. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 2
* **`ranking.py` & `constraints.py`**: Defines constant `UNIVERSAL_SIDES = ["Chicken Nuggets", "Fries", "Medium Fries", "Large Fries", "Onion Rings"]`. Declares `is_universal_side(candidate)`.
* **`scoring.py`**:
  * Function `module2_anti_redundancy_score(candidate: MenuItem, anchor_item: MenuItem | None) -> float`:
    - If `candidate.name` matches `UNIVERSAL_SIDES`, returns `1.0` (zero penalty).
    - If `candidate.category == anchor_item.category` (e.g., burger suggesting burger), applies penalty: `0.30x` multiplier.
    - Lines 1405–1410 in `evaluate_7tier_pipeline`: Applies a **$1.25\times$ commercial multiplier** (`universal_side_boost`) to items with "Nugget" or "Fries" in their name.

#### Blast Radius
* Modifying `UNIVERSAL_SIDES` in `ranking.py` or `constraints.py` determines whether fries and nuggets get blocked when a chicken or potato burger is in the cart.
* Changing `module2_anti_redundancy_score` in `scoring.py` controls whether same-category upsells (e.g. burger-to-burger) are penalized or promoted.

---

### MODULE 3: Flavor Anti-Clash & Cuisine Synergy

#### Core Responsibility
1. **Anti-Clash**: Prevents flavor fatigue and palette clashes (e.g., ordering a Mango Shake should penalize a Mango Sundae to avoid double-mango saturation).
2. **Cuisine Synergy**: Enhances pairings that share cultural flavor affinity (e.g., Tandoori/Makhani items pair synergistically with Masala Fizz or Mint/Masala accompaniments).

#### All Connected Files
1. [`backend/app/intelligence/recommendation/heuristics/sensory_contrast.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/sensory_contrast.py)
2. [`backend/app/intelligence/recommendation/data_quality_gate.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/data_quality_gate.py)
3. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 3
* **`data_quality_gate.py`**: Contains `CulinaryTagger.extract_dominant_flavor(name, desc)`. Identifies flavor profiles: `mango`, `chocolate`, `berry`, `peri_peri`, `makhani`, `cheesy`, `garlic`.
* **`scoring.py`**:
  * Function `module3_flavor_anti_clash_penalty(candidate, cart_lines) -> float`: Compares candidate's dominant flavor against all items in the cart. If duplicate flavor found, applies a **$0.50\times$ penalty**.
  * Function `module3_cuisine_synergy(candidate, anchor_item, cart_lines) -> float`: Evaluates spice and ethnic style. Indian flavor pairings receive a **$1.20\times$ synergy boost**.

#### Blast Radius
* Changing `CulinaryTagger` flavor keywords in `data_quality_gate.py` changes which words trigger clashes.
* Changing penalties in `scoring.py` lines 607–640 alters how heavily double-flavor combinations are suppressed.

---

### MODULE 4: Dining Pillar Gap Analysis & Dual-Role Saturation (Milkshake Paradox)

#### Core Responsibility
Analyzes the 4 meal pillars: **[Main, Side, Drink, Dessert]**. Identifies unfilled gaps in the customer's cart and dedicates recommendation slots to complete the meal. Handles the **Dual-Role Milkshake Paradox**: thick shakes and sodas floats satisfy both **Drink** and **Dessert** simultaneously.

#### All Connected Files
1. [`backend/app/domain/catalog/entities.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/domain/catalog/entities.py)
2. [`backend/app/intelligence/recommendation/ranking.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/ranking.py)
3. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 4
* **`ranking.py`**: Implements `classify_beverage_subrole(item)` and `classify_dessert_subrole(item)`. Classifies shakes (`Berry Blast`, `KitKat Shake`, `Chocolate Shake`) as `thick_shake` (heavy dairy).
* **`scoring.py`**:
  * Function `module4_evaluate_meal_pillars(cart_lines) -> dict[str, bool]`:
    - Checks for `main`, `side`, `drink`, `dessert`.
    - **Milkshake Paradox rule**: If any cart line is a `thick_shake` or `soda_float`, it marks `pillars["drink"] = True` AND `pillars["dessert"] = True`.
  * In `evaluate_7tier_pipeline()` lines 1294–1300:
    - If `pillars["drink"] == True`, suppresses beverage candidates.
    - If `pillars["dessert"] == True`, suppresses sundaes, mousse, and shakes.

#### Blast Radius
* If `classify_beverage_subrole` in `ranking.py` is wrong, a shake might not count as a dessert, causing the kiosk to recommend a heavy sundae on top of a thick shake.
* If `module4_evaluate_meal_pillars` in `scoring.py` is changed, the checkout tray will stop prioritizing missing pillars (e.g. missing drinks).

---

### MODULE 5: Hard Price Ceiling & Elastic Anchoring

#### Core Responsibility
Prevents price shock and protects user budget elasticity. Ensures a ₹79 burger does not recommend a ₹250 dessert. Dynamically lifts the price ceiling when a premium anchor (e.g. Whopper $\ge ₹169$) or bulk cart is detected.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py)
2. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 5
* **`constraints.py`**: In `_tier4_customer_constraints`, tests `item_price > anchor_price * max_price_ratio`.
* **`scoring.py`**:
  * Function `calculate_effective_anchor(cart_lines, default_anchor) -> float`: Unrolls cart quantities (e.g. 5x ₹99 burgers $\to$ ₹495 bulk anchor spend).
  * Function `module5_hard_price_ceiling(candidate, anchor_price, is_product_page) -> tuple[bool, str]`:
    - On product page: If `anchor_price <= 150.0`, candidates cannot exceed `1.5x` anchor price.
    - Elasticity expansion: If `anchor_price >= 169.0` (Whopper class), drinks and desserts bypass price penalties (solves the Fanta Float / Thick Shake lock).
  * Function `price_proximity_score(p_cand, p_anchor, k=4.0) -> float`: Soft sigmoid decay formula for smooth non-linear price fit.

#### Blast Radius
* Tightening ratios in `module5_hard_price_ceiling` drops premium sides (like King Fries or Shakes) from budget burgers.
* Loosening ratios allows ₹250 sharing packs to be suggested to someone buying a ₹45 soft serve.

---

### MODULE 6: Condiment Host Gating & Companion Boost

#### Core Responsibility
Prevents dips, sauces, and condiments (Fiery Hell Dip, Mayo, Chilli Sauce) from crowding the recommendations tray when a customer only has a beverage or burger. Once a "host item" (French Fries, Nuggets, Wings) is added, condiments receive a massive boost.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py)
2. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 6
* **`constraints.py`**: Categorizes condiments. Suppresses condiments from initial candidate retrieval unless finger food is in the cart.
* **`scoring.py`**:
  * Function `_has_valid_condiment_host(cart_lines, anchor_item) -> bool`: Scans cart for host items (`fries`, `nugget`, `wing`, `strip`, `hashbrown`).
  * Function `module6_condiment_host_gate(candidate, cart_lines, anchor_item, has_spice_affinity) -> tuple[float, str]`:
    - If candidate is a dip and NO host exists: Returns `(0.0, "condiment_unhosted_drop")` $\to$ **Immediate drop**.
    - If candidate is a dip and host DOES exist: Returns `(1.50, "condiment_host_boost")` $\to$ **$1.50\times$ boost**.
    - **Spice affinity override**: If customer has high spice affinity (`Spice >= 4`), spicy dips (Fiery Hell Dip) bypass host gating.

#### Blast Radius
* Changing `_has_valid_condiment_host` changes which finger foods unlock dip recommendations.
* Changing `cond_mult` from `0.0` will allow dips to appear on empty cart screens.

---

### MODULE 7: Absolute Cart Exclusion (Anti-Blindness)

#### Core Responsibility
Ensures the kiosk never recommends an item the customer has already placed in their cart. Evaluates both item IDs and normalized title strings.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py)
2. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)
3. [`backend/app/api/v1/recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py)

#### What Lives in Each File for Module 7
* **`constraints.py`**: Checks `item.id in (rejected_item_ids | cart_item_ids)`.
* **`scoring.py`**:
  * Lines 1233–1246: Compiles `cart_ids` and `cart_name_set` from `context.cart_lines`.
  * Function `module7_cart_exclusion(candidate, cart_ids, cart_name_set, anchor_id) -> tuple[bool, str]`:
    - Rejects if `candidate.id in cart_ids`.
    - Rejects if `candidate.name.lower() in cart_name_set`.
    - Rejects if `candidate.id == anchor_id`.
* **`recommendations.py`**: In `get_checkout_recommendations()`, compiles `cart_ids = {i.id for i in request.cart_items}` and strips them before returning final response.

#### Blast Radius
* If this module fails or is bypassed, customers will see upsells for the exact item they just put in their tray.

---

### MODULE 8: Gatekeeper Kill-Switch (Meal Saturation)

#### Core Responsibility
Detects when a customer has reached total meal completion (Cart contains: Main + Savory Side + Drink + Dessert). When all 4 pillars are satisfied, further upsells annoy the customer. The engine immediately returns an empty recommendation list (`[]`), clearing the screen for seamless checkout.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)
2. [`backend/app/api/v1/recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py)

#### What Lives in Each File for Module 8
* **`scoring.py`**:
  * Function `module8_gatekeeper_kill_switch(pillars: dict[str, bool]) -> bool`:
    ```python
    return bool(pillars.get("main") and pillars.get("side") and pillars.get("drink") and pillars.get("dessert"))
    ```
  * In `evaluate_7tier_pipeline()` lines 1252–1254:
    ```python
    if module8_gatekeeper_kill_switch(pillars):
        return [], "module8_gatekeeper_kill_switch_fired"
    ```
* **`recommendations.py`**: In `/checkout`, catches the empty list response and returns `{"recommendations": []}`.

#### Blast Radius
* Changing `module8_gatekeeper_kill_switch` determines whether a full meal customer is shown checkout popups or goes straight to payment.

---

### MODULE 9: Margin Multiplier with Diminishing Returns

#### Core Responsibility
Gives preference to items with high gross contribution margins (beverages, fries, loaded desserts) over low-margin commodity items, weighted dynamically against the anchor item's price.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 9
* **`scoring.py`**:
  * Function `module9_margin_multiplier(candidate: MenuItem, anchor_price: float) -> float`:
    - Evaluates category margin tier: Drinks/Fries $\to$ Margin factor 1.25; Sides $\to$ 1.15; Mains $\to$ 1.05.
    - Applies diminishing returns curve $\log_{10}(\text{price})$ to avoid over-promoting high-cost, low-margin items.
  * Line 1424 in `evaluate_7tier_pipeline`: Multiplies `composite_score *= margin_mult`.

#### Blast Radius
* Adjusting multipliers in `module9_margin_multiplier` alters the profitability weighting of recommendations without affecting eligibility.

---

### MODULE 10: Sensory Contrast (Neuro-Gastronomy) & Thermal Ban

#### Core Responsibility
Implements neuro-gastronomy taste pairing:
1. **Sensory Contrast**: Spicy food demands cooling dairy or sweet soda. Heavy savory food demands salty, crispy textures.
2. **Thermal Ban ("Hot/Hot Ban")**: Recommending a piping hot espresso or hot chocolate with a piping hot flame-grilled burger during lunch/afternoon creates negative thermal balance outside of morning hours.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/heuristics/sensory_contrast.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/sensory_contrast.py)
2. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 10
* **`sensory_contrast.py`**: Defines taste profile taxonomy (`spicy`, `cooling_dairy`, `rich_savory`, `crisp_salty`).
* **`scoring.py`**:
  * Function `module10_sensory_contrast(candidate, anchor_item, cart_lines) -> float`: Returns `1.35x` for Spicy $\to$ Cooling Dairy pairing. Returns `1.25x` for Savory $\to$ Crisp Salty pairing.
  * Function `get_item_temperature(item) -> int`: Maps item IDs to thermal scale ($1=\text{Frozen/Iced}$, $5=\text{Piping Hot}$).
  * Function `module10_thermal_contrast_multiplier(candidate, anchor_item, circadian_phase) -> float`:
    - If `anchor.temp >= 4` and `candidate.temp >= 4` and `phase != "morning_rush"`, applies a **$0.50\times$ penalty** (`thermal_contrast_penalty`).

#### Blast Radius
* Modifying thermal penalties in `scoring.py` line 831 controls whether hot coffees and soups can be recommended with hot burgers in the afternoon.

---

### MODULE 11: Session Fatigue & Novelty Damping

#### Core Responsibility
Prevents recommendation banner blindness. If a customer navigates through multiple category screens and repeatedly ignores an item that was shown to them, that item receives an impression decay penalty, rotating fresh items into view.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/llm_merchandising_engine.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/llm_merchandising_engine.py)
2. [`backend/app/intelligence/recommendation/session_learner.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/session_learner.py)
3. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 11
* **`session_learner.py`**: Increments `item_impressions[item_id]` in `SessionProfile` whenever an item is returned in an API payload.
* **`scoring.py`**:
  * Function `module11_session_fatigue(session_id, item_id, candidate) -> float`:
    - Reads impressions: 1 view $\to$ `1.0x`; 2 views $\to$ `0.85x`; 3+ views $\to$ `0.65x`.
    - **Yield Override Bypass**: If an item is in high surplus stock (Module 12), fatigue penalty is 100% bypassed (`session_fatigue_overridden = True`).

#### Blast Radius
* Controls the velocity of product rotation on the screen across page clicks.

---

### MODULE 12: Circadian Craving Analyzer & Daypart Multipliers

#### Core Responsibility
Aligns recommendations with human biological meal rhythms and environmental time:
- **Morning (06:00–10:59)**: Boosts hot coffee, tea, and breakfast hashbrowns.
- **Lunch (11:00–15:59)**: Boosts hearty burgers and chilled carbonated beverages.
- **Afternoon Slump (16:00–18:59)**: Boosts iced coffees, savory snacks, and mini wraps.
- **Late Night (22:00–05:59)**: Boosts indulgent desserts, sundaes, and thick shakes.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/heuristics/circadian_clock.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/circadian_clock.py)
2. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 12
* **`circadian_clock.py`**: Class `CircadianCravingAnalyzer`. Detects system hour and resolves `circadian_phase`.
* **`scoring.py`**:
  * Function `module12_circadian_score(candidate: MenuItem, circadian_phase: str) -> float`:
    - Evaluates candidate category and keywords against current phase.
    - Applies `1.35x` for coffee in morning, `1.30x` for burger in lunch, `1.25x` for desserts late night.

#### Blast Radius
* Editing phase definitions in `circadian_clock.py` changes the time boundaries for breakfast, lunch, and late night.

---

### MODULE 13: Anti-Gamification & Sub-Role MMR Diversity

#### Core Responsibility
1. **Anti-Gamification**: Enforces strict commercial honesty. Winback logic is deactivated; the system never invents artificial discounts or rewards customers for repeatedly deleting cart items.
2. **Sub-Role MMR Diversity**: The final stage running Maximal Marginal Relevance. Evaluates granular sub-roles (`thick_shake`, `soda_float`, `hot_coffee`, `fries`, `sundae`, `sharing_bucket`) with a `0.90` similarity penalty, guaranteeing the 3-slot tray contains diverse item types.

#### All Connected Files
1. [`backend/app/intelligence/recommendation/diversity.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/diversity.py)
2. [`backend/app/intelligence/recommendation/job_config.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/job_config.py)
3. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Module 13
* **`scoring.py`**: Function `module13_anti_gamification_check(candidate) -> tuple[bool, str]`. Guarantees price integrity.
* **`job_config.py`**: Holds job-specific MMR weights: `CLOSURE` (Cart): $\lambda = 0.50$ (high diversity); `DISCOVERY`: $\lambda = 0.75$.
* **`diversity.py`**:
  * `_SUB_ROLE_RULES`: Maps item names to 27 granular sub-roles.
  * Function `compute_similarity(a, b) -> float`: Returns `0.90` if same sub-role, `0.50` if same category, `0.10` if distinct.
  * Class `MMRDiversity.rerank()`: Iteratively selects items maximizing:
    $$\text{MMR} = \lambda \cdot \text{relevance}(c) - (1 - \lambda) \cdot \max_{s \in \text{selected}} \text{similarity}(c, s)$$

#### Blast Radius
* Changing `_SUB_ROLE_RULES` in `diversity.py` changes which items are recognized as duplicates.
* Changing $\lambda$ in `job_config.py` alters how strongly the tray prioritizes diversity over score.

---

### REAL-TIME HEURISTIC LAYER: Dynamic Affinities, Sub-Role Kills & Velocity Rush

#### Core Responsibility
Processes ephemeral in-memory signals sent directly in the request payload without any database writes:
1. **Attribute Affinity (The Click Tracker)**: Detects user interaction with attributes (e.g. `Spice >= 4`) and applies a **$1.30\times$ impulse boost**.
2. **Sub-Role Rejection (The Back-Button Signal)**: When a user inspects a category (e.g. `thick_shake`, `hot_coffee`) and leaves without buying, that sub-role receives a **$0.0\times$ kill score** (immediate eradication).
3. **Cart Velocity (The Bulk Rush Indicator)**: When cart size $\ge 5$ or `velocity_state == "rushed"`, down-ranks single items ($0.40\times$) and boosts **Sharing Buckets** ($1.40\times$).

#### All Connected Files
1. [`frontend/src/context/KioskContext.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/context/KioskContext.jsx)
2. [`backend/app/api/v1/recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py)
3. [`backend/app/intelligence/recommendation/scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)

#### What Lives in Each File for Heuristics
* **`KioskContext.jsx`**: Tracks `sessionContext.active_affinity`, `sessionContext.rejected_sub_roles`, and `sessionContext.velocity_state`. Sends them in the JSON body of checkout and recommendation calls.
* **`recommendations.py`**: Extracts `session_context` from `CheckoutRecommendationRequest` and initializes `RecommendationContext`.
* **`scoring.py`**:
  * Function `evaluate_realtime_heuristics()`: Evaluates affinities, sub-role rejections, and velocity.
  * Lines 1459–1460: If `heuristics_mult == 0.0`, candidates are dropped immediately.

---

## 3. Master Module-to-File Quick Adjustment Cheatsheet

When you need to adjust any module, use this directory to target the exact file and function:

| Mod # | Name | Target File | Exact Function / Line Area | Default Multipliers / Values |
|:---:|---|---|---|---|
| **1** | **Dietary Lock** | [`constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py)<br/>[`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py) | `_tier4_customer_constraints`<br/>`module1_dietary_lock` (L337)<br/>`FINAL HARDFILTER 1` (L238) | Non-veg $\to$ **$0.0\times$ kill score** when `preference == 'veg'` |
| **2** | **Anti-Redundancy & Universal Sides** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`ranking.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/ranking.py) | `module2_anti_redundancy_score` (L577)<br/>`UNIVERSAL_SIDES` (L28) | Same-category: **$0.30\times$**;<br/>Universal side: **$1.25\times$** boost |
| **3** | **Flavor Anti-Clash & Synergy** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`data_quality_gate.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/data_quality_gate.py) | `module3_flavor_anti_clash_penalty` (L607)<br/>`CulinaryTagger` (L154) | Duplicate flavor: **$0.50\times$** penalty;<br/>Synergy: **$1.20\times$** boost |
| **4** | **Dining Pillars & Dual-Role (Shake)** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`ranking.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/ranking.py) | `module4_evaluate_meal_pillars` (L400)<br/>`classify_beverage_subrole` | Shake = Drink + Dessert fulfilled;<br/>Pillar gap boost: **$1.40\times$** |
| **5** | **Hard Price Ceiling & Elasticity** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py) | `module5_hard_price_ceiling` (L497)<br/>`calculate_effective_anchor` (L457) | Budget anchor ($\le ₹150$): max **$1.5\times$**;<br/>Premium ($\ge ₹169$): elasticity unlocked |
| **6** | **Condiment Gating & Host Boost** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `module6_condiment_host_gate` (L675)<br/>`_has_valid_condiment_host` (L658) | No host: **$0.0\times$ drop**;<br/>Host in cart: **$1.50\times$ boost** |
| **7** | **Cart Exclusion** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py) | `module7_cart_exclusion` (L367)<br/>`get_checkout_recommendations` | Item in cart $\to$ **$0.0\times$ drop** (excluded by ID & normalized name) |
| **8** | **Gatekeeper Kill-Switch** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `module8_gatekeeper_kill_switch` (L444) | All 4 pillars filled $\to$ Return **`[]`** immediately (halts scoring) |
| **9** | **Margin Multiplier** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `module9_margin_multiplier` (L525) | Drinks/Sides: **$1.15\times$–$1.25\times$**; Mains: **$1.05\times$** |
| **10** | **Sensory Contrast & Thermal Ban** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`sensory_contrast.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/sensory_contrast.py) | `module10_sensory_contrast` (L711)<br/>`module10_thermal_contrast_multiplier` (L831) | Spicy $\to$ Cooling Dairy: **$1.35\times$**;<br/>Hot/Hot penalty: **$0.50\times$** |
| **11** | **Session Fatigue / Novelty** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`session_learner.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/session_learner.py) | `module11_session_fatigue` (L875) | 1 view: **$1.0\times$**; 2 views: **$0.85\times$**; 3+ views: **$0.65\times$** |
| **12** | **Circadian Craving Analyzer** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py)<br/>[`circadian_clock.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/circadian_clock.py) | `module12_circadian_score` (L893)<br/>`CircadianCravingAnalyzer` | Morning: Coffee **$1.35\times$**; Lunch: Burger **$1.30\times$**; Late: Dessert **$1.25\times$** |
| **13** | **Anti-Gamification & MMR Diversity** | [`diversity.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/diversity.py)<br/>[`job_config.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/job_config.py)<br/>[`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `MMRDiversity.rerank`<br/>`_SUB_ROLE_RULES`<br/>`module13_anti_gamification_check` (L559) | Same sub-role penalty: **$0.90$**;<br/>Cart MMR $\lambda = 0.50$ (high diversity) |
| **H1** | **Attribute Affinity (Spice)** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_realtime_heuristics` (L1020) | Active tag match (`Spice >= 4`): **$1.30\times$ impulse boost** |
| **H2** | **Sub-Role Rejection Kill** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_realtime_heuristics` (L1020) | Rejected sub-role: **$0.0\times$ kill score** (immediate drop) |
| **H3** | **Cart Velocity (Bulk Mode)** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_7tier_pipeline` (L1318) | Rushed/Bulk: Sharing bucket **$1.40\times$**; single item **$0.40\times$** |

---

## 4. End-to-End Session Reset & Cancel Order Flow

1. **User Action**:
   - On the **Categories Page** ([`Categories.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Categories.jsx)): The customer taps the prominent **Exit Session** button (`.exit-kiosk-btn`), immediately ending the session and returning to the Welcome screen.
   - On **Inner Pages** ([`Header.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/components/Header.jsx)): The customer taps **Cancel Order** (`.cancel-order-btn`).
2. **Backend Wipe**:
   - Calls `POST /session/reset` with the current `session_id`.
   - `SessionLearner.clear_profile(session_id)` completely deletes active affinities, dietary locks, impression histories, and mindset.
   - `CartService.clear_cart(session_id)` clears all backend cart lines.
3. **Frontend State Purge**:
   - `clearCart()` sets local cart lines to `[]`, count to `0`, total to `₹0`.
   - `resetSessionState()` resets `foodPreference` back to `"both"`, clears `sessionStorage.removeItem("dietary_preference")`, and resets all heuristics.
   - `resetSessionId()` purges both `localStorage` and `sessionStorage`, issuing a brand-new kiosk session ID.
4. **Navigation**: Routes immediately to the welcome touch screen (`/` [`Home.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Home.jsx)).

---

## 5. System-Wide Cross-Screen Dietary Lock (Veg / Non-Veg / Both)

When a customer or LLM/voice agent selects a dietary filter (e.g. `veg`) on **any** page (Burger, Sides, or Voice), the choice becomes an explicit dietary lock persisted throughout the kiosk session:

1. **State Persistence**:
   - `KioskContext.jsx` saves to React state and `sessionStorage.setItem("dietary_preference", pref)`.
   - Fires `POST /session/preference` to lock `profile.dietary_lock = "veg"` and `profile.is_explicit_override = True` on backend.
2. **Burger Recommendation & Catalog Pages**:
   - [`Burgerrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Burgerrepage.jsx): Active filter highlights `Veg`; displays only veg burger cards from `data.veg`.
   - [`Burgermenu.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Burgermenu.jsx): Re-queries `/menu/burgers?preference=veg` and client-filters sections.
3. **Sides Recommendation & Catalog Pages**:
   - [`Sidesrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Sidesrepage.jsx): Equipped with matching `<Menufilters>` (`All`, `Veg`, `Non-Veg`), initializes `selectedType` to session `foodPreference`, queries `/recommendations/category/side?preference=veg`, and enforces client-side tri-state guards. Non-veg items (wings, nuggets) are strictly excluded.
   - [`Sidesmenu.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Sidesmenu.jsx): Re-queries `/menu/sides?preference=veg`; SpotlightShelf filters to veg items.
4. **Meal Flow & Product Detail**:
   - [`ProductPage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/ProductPage.jsx): Passes `preference: foodPreference` in `POST /meal/options`; filters companion recommendations to veg.
   - [`MealPage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Mealpage.jsx): Filters `side_options` so only vegetarian sides (Fries, Hashbrowns, Dips) render; automatically auto-swaps non-veg default sides to veg.
5. **Cart & Pre-Checkout**:
   - [`CartPage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/CartPage.jsx): Passes `preference` to `/recommendations/checkout`; applies client-side dietary guard so no non-veg impulse items appear.

---

## 6. Resolution of Sides Async State Reconciliation & Layout Collapse

### Observed Symptom
When a customer selected "Veg" on the Burger page and navigated to the Sides page:
1. The top "Curated for you" / Spotlight shelf rendered 2 cards as expected.
2. The catalog sections directly below rendered as completely blank white space.
3. Hard-refreshing the browser immediately resolved the issue.

### Root Cause Audit
1. **Multi-Set Omission in Conversational / Category Routing**: In `backend/app/application/conversation_service.py` (`_build_screen_data`), the multi-set logic (`both`, `veg`, `non_veg`) was only implemented for `category == "burger"`. When a user transitioned to Sides via Category selection (`handleCategoryClick("side")` -> `sendMessage("I want a side")`), the backend returned only flat `priority`, `premium`, and `additional` sets without `data.veg`. The top 2 priced sides (`Chicken Wings`, `Chicken Nuggets`) were non-veg, so filtering for `veg` wiped out `premium` completely, causing the middle shelf to collapse into blank space.
2. **Stale Cross-Category State in Repages**: In `frontend/src/Pages/Sidesrepage.jsx` and `Burgerrepage.jsx`, `recommendationData?.data` took precedence over `fallbackData` without verifying if `recommendationData` actually belonged to the active category. If a user previously navigated through Burgers, stale burger recommendations polluted the Sides page until a hard refresh cleared React state.
3. **Dietary Contamination in Backend `build_set`**: In `backend/app/main.py` (`_compute_dynamic_category_merchandising`), `build_set(lst)` fell back to `all_items` when candidate pools were short, inadvertently injecting non-veg items into `data.veg`. When the frontend stripped these non-veg items, card slots were left empty.
4. **Backend Catalog Preference Ignored**: `@app.get("/menu/sides")` and other category endpoints did not accept a `preference` query parameter, returning unfiltered menus to `Sidesmenu.jsx`.
5. **Scroll Retainment & Missing Loading States**: `Sidesmenu.jsx` lacked a scroll reset (`scrollTop = 0`) on filter change/mount and lacked a loading indicator, meaning any async fetch latency left the container blank or scrolled down into empty bottom padding.

## 7. Resolution of Repeat Navigation Slot Skipping & In-Memory Client Caching

### Observed Symptom
When a customer repeatedly navigated back and forth between screens (e.g. Burger -> Sides -> Burger -> Sides), the 4-card bottom shelf (`card-5` to `card-8`) on the Sides recommendation screen intermittently skipped product cards or showed fewer items, but hard-refreshing (F5) restored all cards.

### Root Cause
1. In `backend/services/menuservice.py`, `build_category_response()` was returning only flat `priority`, `premium`, and `additional` lists without separating `data.veg` and `data.both`. Because the overall sides menu contains chicken items, `additional` was populated almost entirely with non-veg chicken items. When the user was locked in `veg`, the frontend filtered those items out, leaving `moreSides` with 0 veg items.
2. In `Sidesrepage.jsx`, `recommendationData?.data` took precedence over `fallbackData`. Since `recommendationData` from `POST /message` lacked `data.veg`, `moreSides` was empty. On page refresh, `recommendationData` in React state reset to `null`, forcing a fetch to `/recommendations/category/side` which had `data.veg`, making cards appear only on refresh.
3. Rapid repeated navigation suffered from network race conditions where asynchronous fetch promises resolved after render.

### Architectural Fixes Applied
1. **Multi-Set Backend Generation (`menuservice.py`)**: `build_category_response()` now generates complete `both`, `veg`, and `non_veg` datasets with guaranteed 2 Priority, 2 Premium, and 4 Additional items for all categories (`side`, `drink`, `dessert`).
2. **In-Memory Client Cache (`window.__CATEGORY_CACHE__`)**: `Sidesrepage.jsx` and `Burgerrepage.jsx` now cache category datasets in memory. Subsequent visits load instantly in 0ms without waiting for network roundtrips.
3. **Guaranteed 4-Card Slot Backfill**: Both `Sidesrepage.jsx` and `Burgerrepage.jsx` enforce that if `moreSides.length < 4`, candidate pools recycle valid items so all 4 card slots are 100% filled on every single visit.
4. **Production Build Verified**: Verified `npm run build` with 0 errors and tested backend endpoints with live Supabase data.

