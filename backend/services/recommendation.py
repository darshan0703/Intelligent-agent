from datetime import date, datetime

from services.menu_service import get_available, get_category
from services.modules.m01_dietary_lock import apply_dietary_lock
from services.modules.m07_cart_exclusion import exclude_cart_items
from services.modules.m05_budget_ceiling import apply_price_ceiling
from services.modules.m06_condiment_gating import filter_for_recommendation_page


# =========================================================
# DATE & NUMERIC HELPERS
# =========================================================

def _parse_expiry_date(expiry):
    """
    Safely normalizes expiry into a datetime.date object.
    Returns: (parsed_date: date | None, is_valid: bool)
      - If expiry is None or '': returns (None, True) -> treated as no expiry specified.
      - If isinstance(expiry, datetime): returns (expiry.date(), True)
      - If isinstance(expiry, date): returns (expiry, True)
      - If isinstance(expiry, str): tries ISO format (with optional Z/offset) and YYYY-MM-DD.
          Returns (parsed_date, True) on success, (None, False) on failure.
      - Any other type: returns (None, False).
    """
    if expiry is None or expiry == "":
        return None, True

    if isinstance(expiry, datetime):
        return expiry.date(), True

    if isinstance(expiry, date):
        return expiry, True

    if isinstance(expiry, str):
        s = expiry.strip()
        if not s:
            return None, True
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s).date(), True
        except (ValueError, TypeError):
            pass
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date(), True
        except (ValueError, TypeError):
            pass
        return None, False

    return None, False


def _is_expiry_eligible(item, today):
    """
    Checks if an item is eligible based on expiry date:
      - Missing/None expiry: eligible (standard non-perishable/untracked item).
      - Invalid/malformed expiry: ineligible (safe policy: do not treat unparseable dates as valid).
      - Expired (date < today): ineligible.
      - Future or today (date >= today): eligible.
    """
    if not isinstance(item, dict):
        return False

    expiry = item.get("expiry")
    if expiry is None or expiry == "":
        return True

    parsed_date, is_valid = _parse_expiry_date(expiry)
    if not is_valid:
        return False

    if parsed_date is not None and parsed_date < today:
        return False

    return True


def _parse_stock(stock_val):
    if stock_val is None:
        return None
    try:
        return float(stock_val)
    except (ValueError, TypeError):
        return None


def _is_stock_eligible(item):
    """
    Checks if an item has positive available stock.
    Items with zero, negative, missing, or malformed stock are ineligible across all tiers.
    """
    if not isinstance(item, dict):
        return False
    val = _parse_stock(item.get("stock"))
    return val is not None and val > 0


# =========================================================
# PRIORITY CALCULATION
# =========================================================

def get_priority_items(menu):
    today = date.today()

    for item in menu:
        if not isinstance(item, dict):
            continue

        expiry = item.get("expiry")
        parsed_date, is_valid = _parse_expiry_date(expiry)

        if is_valid and parsed_date is not None:
            days_to_expiry = (parsed_date - today).days
            if days_to_expiry >= 0:
                expiry_score = max(0, 30 - days_to_expiry)
            else:
                expiry_score = 0
        else:
            expiry_score = 0

        # Safe stock parsing
        raw_stock = item.get("stock")
        try:
            stock_score = float(raw_stock) if raw_stock is not None else 0.0
            if stock_score < 0:
                stock_score = 0.0
        except (ValueError, TypeError):
            stock_score = 0.0

        # Safe score parsing
        raw_score = item.get("score")
        try:
            score_multiplier = float(raw_score) if raw_score is not None else 1.0
            if score_multiplier < 0:
                score_multiplier = 0.0
        except (ValueError, TypeError):
            score_multiplier = 0.0

        item["priority"] = (
            stock_score + expiry_score
        ) * score_multiplier

    return sorted(
        menu,
        key=lambda x: x.get("priority", 0.0) if isinstance(x, dict) else 0.0,
        reverse=True
    )


# =========================================================
# FOOD TYPE NORMALIZATION
# =========================================================

def normalize_food_type(food_type):
    normalized = (
        str(food_type or "")
        .lower()
        .replace("-", "_")
        .strip()
    )

    if normalized in ("non_veg", "non veg"):
        return "non_veg"

    if normalized == "veg":
        return "veg"

    if normalized in ("hot", "cold"):
        return normalized

    if normalized == "both":
        return "both"

    return normalized

# =========================================================
# RECOMMENDATION ENGINE
# =========================================================

def build_recommendations(
    items,
    food_type="both",
    cart=None
):
    """
    Builds 3 recommendation tiers:

        priority
        premium
        additional

    Module 1 dietary lock is applied before
    recommendation scoring.

    For "both":

        priority   -> 1 veg + 1 non-veg
        premium    -> 1 veg + 1 non-veg
        additional -> remaining items

    For "veg":

        priority   -> top 2 veg
        premium    -> next 2 by price
        additional -> next 4

    For "non_veg":

        priority   -> top 2 non-veg
        premium    -> next 2 by price
        additional -> next 4

    No item can appear in more than one tier.
    """

    # -----------------------------------------------------
    # CART
    # -----------------------------------------------------

    if cart is None:

        try:
            from state import conversation_context

            cart = conversation_context.get(
                "cart",
                []
            )

        except Exception:

            cart = []


    # -----------------------------------------------------
    # DIETARY LOCK
    # -----------------------------------------------------

    normalized_type = normalize_food_type(
        food_type
    )

    preference = (
        None
        if normalized_type == "both"
        else normalized_type
    )

    filtered = apply_dietary_lock(
        items,
        preference=preference,
        cart=cart or []
    )

    # -----------------------------------------------------
    # CART EXCLUSION (MODULE 7)
    # -----------------------------------------------------
    filtered = exclude_cart_items(
        filtered,
        cart=cart or []
    )

    if not filtered:
        return [], [], []

    # -----------------------------------------------------
    # CONDIMENT + MEAL-ONLY GATING (MODULE 6)
    # Drops: condiments/dips (checkout-only) and 0-price meal-only items
    # -----------------------------------------------------
    filtered = filter_for_recommendation_page(filtered)

    if not filtered:
        return [], [], []

    # -----------------------------------------------------
    # EXPIRY & DEFENSIVE STOCK CHECK
    # Exclude expired items, invalid expiry dates, and zero/negative/invalid stock
    # -----------------------------------------------------
    today = date.today()
    filtered = [
        item for item in filtered
        if _is_stock_eligible(item) and _is_expiry_eligible(item, today)
    ]

    if not filtered:
        return [], [], []

    # =====================================================
    # STATISTICAL PERCENTILE PRICE TIER PARTITIONING
    # Dynamically partitions ANY category (Burgers, Sides, Drinks, Desserts)
    # using price distribution percentiles — ZERO hardcoded numbers.
    # =====================================================
    candidates = filtered
    _prices = sorted([float(i.get("price") or 0) for i in candidates if i.get("price")])
    
    if _prices:
        p_min = _prices[0]
        p_max = _prices[-1]
        # P75 (Upper Quartile): Premium threshold (top 30% of category price range)
        p_75_idx = int(len(_prices) * 0.70)
        p_75 = _prices[min(p_75_idx, len(_prices) - 1)]
        # P40 (Mid Quartile): Popular threshold (excludes bottom 40% cheapest budget items)
        p_40_idx = int(len(_prices) * 0.40)
        p_40 = _prices[min(p_40_idx, len(_prices) - 1)]
    else:
        p_min = p_max = p_75 = p_40 = 0.0

    premium_floor = p_75
    popular_floor = p_40

    # =====================================================
    # BUDGET-AWARE CANDIDATES (MODULE 5) FOR PRIORITY
    # Popular tier: Excludes bottom 40% cheapest entry items
    # =====================================================
    budget_candidates = apply_price_ceiling(candidates, cart=cart or [])
    cand_pool = budget_candidates if budget_candidates else candidates
    popular_candidates = [i for i in cand_pool if float(i.get("price") or 0) >= popular_floor]
    if not popular_candidates:
        popular_candidates = cand_pool

    # Module A: Apply soft sensory contrast ranking to popular candidate pool
    from services.modules.m02_m03_basket_completion import rank_candidates_with_sensory
    popular_candidates = rank_candidates_with_sensory(popular_candidates, cart=cart or [], placement="normal")
    priority_pool = get_priority_items(popular_candidates)

    # =====================================================
    # SINGLE / ALREADY FILTERED TYPE (veg, non_veg, hot, cold)
    # =====================================================
    if normalized_type in ("veg", "non_veg", "hot", "cold"):
        priority = priority_pool[:2]
        if len(priority) < 2:
            used = {x.get("id") or x.get("name") for x in priority}
            for it in get_priority_items(cand_pool):
                if (it.get("id") or it.get("name")) not in used:
                    priority.append(it)
                    if len(priority) == 2:
                        break

        used_ids = {item.get("id") or item.get("name") for item in priority}

        # Premium candidates: price >= premium_floor sorted DESCENDING (highest price & margin items first)
        prem_items = [
            item for item in candidates
            if (item.get("id") or item.get("name")) not in used_ids
            and float(item.get("price") or 0) >= premium_floor
        ]
        prem_items = sorted(prem_items, key=lambda x: float(x.get("price") or 0), reverse=True)

        # Fallback: if no item >= floor, take top costliest sorted descending
        if not prem_items:
            all_sorted = sorted(
                [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids],
                key=lambda x: float(x.get("price") or 0),
                reverse=True
            )
            prem_items = all_sorted

        premium = prem_items[:2]
        if len(premium) < 2:
            rem_by_price = sorted(
                [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids and (item.get("id") or item.get("name")) not in {p.get("id") or p.get("name") for p in premium}],
                key=lambda x: float(x.get("price") or 0),
                reverse=True
            )
            for it in rem_by_price:
                premium.append(it)
                if len(premium) == 2:
                    break

        for p in premium:
            used_ids.add(p.get("id") or p.get("name"))

        additional = [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids][:4]
        return priority[:2], premium[:2], additional[:4]

    # =====================================================
    # BOTH (VEG + NON-VEG)
    # =====================================================
    veg_items = [item for item in candidates if normalize_food_type(item.get("foodType") or item.get("food_type")) == "veg"]
    non_veg_items = [item for item in candidates if normalize_food_type(item.get("foodType") or item.get("food_type")) == "non_veg"]

    if not veg_items or not non_veg_items:
        priority = priority_pool[:2]
        if len(priority) < 2:
            used = {x.get("id") or x.get("name") for x in priority}
            for it in get_priority_items(cand_pool):
                if (it.get("id") or it.get("name")) not in used:
                    priority.append(it)
                    if len(priority) == 2:
                        break

        used_ids = {item.get("id") or item.get("name") for item in priority}

        prem_items = [
            item for item in candidates
            if (item.get("id") or item.get("name")) not in used_ids
            and float(item.get("price") or 0) >= premium_floor
        ]
        prem_items = sorted(prem_items, key=lambda x: float(x.get("price") or 0), reverse=True)

        if not prem_items:
            all_sorted = sorted(
                [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids],
                key=lambda x: float(x.get("price") or 0),
                reverse=True
            )
            prem_items = all_sorted

        premium = prem_items[:2]
        if len(premium) < 2:
            rem_by_price = sorted(
                [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids and (item.get("id") or item.get("name")) not in {p.get("id") or p.get("name") for p in premium}],
                key=lambda x: float(x.get("price") or 0),
                reverse=True
            )
            for it in rem_by_price:
                premium.append(it)
                if len(premium) == 2:
                    break

        for p in premium:
            used_ids.add(p.get("id") or p.get("name"))

        additional = [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids][:4]
        return priority[:2], premium[:2], additional[:4]

    # Priority: 1 veg + 1 non-veg (budget-aware)
    budget_veg = [i for i in cand_pool if normalize_food_type(i.get("foodType") or i.get("food_type")) == "veg"]
    budget_non_veg = [i for i in cand_pool if normalize_food_type(i.get("foodType") or i.get("food_type")) == "non_veg"]

    veg_priority = get_priority_items(budget_veg)
    non_veg_priority = get_priority_items(budget_non_veg)

    priority = []
    if veg_priority:
        priority.append(veg_priority[0])
    if non_veg_priority:
        priority.append(non_veg_priority[0])

    if len(priority) < 2:
        used = {x.get("id") or x.get("name") for x in priority}
        for it in get_priority_items(cand_pool):
            if (it.get("id") or it.get("name")) not in used:
                priority.append(it)
                if len(priority) == 2:
                    break

    used_ids = {item.get("id") or item.get("name") for item in priority}

    # Premium: 1 veg + 1 non-veg (price >= premium_floor sorted DESCENDING)
    veg_prem = [
        item for item in veg_items
        if (item.get("id") or item.get("name")) not in used_ids
        and float(item.get("price") or 0) >= premium_floor
    ]
    veg_prem = sorted(veg_prem, key=lambda x: float(x.get("price") or 0), reverse=True)
    if not veg_prem:
        veg_prem = sorted(
            [item for item in veg_items if (item.get("id") or item.get("name")) not in used_ids],
            key=lambda x: float(x.get("price") or 0),
            reverse=True
        )

    non_veg_prem = [
        item for item in non_veg_items
        if (item.get("id") or item.get("name")) not in used_ids
        and float(item.get("price") or 0) >= premium_floor
    ]
    non_veg_prem = sorted(non_veg_prem, key=lambda x: float(x.get("price") or 0), reverse=True)
    if not non_veg_prem:
        non_veg_prem = sorted(
            [item for item in non_veg_items if (item.get("id") or item.get("name")) not in used_ids],
            key=lambda x: float(x.get("price") or 0),
            reverse=True
        )

    premium = []
    if veg_prem:
        premium.append(veg_prem[0])
        used_ids.add(veg_prem[0].get("id") or veg_prem[0].get("name"))
    if non_veg_prem:
        premium.append(non_veg_prem[0])
        used_ids.add(non_veg_prem[0].get("id") or non_veg_prem[0].get("name"))

    if len(premium) < 2:
        rem_by_price = sorted(
            [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids],
            key=lambda x: float(x.get("price") or 0),
            reverse=True
        )
        for it in rem_by_price:
            premium.append(it)
            used_ids.add(it.get("id") or it.get("name"))
            if len(premium) == 2:
                break

    additional = [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids][:4]
    return (
        priority[:2],
        premium[:2],
        additional[:4]
    )


# =========================================================
# AGENT RECOMMENDATIONS
# =========================================================

def get_agent_recommendations(
    category=None,
    food_type=None,
    cart=None
):

    if category:
        items = get_category(
            category
        )

    else:
        items = get_available()


    if not items:

        return {
            "category": category,
            "recommended": None,
            "premium": None
        }


    priority, premium, _ = build_recommendations(
        items,
        food_type=food_type or "both",
        cart=cart
    )


    return {
        "category": category,
        "recommended": (
            priority[0]
            if priority
            else None
        ),
        "premium": (
            premium[0]
            if premium
            else None
        )
    }