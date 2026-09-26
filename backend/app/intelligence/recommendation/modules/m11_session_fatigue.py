"""
Module 11: Session Fatigue & Novelty Damping (Phase 4 Heuristics)
Damps items that have been presented multiple times without being added (0.70x).
Enables unviewed catalog items to bubble up.
"""
from typing import Dict, Any, List

def apply_session_fatigue(
    candidate: Dict[str, Any],
    shown_counts: Dict[str, int]
) -> float:
    name = str(candidate.get("name", "")).strip().lower()
    impressions = shown_counts.get(name, 0)

    if impressions >= 3:
        return 0.70
    elif impressions >= 2:
        return 0.85

    return 1.0
