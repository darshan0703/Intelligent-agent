# RECOMMENDATION SYSTEM ARCHITECTURE, MODULE LOGIC & PORTING BLUEPRINT

## 1. Goal & Executive Scope
This document is the **single source of truth** for the TheAtom Recommendation Engine. It is engineered so that:
1. **Portability**: Anyone can connect this recommendation engine to an entirely new backend (e.g. Node.js, Go, Spring, or another Python framework) and a new frontend (React Native, Vue, Flutter, Next.js) with zero ambiguity.
2. **Logic & Pipeline Clarity**: Explains whether modules run step-by-step, short-circuit, or run simultaneously, and how scores are calculated and ranked.
3. **Module-to-File Quick Adjustment Cheatsheet**: Maps every module (1 to 13) directly to its target file, function, and tunable parameters so adjustments can be made immediately without re-analyzing the codebase.
4. **System-Wide Veg Lock & Session Lifecycle**: Explains the global Cancel Order / Start Over mechanics and permanent dietary locking.

---

## 2. Portability Blueprint: How to Connect to ANY Backend & Frontend

If you are porting this engine or connecting a new frontend/backend, the system expects these exact database entities, API contracts, and frontend communication flows.

### A. Database Contract (Required Schema & Properties)

#### 1. Table: `menu_items`
| Column Name | Type | Description | Why It Matters to Recommendations |
|---|---|---|---|
| `id` | `INTEGER` (PK) | Unique item identifier | Used for candidate matching, cross-sell queries, cart exclusion |
| `name` | `VARCHAR(100)` | Full item title (e.g. "Veg Whopper") | Used for keyword extraction, flavor profiling, anti-clash |
| `short_description` | `TEXT` | Brief summary (e.g. "Flame grilled patty") | Natural language pairing signals |
| `long_description` | `TEXT` | Descriptive text | Used by NLP / culinary tagger |
| `price` | `NUMERIC(10,2)` | Base selling price (never float) | Module 4 elastic price proximity ceiling |
| `category` | `VARCHAR(50)` | `burger`, `side`, `drink`, `dessert` | Module 2 dining pillar assignment |
| `food_type` | `VARCHAR(20)` | `veg` or `non_veg` | Module 1 strict dietary lock |
| `serving_type` | `VARCHAR(20)` | `hot`, `cold`, `iced`, `ambient` | Module 3 sensorial temperature pairing |
| `meal_role` | `VARCHAR(20)` | `main`, `side`, `drink`, `dessert` | Meal completeness detection |
| `is_available` | `BOOLEAN` | True if item can be sold | Tier 2 Transaction Correctness gate |
| `image` | `VARCHAR(255)` | Relative or absolute image URI | Rendered in recommendation card |
| `display_order` | `INTEGER` | Merchandising sort order | Popularity proxy & Level 5 fallback |

#### 2. Table: `inventory`
| Column Name | Type | Description |
|---|---|---|
| `item_id` | `INTEGER` (FK) | Reference to `menu_items.id` |
| `branch_id` | `INTEGER` | Kiosk store location |
| `stock` | `INTEGER` | Current inventory count ($\le 0$ triggers Tier 2 hard drop; high stock triggers Module 12 overstock boost) |

#### 3. Table: `cross_sells`
| Column Name | Type | Description |
|---|---|---|
| `source_item_id` | `INTEGER` (FK) | Item in cart or viewed (e.g. Veg Whopper) |
| `recommended_item_id` | `INTEGER` (FK) | Complementary pairing (e.g. King Fries, Coke) |
| `priority` | `INTEGER` | Editorial ranking order |

---

### B. API Gateway Contract (HTTP Endpoints)

#### 1. `POST /api/v1/recommendations/checkout`
Used when the user views the cart or checkout drawer to fill missing dining pillars.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "session_id": "uuid-string-or-kiosk-id",
    "cart_items": [
      {
        "id": 7,
        "name": "Veg Whopper",
        "price": 179.0,
        "quantity": 1,
        "category": "burger",
        "food_type": "veg"
      }
    ],
    "preference": "veg",
    "session_context": {
      "active_affinity": { "Spice": 4 },
      "rejected_sub_roles": ["thick_shake"],
      "velocity_state": "normal"
    }
  }
  ```
- **Response Body**:
  ```json
  {
    "recommendations": [
      {
        "id": 19,
        "name": "King Fries",
        "price": 115.0,
        "category": "side",
        "food_type": "veg",
        "badge": "⭐ Best Match",
        "reason": "Classic crisp companion for flame-grilled burger",
        "score": 1.82
      }
    ],
    "dietary_lock": "veg"
  }
  ```

#### 2. `GET /api/v1/recommendations/product/{item_id}`
Used on the Product Detail Modal ("Pairs Best With" tray).
- **Query Params**: `session_id=<string>`, `preference=veg|non_veg|both`, `limit=3`
- **Returns**: Top-3 pairing items with sensory contrast and price elasticity applied against `{item_id}` as the anchor.

#### 3. `POST /api/v1/session/reset`
Used by the Exit / Cancel Order button to purge short-term memory.
- **Request Body**: `{ "session_id": "..." }`
- **Action**: Wipes `SessionLearner` profile and resets in-memory cart lines.

---

### C. Frontend Connection Contract

To connect any frontend:
1. **Session Keeper**: Store `atom_session_id` in `sessionStorage` and `localStorage`. When the app loads, generate a UUIDv4 if none exists.
2. **Dietary Preference Listener**: When the user clicks the "Veg" tab/pill, set `foodPreference = "veg"`. Every subsequent API call must append `?preference=veg` or send `"preference": "veg"`.
3. **Cart Emitter**: When cart state changes, broadcast `cart_items` to the recommendation hook/drawer.
4. **Exit Button**: Render an "✕ Cancel Order" button in the navigation header. On click, call `POST /api/v1/session/reset`, reset frontend cart to `[]`, regenerate `session_id`, and route to `/`.

---

## 3. How the Pipeline Executes: Step-by-Step vs Simultaneous

The recommendation pipeline does **NOT** run all checks simultaneously in a chaotic manner. It executes in **4 strict sequential phases**:

```
[ Incoming Request ]
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ PHASE 1: Quota-Bounded Retrieval (Candidate Gathering)  │
│  - co_purchase generator  (up to 6 items)              │
│  - semantic_fit generator (up to 8 items)              │
│  - popularity generator   (up to 4 items)              │
│  - exploration generator  (up to 2 items)              │
│  Pool Size: ~20 candidates                              │
└────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ PHASE 2: Hard Constraint Bouncers (Strict Short-Circuit)│
│  * Sequential Pass / Fail Gates *                      │
│  Tier 1: Safety & Legal (Price > 0, non-corrupted)     │
│  Tier 2: Transaction Correctness (Available & In Stock)│
│  Tier 3: Operator Business Policy (Not suppressed)    │
│  Tier 4: Customer Constraints:                         │
│          - Strict Veg Lock (Drop non-veg immediately)  │
│          - Cart Exclusion (Drop item if already in cart│
│          - Price Ceiling (Drop if > 2.5x anchor price) │
│  >> If candidate FAILS any gate: KILLED IMMEDIATELY.   │
│     (Bypasses scoring; 0 CPU wasted on rejected items) │
└────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ PHASE 3: Multiplicative Scoring Engine (Evaluated on   │
│          all surviving candidates)                     │
│  Base Score = Popularity Weight + Baseline Trust       │
│  × Module 2: Dining Pillar Gap Boost   (1.4x)          │
│  × Module 3: Sensorial Pairing Boost    (1.35x)        │
│  × Module 5: Circadian Time Boost      (1.25x)         │
│  × Module 6: Real-Time Dynamic Affinity (1.3x)         │
│  × Module 7: Sub-Role Rejection Kill   (0.0x -> Drop)  │
│  × Module 9: Companion Condiment Boost (1.5x)          │
│  × Module 10: Anti-Clash Cannibalization (0.5x)        │
│  × Module 11: Cart Velocity Bulk Boost (1.4x)          │
│  × Module 12: Overstock Surplus Boost  (1.2x)          │
│  Each candidate receives a final composite score.      │
└────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ PHASE 4: MMR Diversity Re-Ranking & Badge Attachment   │
│  - Re-ranks candidates using Sub-Role Similarity       │
│  - Prevents 2 identical sub-roles (e.g. 2 shakes)      │
│  - Selects Top-K highest diverse items (Top 3 for tray)│
│  - Attaches human badges ("⭐ Best Match", "❄️ Calms...")│
└────────────────────────────────────────────────────────┘
        │
        ▼
[ Return Final JSON Response to Frontend ]
```

### Key Execution Rules
- **Short-Circuit Bouncers (Phase 2)**: Step-by-step. If candidate fails Tier 1, it never sees Tier 2. If it fails the Veg Lock, it is dropped instantly.
- **Scoring Pipeline (Phase 3)**: Evaluated for each surviving candidate. Multipliers chain together:
  $$\text{Final Score} = \text{Base} \times M_2 \times M_3 \times M_5 \times M_6 \times M_9 \times M_{10} \times M_{11} \times M_{12}$$
  If any module sets a **$0.0\times$ kill score** (e.g. Sub-Role Rejection), the candidate's total score drops to zero and it is pruned.
- **Highest Score Wins (Phase 4)**: The top-ranking candidates are chosen, tempered by MMR diversity to guarantee visual variety across food categories.

---

## 4. Module-to-File Quick Adjustment Cheatsheet

Use this table when making adjustments to any module. You do **not** need to re-read or analyze the whole codebase—go directly to the target file and function:

| Module # & Name | Target File | Function / Section to Edit | Configurable Parameters / Multipliers |
|---|---|---|---|
| **Module 1: Strict Dietary Lock** | [`constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py), [`session_learner.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/session_learner.py) & [`recommendations.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/api/v1/recommendations.py) | `_tier4_customer_constraints`, `set_explicit_dietary_override` & `FINAL HARDFILTER 1` | `pref == 'veg'`, `food_type != 'veg'` $\to$ Drop immediately. `is_explicit_override = True` locks session. |
| **Module 2: Dining Pillar Gap Analysis** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_meal_completer_module` | Missing pillar boost: `1.40x`. Pillars: `burger`, `side`, `drink`, `dessert`. |
| **Module 3: Sensorial Pairing & Contrast** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) & [`sensory_contrast.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/sensory_contrast.py) | `evaluate_sensory_contrast_module` | Spicy $\to$ Cooling Dairy: `1.35x`. Savory $\to$ Crisp Salty: `1.25x`. Clash: `0.50x`. |
| **Module 4: Elastic Price Ceiling** | [`constraints.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/constraints.py) | `_tier4_customer_constraints` | Budget anchor ($\le ₹150$): max ratio `2.5x`. Premium anchor: max ratio `2.0x`. |
| **Module 5: Daypart / Circadian Clock** | [`circadian_clock.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/heuristics/circadian_clock.py) | `get_circadian_boost` | Morning (6–11h): Coffee/Hashbrowns `1.35x`. Lunch (11–16h): Burger `1.3x`. Late (22h+): Dessert `1.25x`. |
| **Module 6: Real-Time Dynamic Affinity** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_7tier_pipeline` | `active_affinity` match (e.g. `Spice >= 4`): `1.30x` impulse multiplier. |
| **Module 7: Sub-Role Rejection (Kill-Score)** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_7tier_pipeline` | `rejected_sub_roles` match: `0.0x` kill score (immediate drop). |
| **Module 8: Universal Kraving Anchors** | [`ranking.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/ranking.py) | `UNIVERSAL_SIDES` | Staple list: `["fries", "nuggets", "onion rings"]`. Bypasses role clash. |
| **Module 9: Companion Condiment Boost** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_condiment_host_boost` | Host in cart (Fries/Nuggets) $\to$ Dips get `1.50x`. No host $\to$ Dips suppressed (`0.20x`). |
| **Module 10: Anti-Clash Cannibalization** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_flavor_anti_clash` | Double flavor saturation (e.g. Mango Shake + Mango Sundae): `0.50x` penalty. |
| **Module 11: Cart Velocity & Bulk Sharing** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_7tier_pipeline` | `velocity_state == "rushed"` / bulk $\ge 5$: Sharing buckets `1.40x`, single items `0.40x`. |
| **Module 12: Yield Overstock Boost** | [`scoring.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/scoring.py) | `evaluate_yield_management` | Surplus stock / near-expiry items: `1.20x` promotion multiplier. |
| **Module 13: Sub-Role MMR Diversity** | [`diversity.py`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/backend/app/intelligence/recommendation/diversity.py) | `MMRDiversity.rerank` | Same sub-role penalty: similarity `0.90`. `CLOSURE` $\lambda = 0.50$, `DISCOVERY` $\lambda = 0.75$. |

---

## 5. Session State Persistence & Exit Flow

### A. How Session State is Preserved
1. **Ephemeral Memory (`SessionLearner`)**: Lives in backend memory (`_session_profiles[session_id]`). Tracks `dietary_lock`, `is_explicit_override`, `active_affinities`, `dismissed_ids`, and `basket_intent`.
2. **Dual-Storage Frontend Sync**: [`session.js`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/utils/session.js) mirrors `session_id` and `dietary_preference` between `sessionStorage` and `localStorage`. Even if the user refreshes the page or navigates between categories, the session identity and dietary lock remain intact.
3. **Cross-Page Dietary Lock (Burgers $\to$ Sides $\to$ Meals $\to$ Cart)**:
   - Once set to `"veg"` on any page (Burger menu/repage or Sides menu/repage), `SessionLearner.set_explicit_dietary_override(session_id, "veg")` locks the session.
   - **Sides Recommendation Page** ([`Sidesrepage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Sidesrepage.jsx)): Renders with `<Menufilters>` active on "Veg", queries `/recommendations/category/side?preference=veg`, and enforces client-side tri-state guards to guarantee only veg sides (Fries, Hashbrowns, Dips) are presented.
   - **Meal Builder** ([`MealPage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Mealpage.jsx) & [`MealPopup.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/components/MealPopup.jsx)): Filters `side_options` so only vegetarian sides appear; automatically replaces non-veg default sides with veg sides.
   - **Pre-Checkout** ([`CartPage.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/CartPage.jsx)): Companion recommendations and checkout suggestions drop non-veg candidates.

### B. Exit Session & Cancel Order Trigger Flow
1. **Categories Page**: Located prominently on [`Categories.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/Pages/Categories.jsx) as `"🚪 Exit Session"`.
2. **Inner Pages**: Located in [`Header.jsx`](file:///C:/Users/Hemanth%20Raju%20N/Downloads/Working%20Model/TheAtom/frontend/src/components/Header.jsx) as `"✕ Cancel Order"`.
3. **Backend Wipe**: Calls `POST /session/reset`, triggering `SessionLearner.clear_profile(session_id)` and clearing cart lines.
4. **Frontend Wipe**:
   - `clearCart()` sets cart lines to `[]`, count to `0`, total to `0`.
   - `resetSessionState()` sets `foodPreference = "both"`, clears `sessionStorage.removeItem("dietary_preference")`, and clears recommendation caches.
   - `resetSessionId()` cleans storage and issues a brand-new kiosk session ID.
5. **Redirect**: Navigates to `/` (Welcome Touch Screen).

---

## 6. Maintenance & Future Updates
This document will be updated whenever:
- A new recommendation module or heuristic is introduced.
- Multipliers, thresholds, or sub-role taxonomy rules are modified.
- Database schemas or API contracts are altered.
