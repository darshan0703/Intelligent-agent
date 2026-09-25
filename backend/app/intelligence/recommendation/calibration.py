"""
app/intelligence/recommendation/calibration.py
Score Calibration Infrastructure — v7 §18

Problem: raw_score=0.82 means whatever the weighted sum happened to produce.
It is NOT comparable across jobs, sessions, or model versions. A fixed threshold
(gatekeeper_floor=0.20) is therefore arbitrary by construction.

Fix: calibrate raw scores to actual probabilities before any threshold is applied.
  calibrated_score = isotonic_regression(raw_score)  # fit against logged outcomes
  calibrated_score ≈ P(customer adds this to cart | shown)

Once calibrated, the gatekeeper floor becomes a real statement:
  'Don't show anything below 20% predicted add-to-cart probability.'

Phase 1 (current, < MIN_IMPRESSIONS):
  calibration is a transparent no-op — raw scores pass through unchanged.
  The gatekeeper floor remains a heuristic during this warmup period.
  The infrastructure logs outcomes to score_calibration_log for future fitting.

Phase 2 (self-activating, >= MIN_IMPRESSIONS per job_code):
  isotonic_regression mapping is fitted and applied automatically.
  Recalibrated weekly/monthly on the same cadence as Phase-2 model retraining.

Critical: DO NOT compare raw scores across model versions — only calibrated ones.
  The underlying scale can shift between versions. Calibrated scores are stable.
"""
from __future__ import annotations
import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "infrastructure", "db", "theatom_local.db"
)


class ScoreCalibrator:
    """
    Manages the lifecycle of score calibration per job_code.
    Self-activates calibrated mode once MIN_IMPRESSIONS_FOR_CALIBRATION
    outcome logs are accumulated.
    """

    MIN_IMPRESSIONS_FOR_CALIBRATION: int = 1000
    POLICY_VERSION: str = "v7.0"
    MODEL_VERSION: str = "phase1-heuristic"

    # In-memory outcome counts per job_code — avoids DB query on every request
    _impression_counts: dict[str, int] = {}
    _isotonic_maps: dict[str, list[tuple[float, float]]] = {}  # raw -> calibrated breakpoints

    @classmethod
    def calibrate(cls, raw_score: float, job_code: str = "CLOSURE") -> float:
        """
        Phase 1: Returns raw_score unchanged (transparent no-op).
        Phase 2: Once MIN_IMPRESSIONS reached per job_code, applies isotonic mapping.
        calibrated_score ≈ P(customer adds this to cart | shown)
        """
        if not cls._has_enough_data(job_code):
            return raw_score  # Explicit no-op — not a silent failure
        return cls._apply_isotonic_map(raw_score, job_code)

    @classmethod
    def record_outcome(
        cls,
        item_id: int,
        raw_score: float,
        outcome: int,  # 1 = added to cart, 0 = ignored/dismissed
        job_code: str,
        session_id: str,
        experiment_arm: str = "control",
    ) -> None:
        """
        Logs an impression outcome to score_calibration_log.
        Only 'control' arm outcomes feed the default calibration/training pipeline (§20).
        Treatment arm outcomes are segregated and used only for their own experiment readout.
        """
        # §20 experiment isolation: skip non-control arms for calibration training
        if experiment_arm != "control":
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO score_calibration_log
                  (item_id, raw_score, outcome, job_code, session_id, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    round(raw_score, 6),
                    outcome,
                    job_code,
                    session_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()

            # Update in-memory count
            cls._impression_counts[job_code] = cls._impression_counts.get(job_code, 0) + 1
        except Exception:
            pass  # Telemetry must never crash the request path

    @classmethod
    def _has_enough_data(cls, job_code: str) -> bool:
        """Checks if enough outcome data exists to trust the isotonic mapping."""
        cached = cls._impression_counts.get(job_code)
        if cached is not None:
            return cached >= cls.MIN_IMPRESSIONS_FOR_CALIBRATION

        # Query DB to initialize the cache
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM score_calibration_log WHERE job_code = ? AND outcome IS NOT NULL",
                (job_code,),
            )
            row = cursor.fetchone()
            conn.close()
            count = row[0] if row else 0
            cls._impression_counts[job_code] = count
            return count >= cls.MIN_IMPRESSIONS_FOR_CALIBRATION
        except Exception:
            return False  # Can't query DB → stay in Phase 1

    @classmethod
    def _apply_isotonic_map(cls, raw_score: float, job_code: str) -> float:
        """
        Phase 2: Applies isotonic regression mapping.
        The map is a sorted list of (raw, calibrated) breakpoints.
        Linear interpolation between breakpoints.
        """
        if job_code not in cls._isotonic_maps:
            return raw_score  # Map not loaded yet

        breakpoints = cls._isotonic_maps[job_code]
        if not breakpoints:
            return raw_score

        # Binary search + linear interpolation
        for i, (r, c) in enumerate(breakpoints):
            if raw_score <= r:
                if i == 0:
                    return c
                prev_r, prev_c = breakpoints[i - 1]
                # Linear interpolation
                if r == prev_r:
                    return c
                frac = (raw_score - prev_r) / (r - prev_r)
                return prev_c + frac * (c - prev_c)
        # Beyond last breakpoint
        return breakpoints[-1][1]

    @classmethod
    def recalibrate(cls, job_code: str) -> bool:
        """
        Fits a new isotonic regression mapping from logged outcomes.
        Called weekly/monthly by a maintenance job (not on the request path).
        Returns True if recalibration succeeded.
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT raw_score, outcome FROM score_calibration_log
                WHERE job_code = ? AND outcome IS NOT NULL
                ORDER BY raw_score ASC
                """,
                (job_code,),
            )
            rows = cursor.fetchall()
            conn.close()

            if len(rows) < cls.MIN_IMPRESSIONS_FOR_CALIBRATION:
                return False

            # Pool scores into bins and compute empirical conversion rate per bin
            bin_size = 0.05
            bins: dict[float, list[int]] = {}
            for raw, outcome in rows:
                bin_key = round(round(raw / bin_size) * bin_size, 2)
                bins.setdefault(bin_key, []).append(outcome)

            # Build breakpoints: (raw_score, empirical_ctr)
            breakpoints = []
            for bin_key in sorted(bins.keys()):
                outcomes = bins[bin_key]
                empirical_ctr = sum(outcomes) / len(outcomes)
                breakpoints.append((bin_key, empirical_ctr))

            # Enforce isotonic (non-decreasing) constraint
            for i in range(1, len(breakpoints)):
                if breakpoints[i][1] < breakpoints[i - 1][1]:
                    # Pool adjacent violating bins
                    avg = (breakpoints[i - 1][1] + breakpoints[i][1]) / 2
                    breakpoints[i - 1] = (breakpoints[i - 1][0], avg)
                    breakpoints[i] = (breakpoints[i][0], avg)

            cls._isotonic_maps[job_code] = breakpoints
            return True
        except Exception:
            return False

    @classmethod
    def get_status(cls, job_code: str) -> dict:
        """Returns calibration status for observability/debugging."""
        count = cls._impression_counts.get(job_code, 0)
        return {
            "job_code": job_code,
            "phase": "2_calibrated" if count >= cls.MIN_IMPRESSIONS_FOR_CALIBRATION else "1_passthrough",
            "impression_count": count,
            "threshold": cls.MIN_IMPRESSIONS_FOR_CALIBRATION,
            "isotonic_map_loaded": job_code in cls._isotonic_maps,
            "policy_version": cls.POLICY_VERSION,
            "model_version": cls.MODEL_VERSION,
        }
