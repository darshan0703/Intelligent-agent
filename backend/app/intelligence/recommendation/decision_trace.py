"""
app/intelligence/recommendation/decision_trace.py
Full Replayable Decision Trace — v7 §19

Every recommendation request stores a complete, replayable record.
This is not reconstructed from logs after the fact — it is written atomically
at request completion. It enables answering incident questions in minutes:
  'Why did we recommend a Rs.519 bucket to a Rs.59 order last Tuesday?'
  -> Load the trace, read candidates_generated, filters_applied, evidence_per_candidate.

Trace is stored as append-only JSONL in observability/logs/decision_traces_{date}.jsonl
Old traces beyond RETENTION_DAYS are pruned by SessionPurgeService.
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "observability", "logs"
)
RETENTION_DAYS = 7


@dataclass
class DecisionTrace:
    """
    Complete, replayable record of a single recommendation request.
    Every field here enables a different class of incident investigation.
    """
    # Identity
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    session_id: str = ""
    experiment_arm: str = "control"      # §20: arm tracked, isolated from training
    policy_version: str = "v7.0"         # What version of policy produced this
    model_version: str = "phase1-heuristic"  # What model produced the scores

    # Request context (§23: identity boundary applied before snapshot)
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    job_code: str = ""

    # Generation stage (§12: source-tagged)
    candidates_generated: list[dict[str, Any]] = field(default_factory=list)
    # [{'item_id': 81, 'source': 'semantic_fit', 'provenance': 'model_inferred'}, ...]

    # Filter stage (§21: override hierarchy tiers 1-4)
    filters_applied: list[str] = field(default_factory=list)
    # ['tier1_passed', 'tier2_unavailable:item_42', 'tier4_dietary_veg_lock:item_7', ...]
    candidates_after_filter: list[int] = field(default_factory=list)  # item_ids

    # Scoring stage (§18: calibrated scores recorded)
    evidence_per_candidate: dict[str, Any] = field(default_factory=dict)
    # {item_id: {price_fit, sensory, circadian, kitchen_load, bandit_theta, composite}}

    # Diversity stage
    diversity_pass_applied: bool = False
    diversity_lambda: float = 0.70

    # Gate stage
    gate_decision: str = "shown"  # 'shown' | 'silenced:{reason}'

    # Output
    selected_items: list[int] = field(default_factory=list)  # item_ids in shown order

    # Fallback (§17)
    fallback_level_used: int = 0  # 0=full, 1-5=degraded with reason
    fallback_trigger: str = "none"

    # Latency
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def write(self) -> None:
        """Append this trace to the daily JSONL file. Never raises."""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path = os.path.join(LOGS_DIR, f"decision_traces_{date_str}.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self.to_dict(), ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass  # Tracing must never crash the request path


def build_trace(
    session_id: str,
    job_code: str,
    context_snapshot: dict,
    candidates_generated: list[dict],
    filters_applied: list[str],
    candidates_after_filter: list[int],
    evidence_per_candidate: dict,
    diversity_pass_applied: bool,
    diversity_lambda: float,
    gate_decision: str,
    selected_items: list[int],
    fallback_level_used: int,
    fallback_trigger: str,
    latency_ms: float,
    experiment_arm: str = "control",
    policy_version: str = "v7.0",
    model_version: str = "phase1-heuristic",
) -> DecisionTrace:
    """Factory function to build and immediately write a DecisionTrace."""
    trace = DecisionTrace(
        session_id=session_id,
        experiment_arm=experiment_arm,
        policy_version=policy_version,
        model_version=model_version,
        context_snapshot=context_snapshot,
        job_code=job_code,
        candidates_generated=candidates_generated,
        filters_applied=filters_applied,
        candidates_after_filter=candidates_after_filter,
        evidence_per_candidate=evidence_per_candidate,
        diversity_pass_applied=diversity_pass_applied,
        diversity_lambda=diversity_lambda,
        gate_decision=gate_decision,
        selected_items=selected_items,
        fallback_level_used=fallback_level_used,
        fallback_trigger=fallback_trigger,
        latency_ms=latency_ms,
    )
    trace.write()
    return trace
