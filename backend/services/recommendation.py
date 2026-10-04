from datetime import date, datetime

from services.menu_service import get_available, get_category
from services.modules.m01_dietary_lock import apply_dietary_lock
from services.modules.m07_cart_exclusion import exclude_cart_items


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
        )

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


    # =====================================================
    # SINGLE / ALREADY FILTERED TYPE
    # =====================================================

    if normalized_type in (
        "veg",
        "non_veg",
        "hot",
        "cold"
    ):

        priority_candidates = get_priority_items(
            filtered
        )

        priority = priority_candidates[:2]

        used_ids = {
            item.get("id") or item.get("name")
            for item in priority
        }


        # -------------------------------------------------
        # PREMIUM
        # -------------------------------------------------

        premium = []

        for item in sorted(
            filtered,
            key=lambda x: float(
                x.get("price") or 0
            ),
            reverse=True
        ):

            item_id = (
                item.get("id")
                or item.get("name")
            )

            if item_id in used_ids:
                continue

            premium.append(item)
            used_ids.add(item_id)

            if len(premium) == 2:
                break


        # -------------------------------------------------
        # ADDITIONAL
        # -------------------------------------------------

        additional = []

        for item in filtered:

            item_id = (
                item.get("id")
                or item.get("name")
            )

            if item_id in used_ids:
                continue

            additional.append(item)
            used_ids.add(item_id)

            if len(additional) == 4:
                break


        return (
            priority[:2],
            premium[:2],
            additional[:4]
        )


    # =====================================================
    # BOTH
    # =====================================================

    veg_items = [
        item
        for item in filtered
        if normalize_food_type(
            item.get("foodType")
        ) == "veg"
    ]


    non_veg_items = [
        item
        for item in filtered
        if normalize_food_type(
            item.get("foodType")
        ) == "non_veg"
    ]


    # =====================================================
    # IF CATEGORY HAS ONLY ONE FOOD TYPE
    # =====================================================

    if not veg_items or not non_veg_items:

        priority_candidates = get_priority_items(
            filtered
        )

        priority = priority_candidates[:2]

        used_ids = {
            item.get("id") or item.get("name")
            for item in priority
        }


        premium = []

        for item in sorted(
            filtered,
            key=lambda x: float(
                x.get("price") or 0
            ),
            reverse=True
        ):

            item_id = (
                item.get("id")
                or item.get("name")
            )

            if item_id in used_ids:
                continue

            premium.append(item)
            used_ids.add(item_id)

            if len(premium) == 2:
                break


        additional = []

        for item in filtered:

            item_id = (
                item.get("id")
                or item.get("name")
            )

            if item_id in used_ids:
                continue

            additional.append(item)
            used_ids.add(item_id)

            if len(additional) == 4:
                break


        return (
            priority[:2],
            premium[:2],
            additional[:4]
        )


    # =====================================================
    # BOTH: VEG + NON-VEG
    #
    # IMPORTANT:
    # Preserve the behavior from the previous
    # recommendation engine:
    #
    # priority = 1 veg + 1 non-veg
    # premium  = 1 veg + 1 non-veg
    # =====================================================

    veg_priority = get_priority_items(
        veg_items
    )

    non_veg_priority = get_priority_items(
        non_veg_items
    )


    # -----------------------------------------------------
    # PRIORITY
    # -----------------------------------------------------

    priority = []

    if veg_priority:
        priority.append(
            veg_priority[0]
        )

    if non_veg_priority:
        priority.append(
            non_veg_priority[0]
        )


    used_ids = {
        item.get("id") or item.get("name")
        for item in priority
    }


    # -----------------------------------------------------
    # PREMIUM CANDIDATES
    # -----------------------------------------------------

    veg_premium_candidates = sorted(
        [
            item
            for item in veg_items
            if (
                item.get("id")
                or item.get("name")
            ) not in used_ids
        ],
        key=lambda x: float(
            x.get("price") or 0
        ),
        reverse=True
    )


    non_veg_premium_candidates = sorted(
        [
            item
            for item in non_veg_items
            if (
                item.get("id")
                or item.get("name")
            ) not in used_ids
        ],
        key=lambda x: float(
            x.get("price") or 0
        ),
        reverse=True
    )


    # -----------------------------------------------------
    # PREMIUM
    # -----------------------------------------------------

    premium = []

    if veg_premium_candidates:

        premium.append(
            veg_premium_candidates[0]
        )

        used_ids.add(
            veg_premium_candidates[0].get("id")
            or veg_premium_candidates[0].get("name")
        )


    if non_veg_premium_candidates:

        premium.append(
            non_veg_premium_candidates[0]
        )

        used_ids.add(
            non_veg_premium_candidates[0].get("id")
            or non_veg_premium_candidates[0].get("name")
        )


    # -----------------------------------------------------
    # ADDITIONAL
    # -----------------------------------------------------

    additional = []

    for item in filtered:

        item_id = (
            item.get("id")
            or item.get("name")
        )

        if item_id in used_ids:
            continue

        additional.append(item)
        used_ids.add(item_id)

        if len(additional) == 4:
            break


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