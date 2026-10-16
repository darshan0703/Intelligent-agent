"""
backend/services/modules/m08_contextual_memory.py
Module B1: Contextual Observation Memory Store & Scoped Session Memory

Core Responsibilities:
1. Scoped Observation Tracking:
   - Tracks session-scoped interactions (rejections, dismissals, preferences, views).
   - Scoping:
     * 'item': Scoped strictly to a specific item (e.g. meal upgrade dismissed for item_id 12).
     * 'category': Scoped to an entire category (e.g. customer rejected sides).
     * 'session': Global session preference/rejection.
2. Meal Offer Protection:
   - Dismissing a meal offer for 'Veg Makhani' (item_id 12) ONLY suppresses meal offers
     for item_id 12 — NOT for other burgers.
3. Reranking Memory Integration:
   - Tracks viewed and skipped items to provide novelty decay signals for downstream ranking.
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime


def ensure_memory_structures(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures observations and interaction tracking maps exist in conversation_context.
    """
    if "observations" not in context or not isinstance(context["observations"], list):
        context["observations"] = []
    if "dismissed_meals" not in context or not isinstance(context["dismissed_meals"], set):
        context["dismissed_meals"] = set()
    if "view_history" not in context or not isinstance(context["view_history"], list):
        context["view_history"] = []
    return context


def record_observation(
    context: Dict[str, Any],
    subject: str,
    predicate: str,
    value: Any,
    scope: str = "item",
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Records a structured contextual observation into the session memory.
    """
    ensure_memory_structures(context)

    obs = {
        "subject": str(subject),
        "predicate": str(predicate),
        "value": str(value),
        "scope": str(scope).lower(),
        "confidence": float(confidence),
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    }

    context["observations"].append(obs)

    # Fast lookup sets
    if predicate == "meal_offer_dismissed" and scope == "item":
        try:
            context["dismissed_meals"].add(str(value))
        except (TypeError, ValueError):
            pass

    return obs


def record_meal_rejection(context: Dict[str, Any], item_id: Any) -> None:
    """
    Records an explicit meal upgrade rejection scoped strictly to item_id.
    Does NOT globally block meal offers for other products.
    """
    if item_id is None:
        return
    record_observation(
        context,
        subject="meal_offer",
        predicate="meal_offer_dismissed",
        value=str(item_id),
        scope="item",
        confidence=1.0,
        metadata={"reason": "user_dismissed"}
    )


def is_meal_offer_dismissed(context: Dict[str, Any], item_id: Any) -> bool:
    """
    Checks if a meal offer for a specific item_id was dismissed in this session.
    """
    if item_id is None:
        return False
    ensure_memory_structures(context)

    target_str = str(item_id)
    if target_str in context["dismissed_meals"]:
        return True

    for obs in context.get("observations", []):
        if (
            obs.get("subject") == "meal_offer"
            and obs.get("predicate") == "meal_offer_dismissed"
            and obs.get("scope") == "item"
        ):
            if str(obs.get("value")) == target_str:
                return True
    return False


def get_active_rejections(context: Dict[str, Any]) -> Set[str]:
    """
    Returns set of item IDs explicitly rejected or dismissed in this session.
    """
    ensure_memory_structures(context)
    rejected = set()
    for obs in context.get("observations", []):
        if obs.get("predicate") in ("item_rejected", "meal_offer_dismissed") and obs.get("scope") == "item":
            rejected.add(str(obs.get("value")))
    return rejected


def record_item_view(context: Dict[str, Any], item_id: Any, item_name: Optional[str] = None) -> None:
    """
    Records an item view for novelty decay scoring.
    """
    if not item_id:
        return
    ensure_memory_structures(context)
    context["view_history"].append({
        "item_id": str(item_id),
        "item_name": item_name,
        "timestamp": datetime.utcnow().isoformat(),
    })
