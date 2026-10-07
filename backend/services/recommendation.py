from datetime import date, datetime

from services.menu_service import get_available, get_category
from services.modules.m01_dietary_lock import apply_dietary_lock
from services.modules.m07_cart_exclusion import exclude_cart_items
from services.modules.m05_budget_ceiling import apply_price_ceiling
from services.modules.m06_condiment_gating import filter_for_recommendation_page


# =========================================================
# PRIORITY CALCULATION
# =========================================================

def get_priority_items(menu):
    today = date.today()

    for item in menu:
        expiry = item.get("expiry")

        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry).date()

        days_to_expiry = (
            (expiry - today).days
            if expiry
            else 30
        )

        expiry_score = max(
            0,
            30 - days_to_expiry
        )

        item["priority"] = (
            item.get("stock", 0)
            + expiry_score
        ) * item.get("score", 1.0)

    return sorted(
        menu,
        key=lambda x: x["priority"],
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

    # =====================================================
    # CANDIDATE POOL & DYNAMIC PREMIUM FLOOR
    # =====================================================
    candidates = filtered
    _all_prices = [float(i.get("price") or 0) for i in candidates if i.get("price")]
    _cat_max = max(_all_prices) if _all_prices else 0

    # Adaptive premium floor:
    # If category max is >= 150 (burgers, drinks, sides), premium floor is at least 120 and 55% of max.
    # If category max is < 150 (e.g. desserts where max is 129), premium floor is 55% of max (~71).
    if _cat_max >= 150:
        premium_floor = max(120.0, _cat_max * 0.55)
    else:
        premium_floor = _cat_max * 0.55

    # =====================================================
    # BUDGET-AWARE CANDIDATES (MODULE 5) FOR PRIORITY
    # =====================================================
    budget_candidates = apply_price_ceiling(candidates, cart=cart or [])
    priority_pool = get_priority_items(budget_candidates) if budget_candidates else get_priority_items(candidates)

    # =====================================================
    # SINGLE / ALREADY FILTERED TYPE (veg, non_veg, hot, cold)
    # =====================================================
    if normalized_type in ("veg", "non_veg", "hot", "cold"):
        priority = priority_pool[:2]
        if len(priority) < 2:
            used = {x.get("id") or x.get("name") for x in priority}
            for it in get_priority_items(candidates):
                if (it.get("id") or it.get("name")) not in used:
                    priority.append(it)
                    if len(priority) == 2:
                        break

        used_ids = {item.get("id") or item.get("name") for item in priority}

        # Premium candidates: price >= premium_floor sorted ASCENDING (nearest above floor)
        prem_items = [
            item for item in candidates
            if (item.get("id") or item.get("name")) not in used_ids
            and float(item.get("price") or 0) >= premium_floor
        ]
        prem_items = sorted(prem_items, key=lambda x: float(x.get("price") or 0))

        # Fallback: if no item >= floor, take top 30% costliest sorted ascending
        if not prem_items:
            all_sorted = sorted(
                [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids],
                key=lambda x: float(x.get("price") or 0),
                reverse=True
            )
            prem_items = sorted(
                all_sorted[: max(1, len(all_sorted) // 3)],
                key=lambda x: float(x.get("price") or 0)
            )

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
    veg_items = [item for item in candidates if normalize_food_type(item.get("foodType")) == "veg"]
    non_veg_items = [item for item in candidates if normalize_food_type(item.get("foodType")) == "non_veg"]

    if not veg_items or not non_veg_items:
        priority = priority_pool[:2]
        if len(priority) < 2:
            used = {x.get("id") or x.get("name") for x in priority}
            for it in get_priority_items(candidates):
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
        prem_items = sorted(prem_items, key=lambda x: float(x.get("price") or 0))

        if not prem_items:
            all_sorted = sorted(
                [item for item in candidates if (item.get("id") or item.get("name")) not in used_ids],
                key=lambda x: float(x.get("price") or 0),
                reverse=True
            )
            prem_items = sorted(
                all_sorted[: max(1, len(all_sorted) // 3)],
                key=lambda x: float(x.get("price") or 0)
            )

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
    veg_priority = get_priority_items([i for i in budget_candidates if normalize_food_type(i.get("foodType")) == "veg"])
    if not veg_priority:
        veg_priority = get_priority_items(veg_items)

    non_veg_priority = get_priority_items([i for i in budget_candidates if normalize_food_type(i.get("foodType")) == "non_veg"])
    if not non_veg_priority:
        non_veg_priority = get_priority_items(non_veg_items)

    priority = []
    if veg_priority:
        priority.append(veg_priority[0])
    if non_veg_priority:
        priority.append(non_veg_priority[0])

    if len(priority) < 2:
        used = {x.get("id") or x.get("name") for x in priority}
        for it in priority_pool:
            if (it.get("id") or it.get("name")) not in used:
                priority.append(it)
                if len(priority) == 2:
                    break

    used_ids = {item.get("id") or item.get("name") for item in priority}

    # Premium: 1 veg + 1 non-veg (price >= premium_floor sorted ASCENDING)
    veg_prem = [
        item for item in veg_items
        if (item.get("id") or item.get("name")) not in used_ids
        and float(item.get("price") or 0) >= premium_floor
    ]
    veg_prem = sorted(veg_prem, key=lambda x: float(x.get("price") or 0))
    if not veg_prem:
        all_sorted = sorted(
            [item for item in veg_items if (item.get("id") or item.get("name")) not in used_ids],
            key=lambda x: float(x.get("price") or 0),
            reverse=True
        )
        veg_prem = sorted(
            all_sorted[: max(1, len(all_sorted) // 3)],
            key=lambda x: float(x.get("price") or 0)
        )

    non_veg_prem = [
        item for item in non_veg_items
        if (item.get("id") or item.get("name")) not in used_ids
        and float(item.get("price") or 0) >= premium_floor
    ]
    non_veg_prem = sorted(non_veg_prem, key=lambda x: float(x.get("price") or 0))
    if not non_veg_prem:
        all_sorted = sorted(
            [item for item in non_veg_items if (item.get("id") or item.get("name")) not in used_ids],
            key=lambda x: float(x.get("price") or 0),
            reverse=True
        )
        non_veg_prem = sorted(
            all_sorted[: max(1, len(all_sorted) // 3)],
            key=lambda x: float(x.get("price") or 0)
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