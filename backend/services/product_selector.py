import threading
from services.menu_service import get_available, get_menu_version
from perf import get_current_tracer

_INDEX_LOCK = threading.Lock()
_CACHED_ID = None
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
    Pre-tokenized in-memory index for O(1) exact lookup and rapid token-subset matching.
    """
    __slots__ = ("exact_map", "token_list", "category_token_list")

    def __init__(self, products):
        self.exact_map = {}
        self.token_list = []
        self.category_token_list = []

        for p in products:
            raw_name = p.get("name")
            norm_name = normalize(raw_name)
            if norm_name:
                self.exact_map.setdefault(norm_name, []).append(p)
            name_tokens = tokenize(raw_name)
            if name_tokens:
                self.token_list.append((name_tokens, p))
                cat = normalize(p.get("category"))
                if cat:
                    self.category_token_list.append((name_tokens, cat, p))


def _get_or_build_index(products):
    global _CACHED_ID, _FAST_INDEX
    current_id = id(products)
    if _FAST_INDEX is not None and _CACHED_ID == current_id:
        return _FAST_INDEX

    with _INDEX_LOCK:
        if _FAST_INDEX is not None and _CACHED_ID == current_id:
            return _FAST_INDEX
        _FAST_INDEX = _ProductIndex(products)
        _CACHED_ID = current_id
        return _FAST_INDEX


def resolve_product(product_query, conversation_context):
    tracer = get_current_tracer()
    if tracer:
        with tracer.measure("backend_product_resolution"):
            return _resolve_product_internal(product_query, conversation_context)
    return _resolve_product_internal(product_query, conversation_context)


def _resolve_product_internal(product_query, conversation_context):
    """
    Resolve a customer's product reference against the real
    available restaurant menu.

    Matching strategy:
    1. Exact product-name match (O(1) hash map lookup).
    2. Token-based product-name matching (pre-tokenized list comprehension).
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
    if not available_products:
        return {
            "status": "not_found",
            "matches": [],
        }

    index = _get_or_build_index(available_products)



    # ==========================================================
    # 1. EXACT PRODUCT NAME (O(1))
    # ==========================================================
    exact_matches = index.exact_map.get(query)
    if exact_matches:
        if len(exact_matches) == 1:
            return {
                "status": "selected",
                "product": exact_matches[0],
                "matches": exact_matches,
            }
        return {
            "status": "ambiguous",
            "matches": exact_matches,
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
        product
        for name_tokens, product in index.token_list
        if name_tokens.issubset(query_tokens)
    ]

    # ==========================================================
    # 3. CATEGORY-AWARE MATCH
    # ==========================================================
    if not candidates:
        candidates = [
            product
            for name_tokens, cat, product in index.category_token_list
            if (name_tokens | {cat}).issubset(query_tokens) or name_tokens.issubset(query_tokens)
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