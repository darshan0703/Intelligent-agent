import threading
from services.menu_service import get_available, get_menu_version
from perf import get_current_tracer

_INDEX_LOCK = threading.RLock()
_FAST_INDEX = None


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


class _ProductIndex:
    """
    Pre-tokenized in-memory index mapping normalized names and token sets
    to positional indices within the authoritative products list.
    """
    __slots__ = ("exact_indices_map", "token_indices", "category_indices", "signature")

    def __init__(self, products, signature):
        self.signature = signature
        self.exact_indices_map = {}
        self.token_indices = []
        self.category_indices = []

        for idx, p in enumerate(products):
            if not isinstance(p, dict):
                continue
            raw_name = p.get("name")
            norm_name = normalize(raw_name)
            if norm_name:
                self.exact_indices_map.setdefault(norm_name, []).append(idx)
            name_tokens = frozenset(tokenize(raw_name))
            if name_tokens:
                self.token_indices.append((name_tokens, idx))
                cat = normalize(p.get("category"))
                if cat:
                    self.category_indices.append((name_tokens, cat, idx))


def _compute_snapshot_signature(products):
    """
    Computes a snapshot signature of the products list.
    Guarantees invalidation if menu version, item count, or item names/categories change.
    """
    version = get_menu_version()
    items_sig = tuple(
        (p.get("id"), p.get("name"), p.get("category"))
        for p in products
        if isinstance(p, dict)
    )
    return (version, len(products), items_sig)


def invalidate_product_index():
    """
    Safely reset the product index cache.
    """
    global _FAST_INDEX
    with _INDEX_LOCK:
        _FAST_INDEX = None


def _get_or_build_index(products):
    global _FAST_INDEX
    sig = _compute_snapshot_signature(products)

    current = _FAST_INDEX
    if current is not None and current.signature == sig:
        return current

    with _INDEX_LOCK:
        current = _FAST_INDEX
        if current is not None and current.signature == sig:
            return current
        new_index = _ProductIndex(products, sig)
        _FAST_INDEX = new_index
        return new_index


def resolve_product(product_query, conversation_context):
    tracer = get_current_tracer()
    if tracer:
        with tracer.measure("backend_product_resolution"):
            return _resolve_product_internal(product_query, conversation_context)
    return _resolve_product_internal(product_query, conversation_context)


def _is_eligible_product(product):
    """
    Enforces business rules for product eligibility:
    - Products must be valid dictionaries.
    - Explicitly unavailable products (is_available is False) are ineligible.
    - Explicitly out-of-stock products (stock is not None and stock <= 0) are ineligible.
    """
    if not isinstance(product, dict):
        return False
    if product.get("is_available") is False:
        return False
    stock = product.get("stock")
    if stock is not None and stock <= 0:
        return False
    return True


def _resolve_product_internal(product_query, conversation_context):
    """
    Resolve a customer's product reference against the real
    available restaurant menu.

    Matching strategy:
    1. Exact product-name match (O(1) hash map lookup).
    2. Token-based product-name matching (pre-tokenized list comprehension).
    3. Use database category information when relevant.
    4. Return selected only when the result is unambiguous and eligible.
    5. Return ambiguous when multiple real products match.
    6. Return not_found when no eligible products match.
    """
    query = normalize(product_query)

    if not query:
        return {
            "status": "not_found",
            "matches": [],
        }

    available_products = get_available()
    if not available_products:
        return {
            "status": "not_found",
            "matches": [],
        }

    index = _get_or_build_index(available_products)

    # ==========================================================
    # 1. EXACT PRODUCT NAME (O(1))
    # ==========================================================
    exact_indices = index.exact_indices_map.get(query)
    if exact_indices:
        exact_matches = [
            available_products[i] for i in exact_indices
            if _is_eligible_product(available_products[i])
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
        # If all exact candidates are ineligible (out of stock/unavailable),
        # return not_found. Established business rule prevents selecting unavailable items.
        return {
            "status": "not_found",
            "matches": [],
        }

    # ==========================================================
    # 2. TOKEN-BASED PRODUCT MATCH (Pre-tokenized subset test)
    # ==========================================================
    query_tokens = tokenize(query)
    if not query_tokens:
        return {
            "status": "not_found",
            "matches": [],
        }

    candidates = [
        available_products[idx]
        for name_tokens, idx in index.token_indices
        if name_tokens.issubset(query_tokens) and _is_eligible_product(available_products[idx])
    ]

    # ==========================================================
    # 3. CATEGORY-AWARE MATCH
    # ==========================================================
    if not candidates:
        candidates = [
            available_products[idx]
            for name_tokens, cat, idx in index.category_indices
            if ((name_tokens | {cat}).issubset(query_tokens) or name_tokens.issubset(query_tokens))
            and _is_eligible_product(available_products[idx])
        ]

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