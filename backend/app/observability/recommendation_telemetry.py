"""
app/observability/recommendation_telemetry.py
Evaluation Loop & Counterfactual Telemetry Logger (v4 Specification).

Instruments every recommendation impression with:
- recommendation_id, session_id, user_id (nullable), timestamp
- anchor_item_id, candidate_item_id, slot (drink/side/dessert)
- score, score_breakdown (price_fit, sensory, circadian, novelty, kitchen_load)
- tier_that_fired
- shown (bool), clicked (bool), added_to_cart (bool)
- Logs considered-but-unshown candidates for counterfactual off-policy evaluation (IPS / Doubly Robust)
- Supports online A/B testing: routes fixed % of traffic to naive baseline
"""
from __future__ import annotations
import json
import os
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from app.observability.logging import get_logger

logger = get_logger("recommendation_telemetry")

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "observability", "logs")
IMPRESSIONS_LOG_PATH = os.path.join(LOGS_DIR, "recommendation_impressions.jsonl")
DECISIONS_LOG_PATH = os.path.join(LOGS_DIR, "recommendation_decisions.jsonl")


class RecommendationTelemetryLogger:
    """Logs impression and candidate evaluation records per v4 specification."""

    _in_memory_records: list[dict[str, Any]] = []
    _in_memory_decisions: list[dict[str, Any]] = []
    MAX_IN_MEMORY = 150

    @classmethod
    def should_route_to_baseline_ab(cls, session_id: str, holdout_pct: float = 0.10) -> bool:
        """
        Online A/B Testing: Deterministically hashes session_id.
        Routes holdout_pct of sessions (default 10%) to naive category top-seller baseline.
        """
        if not session_id or holdout_pct <= 0:
            return False
        # Do not route automated test sessions to the holdout arm unless testing ab explicitly
        if session_id.startswith("test-") and "ab" not in session_id:
            return False
        h = int(hashlib.md5(session_id.encode("utf-8")).hexdigest()[:6], 16)
        bucket = (h % 100) / 100.0
        return bucket < holdout_pct

    @classmethod
    def log_impression_event(
        cls,
        session_id: str,
        anchor_item_id: int | None,
        candidate_item_id: int,
        slot: str,
        score: float,
        score_breakdown: dict[str, float],
        tier_that_fired: str,
        shown: bool,
        user_id: Optional[str] = None,
        recommendation_id: Optional[str] = None,
        clicked: bool = False,
        added_to_cart: bool = False,
        experiment_arm: str = "treatment",
    ) -> dict[str, Any]:
        """
        Logs an individual impression candidate row conforming to v4 §5.
        Captures both shown and unshown candidates for counterfactuals.
        """
        rec_id = recommendation_id or f"rec_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        row = {
            "decision_id": rec_id,
            "recommendation_id": rec_id,
            "session_id": session_id,
            "user_id": user_id,  # Nullable for anonymous kiosk sessions
            "experiment_arm": experiment_arm,  # "treatment" vs "baseline"
            "timestamp": timestamp,
            "anchor_item_id": anchor_item_id,
            "candidate_item_id": candidate_item_id,
            "slot": slot,
            "score": round(score, 4),
            "score_breakdown": score_breakdown,
            "tier_that_fired": tier_that_fired,
            "shown": shown,
            "clicked": clicked,
            "added_to_cart": added_to_cart,
        }

        cls._in_memory_records.append(row)
        if len(cls._in_memory_records) > cls.MAX_IN_MEMORY:
            cls._in_memory_records.pop(0)

        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(IMPRESSIONS_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug(f"Telemetry append failed: {exc}")

        return row

    @classmethod
    def log_decision(
        cls,
        session_id: str,
        endpoint: str,
        anchor_info: dict[str, Any],
        candidates_evaluated: list[dict[str, Any]],
        served_items: list[dict[str, Any]],
        gatekeeper_decision: dict[str, Any],
        user_id: Optional[str] = None,
        latency_ms: float = 0.0,
        experiment_arm: str = "treatment",
    ) -> str:
        """
        Batch-logs complete decision and emits v4 §5 impression rows for all evaluated candidates.
        """
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        served_ids = {s.get("id") or s.get("item_id") for s in served_items}
        anchor_id = anchor_info.get("id") or anchor_info.get("anchor_item_id")

        # Emit counterfactual rows for every evaluated candidate
        for cand in candidates_evaluated:
            cid = cand.get("item_id") or cand.get("id")
            is_shown = cid in served_ids
            slot = cand.get("category", "general")
            score = cand.get("composite_score", 0.0)
            breakdown = cand.get("score_breakdown", {})

            cls.log_impression_event(
                session_id=session_id,
                user_id=user_id,
                recommendation_id=decision_id,
                anchor_item_id=anchor_id,
                candidate_item_id=cid,
                slot=slot,
                score=score,
                score_breakdown=breakdown,
                tier_that_fired="Tier 7: Controlled Exploration" if is_shown else "Tier 4: Rejected / Unshown Counterfactual",
                shown=is_shown,
                experiment_arm=experiment_arm,
            )

        # Write overall decision record
        record = {
            "decision_id": decision_id,
            "recommendation_id": decision_id,
            "timestamp": timestamp,
            "session_id": session_id,
            "user_id": user_id,
            "experiment_arm": experiment_arm,
            "endpoint": endpoint,
            "latency_ms": round(latency_ms, 2),
            "anchor": anchor_info,
            "candidates_count": len(candidates_evaluated),
            "candidates_evaluated": candidates_evaluated,
            "served_count": len(served_items),
            "served_items": served_items,
            "gatekeeper": gatekeeper_decision,
        }

        cls._in_memory_decisions.append(record)
        if len(cls._in_memory_decisions) > cls.MAX_IN_MEMORY:
            cls._in_memory_decisions.pop(0)

        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(DECISIONS_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

        return decision_id

    @classmethod
    def get_recent_decisions(cls, limit: int = 10) -> list[dict[str, Any]]:
        if cls._in_memory_decisions:
            return cls._in_memory_decisions[-limit:]
        return cls._in_memory_records[-limit:]


# ── EXPERIMENT ISOLATION — v7 §20 ─────────────────────────────────────────────

from dataclasses import dataclass as _exp_dataclass


@_exp_dataclass
class ExperimentConfig:
    """
    Scoped experiment configuration per A/B arm.
    Each experiment gets its own policy_namespace — a losing experiment can be
    torn down cleanly with zero residue in the shared policy_config.

    Training pipelines must filter by experiment_arm='control' by default.
    Treatment arm traffic is analyzed for the experiment's own readout ONLY,
    never silently pooled into the general training set (§20).
    """
    arm_id: str            # 'control' | 'treatment_price_k6' | 'treatment_mmr_lambda'
    policy_namespace: str  # Scoped version: 'v7.0-exp-price_k6' — not mutating global policy
    param_overrides: dict  # {'price_logistic_k': 6.0} — scoped, not global mutations
    treatment_pct: float = 0.10  # Fraction of sessions in this arm


class ExperimentRegistry:
    """
    Manages A/B experiment arm assignment and isolation.
    Assignment is deterministic (same session always gets same arm).
    """

    _active_experiments: dict[str, ExperimentConfig] = {}

    @classmethod
    def register(cls, config: ExperimentConfig) -> None:
        """Registers an experiment arm. Only one active experiment per arm_id."""
        cls._active_experiments[config.arm_id] = config

    @classmethod
    def get_arm(cls, session_id: str) -> ExperimentConfig:
        """
        Returns the ExperimentConfig for this session.
        Uses deterministic hash assignment so the same session always gets the same arm.
        Returns a default 'control' config when no experiments are active.
        """
        import hashlib
        if not cls._active_experiments:
            return ExperimentConfig(
                arm_id="control",
                policy_namespace="v7.0",
                param_overrides={},
            )

        h = int(hashlib.md5(session_id.encode("utf-8")).hexdigest()[:6], 16)
        bucket = (h % 100) / 100.0

        # Find matching treatment arm (control gets the rest)
        for arm_id, config in cls._active_experiments.items():
            if arm_id != "control" and bucket < config.treatment_pct:
                return config

        # Default to control
        return ExperimentConfig(
            arm_id="control",
            policy_namespace="v7.0",
            param_overrides={},
        )

    @classmethod
    def is_training_eligible(cls, arm_id: str) -> bool:
        """
        §20: Only the 'control' arm feeds the default training pipeline.
        Treatment arm traffic is isolated and used only for its own experiment readout.
        A temporary experiment must never permanently bias the model that outlives it.
        """
        return arm_id == "control"

    @classmethod
    def get_policy_namespace(cls, session_id: str) -> str:
        """Returns the scoped policy_version for this session's experiment arm."""
        arm = cls.get_arm(session_id)
        return arm.policy_namespace
