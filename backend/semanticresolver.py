from difflib import get_close_matches


def semantic_resolve(item_name, menu, conversation_context):
    result = {
        "resolved_item": None,
        "candidates": [],
        "needs_clarification": False,
        "clarification_question": None
    }

    item_name = item_name.lower().strip() if item_name else None

    if not item_name:
        return result

    # ----------------------------
    # 1. Exact match
    # ----------------------------
    for item in menu:
        if item["name"].lower() == item_name:
            result["resolved_item"] = item
            return result

    # ----------------------------
    # 2. Partial match
    # ----------------------------
    partial_matches = [
        item for item in menu
        if item_name in item["name"].lower()
    ]

    if len(partial_matches) == 1:
        result["resolved_item"] = partial_matches[0]
        return result

    if len(partial_matches) > 1:
        result["candidates"] = partial_matches
        result["needs_clarification"] = True
        result["clarification_question"] = (
            "We have " +
            ", ".join([item["name"] for item in partial_matches]) +
            ". Which one would you like?"
        )
        return result

    # ----------------------------
    # 3. Similar fuzzy match
    # ----------------------------
    menu_names = [item["name"] for item in menu]

    similar = get_close_matches(
        item_name,
        menu_names,
        n=3,
        cutoff=0.4
    )

    if similar:
        candidates = [
            item for item in menu
            if item["name"] in similar
        ]

        result["candidates"] = candidates
        result["needs_clarification"] = True
        result["clarification_question"] = (
            "Did you mean " +
            ", ".join(similar) +
            "?"
        )
        return result

    # ----------------------------
    # 4. Context reference words
    # ----------------------------
    if item_name in ["that", "it", "same", "another"]:
        if conversation_context["last_item"]:
            for item in menu:
                if item["name"] == conversation_context["last_item"]:
                    result["resolved_item"] = item
                    return result

    return result