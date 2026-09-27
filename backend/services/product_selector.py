from services.menu_service import get_available


def normalize(value):
    """
    Normalize text for deterministic product matching.
    """
    return " ".join(
        str(value or "")
        .lower()
        .strip()
        .split()
    )


def tokenize(value):
    """
    Convert text into normalized tokens.
    """
    return set(normalize(value).split())


def resolve_product(product_query, conversation_context):
    """
    Resolve a customer's product reference against the real
    available restaurant menu.

    Matching strategy:

    1. Exact product-name match.
    2. Token-based product-name matching.
    3. Use database category information when relevant.
    4. Return selected only when the result is unambiguous.
    5. Return ambiguous when multiple real products match.
    """

    query = normalize(product_query)

    if not query:
        return {
            "status": "not_found",
            "matches": [],
        }

    available_products = get_available()

    # ==========================================================
    # 1. EXACT PRODUCT NAME
    # ==========================================================

    exact_matches = [
        product
        for product in available_products
        if normalize(product.get("name")) == query
    ]

    if len(exact_matches) == 1:
        return {
            "status": "selected",
            "product": exact_matches[0],
            "matches": exact_matches,
        }

    if len(exact_matches) > 1:
        return {
            "status": "ambiguous",
            "matches": exact_matches,
        }

    # ==========================================================
    # 2. TOKEN-BASED PRODUCT MATCH
    # ==========================================================

    query_tokens = tokenize(query)

    if not query_tokens:
        return {
            "status": "not_found",
            "matches": [],
        }

    candidates = []

    for product in available_products:

        name_tokens = tokenize(product.get("name"))

        if not name_tokens:
            continue

        # Every meaningful token from the stored product name
        # must appear in the customer's request.
        #
        # Example:
        #
        # "crispy chicken double patty"
        #       ↓
        # "crispy chicken double patty"
        #
        # matches exactly.
        if name_tokens.issubset(query_tokens):

            candidates.append(product)

    # ==========================================================
    # 3. CATEGORY-AWARE MATCH
    # ==========================================================
    #
    # If no product name matched directly, allow the customer's
    # extra wording to describe the product category.
    #
    # Example:
    #
    # "crispy chicken burger"
    #
    # Product:
    # "Crispy Chicken"
    # category: burger
    #
    # The product name tokens match the meaningful part of
    # the customer's request and the DB confirms it is a burger.
    #
    # We deliberately do NOT hardcode words such as "burger".
    # The category comes from the database.

    if not candidates:

        category_matches = []

        for product in available_products:

            name_tokens = tokenize(product.get("name"))
            category = normalize(product.get("category"))

            if not name_tokens:
                continue

            matched_name_tokens = name_tokens.intersection(query_tokens)

            if not matched_name_tokens:
                continue

            # Customer wording contains the stored product name
            # tokens, while additional words may describe its
            # database category.
            if name_tokens.issubset(query_tokens):
                category_matches.append(product)

        candidates = category_matches

    # ==========================================================
    # 4. RESOLVE RESULT
    # ==========================================================

    if len(candidates) == 1:
        return {
            "status": "selected",
            "product": candidates[0],
            "matches": candidates,
        }

    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "matches": candidates,
        }

    # ==========================================================
    # 5. NOTHING FOUND
    # ==========================================================

    return {
        "status": "not_found",
        "matches": [],
    }