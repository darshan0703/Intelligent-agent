"""
app/intelligence/recommendation/engine.py
Universal Context-Aware Recommendation Engine — v7 Specification

The Governance Layer:
- Latency-aware execution tiers: LIGHT (sub-50ms) | FULL (<350ms) | NARROW (<20ms) (§16)
- Quota-bounded candidate retrieval per job_code (§12)
- Product relationship provenance tracking (§22)
- Generator data quality gate: volume + coverage + freshness (§14)
- Override hierarchy short-circuit: Tiers 1-4 pass/fail before Tier 5 scoring (§15, §21)
- Sub-role-aware MMR slot diversity with job-specific lambda (§13)
- Score calibration infrastructure (§18)
- 5-level capability-keyed fallback graph (§17)
- Presentation layer separation (§24)
- Full replayable decision trace emission per request (§19)
- Experiment namespace isolation (§20)
- Privacy / identity boundary enforcement (§23)
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import Candidate, RecommendationSet
from app.domain.session.entities import SessionState
from app.intelligence.recommendation.calibration import ScoreCalibrator
from app.intelligence.recommendation.cognitive_reasoner import CognitiveContextReasoner
from app.intelligence.recommendation.constraints import ConstraintFilter, OverrideHierarchy
from app.intelligence.recommendation.data_quality_gate import DataQualityGate, GeneratorQualityGate
from app.intelligence.recommendation.decision_trace import build_trace
from app.intelligence.recommendation.diversity import MMRDiversity
from app.intelligence.recommendation.fallback_graph import FallbackGraph, FallbackResult
from app.intelligence.recommendation.gatekeeper import Gatekeeper
from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
from app.intelligence.recommendation.job_config import get_job, JobConfig, JOB_REGISTRY
from app.intelligence.recommendation.presentation import PresentationLayer, RenderedItem
from app.intelligence.recommendation.provenance import RelationshipTrust, TaggedCandidate
from app.intelligence.recommendation.ranking import StatisticalRanker
from app.intelligence.recommendation.retrieval import CandidateRetriever, QuotaBoundedRetriever
from app.intelligence.recommendation.session_learner import IdentityBoundary, SessionLearner
from app.observability.recommendation_telemetry import ExperimentRegistry
from app.ports.catalog_port import CatalogRepository
from app.ports.recommendation_port import RecommendationEngine as RecommendationEnginePort

# Session Evidence Acceleration Action Weights (Kiosk high-intent ordering)
ACTION_WEIGHT: dict[str, float] = {
    "viewed": 0.2,
    "clicked": 0.4,
    "added_to_cart": 0.8,
    "removed_from_cart": -0.6,
    "dismissed": -0.5,
}


class HybridRecommendationEngine(RecommendationEnginePort):
    """
    v7 Universal Commercial Intelligence & Recommendation Engine.
    Orchestrates the quota-bounded, governed, traceable pipeline.
    """

    def __init__(self, catalog: CatalogRepository):
        self.catalog = catalog
        self.quality_gate = DataQualityGate()
        self.retriever = QuotaBoundedRetriever(catalog)
        self.constraint_filter = ConstraintFilter()
        self.ranker = StatisticalRanker()
        self.gatekeeper = Gatekeeper()
        self.cognitive_reasoner = CognitiveContextReasoner()
        self.fallback_graph = FallbackGraph(catalog)

    # ── V7 PRIMARY EXECUTION CONTRACT ─────────────────────────────────────────

    async def execute(
        self,
        job_code: str,
        session: SessionState,
        context_payload: dict[str, Any] | None = None,
        branch_id: int = 1,
        limit: int | None = None,
        circadian_hour: int | None = None,
    ) -> list[RenderedItem]:
        """
        v7 §24: Primary execution method returning frontend-renderable RenderedItems.
        Separates ranking decisions from presentation copy.
        """
        payload = context_payload or {}
        payload["job_code"] = job_code
        raw_items, breakdowns, sources = await self._run_governed_pipeline(
            session=session,
            context_payload=payload,
            branch_id=branch_id,
            limit=limit,
            circadian_hour=circadian_hour,
        )
        return PresentationLayer.render_list(raw_items, score_breakdowns=breakdowns, sources=sources)

    # ── BACKWARD-COMPATIBLE PORT METHODS ──────────────────────────────────────

    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None = None,
        food_type: str | None = None,
        branch_id: int = 1,
    ) -> RecommendationSet:
        """
        Category-level browsing recommendation set.
        Maps to DISCOVERY job code under the hood.
        """
        start_time = time.time()
        job_code = "DISCOVERY"

        raw_candidates, cross_sell_ids = await self.retriever.retrieve(
            session=session,
            branch_id=branch_id,
            active_category=category,
            job_code=job_code,
        )

        sanitized_candidates = self.quality_gate.sanitize_candidate_pool(raw_candidates)

        dismissed_ids: set[int] = set()
        if hasattr(self.catalog, "get_dismissed_item_ids"):
            try:
                dismissed_ids = await self.catalog.get_dismissed_item_ids(session.session_id)
            except Exception:
                dismissed_ids = set()

        valid_items = self.constraint_filter.filter_candidates(
            candidates=sanitized_candidates,
            session=session,
            rejected_item_ids=dismissed_ids,
            branch_id=branch_id,
        )

        cart_item_ids: set[int] = set()
        scored_candidates = self.ranker.score_candidates(
            candidates=valid_items,
            session=session,
            cart_item_ids=cart_item_ids,
            cross_sell_ids=cross_sell_ids,
        )

        # v7 sub-role aware MMR with DISCOVERY lambda
        ranked = self.ranker.diversity.rerank(scored_candidates, top_k=8, job_code=job_code)

        priority = ranked[:2]
        remaining = ranked[2:]
        premium = sorted(remaining, key=lambda c: c.item.price.amount, reverse=True)[:2]
        premium_ids = {p.item.id for p in premium}
        additional = [c for c in remaining if c.item.id not in premium_ids][:4]

        rec_set = RecommendationSet(
            session_id=session.session_id,
            context=f"category:{category}" if category else "general",
            priority=priority,
            premium=premium,
            additional=additional,
            generated_at=datetime.now(timezone.utc),
            signals_used=["inventory_pressure", "popularity", "session_affinity", "cross_sell"],
        )

        latency_ms = (time.time() - start_time) * 1000.0

        if hasattr(self.catalog, "record_observation"):
            all_ids = [c.item.id for c in priority + premium + additional]
            asyncio.create_task(
                self.catalog.record_observation(
                    session_id=session.session_id,
                    context_state={"category": category, "food_type": food_type, "latency_ms": round(latency_ms, 2)},
                    recommended_item_ids=all_ids,
                    policy_applied="v7_discovery_governed",
                )
            )

        return rec_set

    async def get_contextual_recommendations(
        self,
        session: SessionState,
        context_payload: dict[str, Any],
        branch_id: int = 1,
        limit: int = 4,
        circadian_hour: int | None = None,
    ) -> list[MenuItem]:
        """
        Context-aware recommendation pipeline returning raw MenuItems for backward compatibility.
        """
        items, _, _ = await self._run_governed_pipeline(
            session=session,
            context_payload=context_payload,
            branch_id=branch_id,
            limit=limit,
            circadian_hour=circadian_hour,
        )
        return items

    async def get_cart_recommendations(
        self,
        session: SessionState,
        cart_lines: list,
        branch_id: int = 1,
        limit: int = 4,
        circadian_hour: int | None = None,
    ) -> list[MenuItem]:
        """Convenience wrapper adapting cart_lines to CLOSURE job."""
        payload = {
            "current_view": "cart_checkout",
            "cart_lines": cart_lines,
            "job_code": "CLOSURE",
        }
        return await self.get_contextual_recommendations(
            session, payload, branch_id=branch_id, limit=limit, circadian_hour=circadian_hour
        )

    # ── V7 GOVERNED PIPELINE CORE ─────────────────────────────────────────────

    async def _run_governed_pipeline(
        self,
        session: SessionState,
        context_payload: dict[str, Any],
        branch_id: int = 1,
        limit: int | None = None,
        circadian_hour: int | None = None,
    ) -> tuple[list[MenuItem], dict[int, dict[str, float]], dict[int, str]]:
        """
        Internal full v7 pipeline execution.
        Returns: (items, score_breakdowns_by_id, source_by_id)
        """
        start_time = time.time()
        cart_lines = context_payload.get("cart_lines", [])
        current_view = context_payload.get("current_view", "menu")
        active_category = context_payload.get("active_category")
        reward_threshold = Decimal(str(context_payload.get("reward_threshold", "299.00")))
        reward_name = context_payload.get("reward_name", "Free Delivery")

        # 1. Job Code Resolution & Config Lookup (§12, §16)
        job_code = context_payload.get("job_code")
        if not job_code:
            if current_view in ("cart_checkout", "cart"):
                job_code = "CLOSURE"
            elif current_view == "category":
                job_code = "DISCOVERY"
            elif current_view == "product":
                job_code = "PRODUCT_CROSSSELL"
            elif current_view == "winback":
                job_code = "SUBSTITUTE"
            else:
                job_code = "CLOSURE" if cart_lines else "DISCOVERY"

        job_cfg = get_job(job_code)
        target_limit = limit if limit is not None else job_cfg.top_k

        # 2. Experiment Arm Assignment (§20 Isolation)
        exp_arm = ExperimentRegistry.get_arm(session.session_id)
        experiment_arm = exp_arm.arm_id
        policy_version = exp_arm.policy_namespace

        # 3. Session Learner & Identity Boundary (§23)
        profile = SessionLearner.update_from_cart(
            session_id=session.session_id,
            cart_lines=cart_lines,
            session_preference=session.food_preference,
        )
        safe_context_snapshot = IdentityBoundary.extract_auto_carry(session.session_id)
        safe_context_snapshot.update({
            "job_code": job_code,
            "current_view": current_view,
            "branch_id": branch_id,
            "cart_line_count": len(cart_lines),
            "added_to_cart_weight": ACTION_WEIGHT["added_to_cart"],
        })

        cart_item_ids = {
            getattr(l, "item_id", l.get("item_id") if isinstance(l, dict) else None)
            for l in cart_lines
            if (getattr(l, "item_id", None) or (isinstance(l, dict) and l.get("item_id")))
        }

        # 4. Anchor Item & Bulk Cart Elasticity (Quantity Unrolling)
        anchor_item_name: str | None = None
        anchor_category: str | None = None
        anchor_price: Decimal | None = None
        cart_total = Decimal("0.00")

        if cart_lines:
            from app.intelligence.recommendation.scoring import calculate_effective_anchor
            eff_anchor = calculate_effective_anchor(cart_lines)
            anchor_price = Decimal(str(round(eff_anchor, 2)))

            prices = []
            for l in cart_lines:
                p = getattr(l, "unit_price", l.get("price") if isinstance(l, dict) else None)
                qty = getattr(l, "quantity", l.get("quantity") if isinstance(l, dict) else 1)
                if p is not None:
                    p_amt = p.amount if hasattr(p, "amount") else Decimal(str(p))
                    prices.append((p_amt, l))
                    cart_total += p_amt * Decimal(str(qty))

            if prices:
                prices.sort(key=lambda x: x[0], reverse=True)
                _, anchor_line = prices[0]
                anchor_item_name = getattr(anchor_line, "item_name", anchor_line.get("name") if isinstance(anchor_line, dict) else "")
                anchor_category = getattr(anchor_line, "category", anchor_line.get("category") if isinstance(anchor_line, dict) else "")

        # 5. Dining Pillar Gap Analysis with Dual-Role Saturation
        has_burger = any("burger" in str(getattr(l, "category", l.get("category") if isinstance(l, dict) else "")).lower() for l in cart_lines)
        has_drink = any("drink" in str(getattr(l, "category", l.get("category") if isinstance(l, dict) else "")).lower() for l in cart_lines)
        has_side = any("side" in str(getattr(l, "category", l.get("category") if isinstance(l, dict) else "")).lower() for l in cart_lines)
        has_dessert = any("dessert" in str(getattr(l, "category", l.get("category") if isinstance(l, dict) else "")).lower() for l in cart_lines)

        # Dual-Role Saturation:
        # If cart contains a heavy, high-dairy beverage (Shake, Frappe, Float, or dairy >= 0.7),
        # mark BOTH Drink and Dessert pillars as FULFILLED.
        has_heavy_drink = any(self.ranker.is_heavy_dairy_beverage(l) for l in cart_lines)
        if has_heavy_drink:
            has_drink = True
            has_dessert = True

        suppressed_categories: set[str] = set()
        if has_drink:
            suppressed_categories.add("drink")
        if has_dessert:
            suppressed_categories.add("dessert")
        if has_burger:
            suppressed_categories.add("burger")
        if has_side:
            suppressed_categories.add("side")

        unfilled = [c for c in ["side", "drink", "dessert", "burger"] if c not in suppressed_categories]
        if unfilled:
            target_categories = unfilled
        else:
            target_categories = ["side", "burger"]

        # 6. Sourcing & Quota-Bounded Retrieval (§12, §22)
        tagged_candidates, cross_sell_ids = await self.retriever.retrieve_tagged(
            session=session,
            branch_id=branch_id,
            active_category=active_category if current_view == "category" else None,
            cart_item_ids=cart_item_ids,
            job_code=job_code,
        )

        candidates_generated_log = [
            {
                "item_id": tc.item.id,
                "name": tc.item.name,
                "source": tc.source,
                "provenance": tc.provenance_type,
            }
            for tc in tagged_candidates
        ]
        source_map = {tc.item.id: tc.source for tc in tagged_candidates}

        # 7. Generator Data Quality Gate (§14)
        co_purchase_count = len([tc for tc in tagged_candidates if tc.source == "co_purchase"])
        source_quality = GeneratorQualityGate.assess_co_purchase(row_count=co_purchase_count, catalog_size=84)
        fallback_level = 0
        fallback_trigger = "none"

        # 8. Data Imputation & Sanitization
        raw_items = [tc.item for tc in tagged_candidates]
        sanitized_candidates = self.quality_gate.sanitize_candidate_pool(raw_items)

        # 9. Dismissal lookups
        dismissed_ids: set[int] = set(profile.dismissed_item_ids)
        if hasattr(self.catalog, "get_dismissed_item_ids"):
            try:
                db_dismissed = await self.catalog.get_dismissed_item_ids(session.session_id)
                dismissed_ids.update(db_dismissed)
            except Exception:
                pass

        # 10. Override Hierarchy Strict Short-Circuit (§21, §15)
        anchor_item_obj: MenuItem | None = None
        if anchor_item_name:
            # Match anchor item from candidates or construct lightweight proxy
            for it in sanitized_candidates:
                if it.name.lower() == anchor_item_name.lower():
                    anchor_item_obj = it
                    break
            if not anchor_item_obj:
                from app.domain.catalog.value_objects import Price, CategorySlug
                anchor_item_obj = MenuItem(
                    id=0,
                    name=anchor_item_name,
                    price=Price(anchor_price or Decimal("0")),
                    category=CategorySlug.BURGER if "burger" in str(anchor_category or "").lower() else CategorySlug.SIDE,
                )

        valid_items, filters_applied = self.constraint_filter.filter_with_reasons(
            candidates=sanitized_candidates,
            session=session,
            cart_item_ids=cart_item_ids,
            rejected_item_ids=dismissed_ids,
            suppressed_categories=suppressed_categories,
            anchor_price=anchor_price,
            max_price_ratio=2.5,
            branch_id=branch_id,
            anchor_item=anchor_item_obj,
            mode=job_code,
        )
        candidates_after_filter = [it.id for it in valid_items]

        # 11. Handle Zero Candidates Fallback Graph (§17)
        if not valid_items:
            fallback_res: FallbackResult = await self.fallback_graph.resolve(
                trigger_reason="all_generators_empty" if not tagged_candidates else "scoring_zero_candidates",
                category=active_category,
                session_mindset=profile.persona,
                branch_id=branch_id,
                limit=target_limit,
                circadian_hour=circadian_hour,
            )
            valid_items = fallback_res.items
            fallback_level = fallback_res.level
            fallback_trigger = fallback_res.trigger_reason

        # 12. Latency Tier Dispatch (§16) — Groq LLM Synergy
        cognitive_multipliers = {}
        cognitive_rationale = "Heuristic baseline"
        if job_cfg.latency_tier == "LIGHT" or not job_cfg.llm_enabled:
            # LIGHT Tier: Skip LLM call to guarantee sub-50ms latency
            cognitive_rationale = "LIGHT tier — LLM skipped for sub-50ms speed"
        elif cart_lines and len(valid_items) > 0:
            # FULL Tier: Run LLM cognitive reasoner
            try:
                cart_dicts = [
                    {
                        "name": getattr(l, "item_name", l.get("name") if isinstance(l, dict) else ""),
                        "price": float(getattr(l, "unit_price", l.get("price") if isinstance(l, dict) else 0).amount if hasattr(getattr(l, "unit_price", None), "amount") else getattr(l, "unit_price", 0)),
                    }
                    for l in cart_lines
                ]
                cognitive_multipliers, cognitive_rationale = await self.cognitive_reasoner.analyze_synergy(
                    session_id=session.session_id,
                    cart_items=cart_dicts,
                    candidates=valid_items,
                    session_preference=session.food_preference,
                )
            except Exception:
                cognitive_multipliers = {}

        # 13. Statistical Scoring (Stage 3 & 4)
        scored_candidates = self.ranker.score_candidates(
            candidates=valid_items,
            session=session,
            cart_item_ids=cart_item_ids,
            cross_sell_ids=cross_sell_ids,
            anchor_item_name=anchor_item_name,
            anchor_category=anchor_category,
            anchor_price=anchor_price,
            cart_total=cart_total,
            reward_threshold=reward_threshold,
            reward_name=reward_name,
            cognitive_multipliers=cognitive_multipliers,
            category_dismissal_counts=profile.category_dismissal_counts,
            customer_persona=profile.persona,
            circadian_hour=circadian_hour,
        )

        # 14. Sub-Role Aware MMR Diversity (§13)
        mmr_reranked = self.ranker.diversity.rerank(
            candidates=scored_candidates,
            top_k=target_limit * 2,
            job_code=job_code,
        )

        # Apply slot diversity on top of MMR candidates
        final_candidates_items = self.ranker.apply_slot_diversity(
            scored_candidates=mmr_reranked if mmr_reranked else scored_candidates,
            target_categories=target_categories,
            suppressed_categories=suppressed_categories,
            limit=target_limit,
        )

        # 15. Score Calibration & Gatekeeper (§18)
        evidence_per_candidate = {}
        for c in scored_candidates:
            raw_s = c.weighted_score
            calibrated_s = ScoreCalibrator.calibrate(raw_s, job_code=job_code)
            evidence_per_candidate[str(c.item.id)] = {
                "raw_score": round(raw_s, 4),
                "calibrated_score": round(calibrated_s, 4),
                "action_intent_weight": ACTION_WEIGHT["added_to_cart"],
                "breakdown": {s.signal_name: round(s.raw_score, 4) for s in c.scores},
            }

        top_raw = scored_candidates[0].weighted_score if scored_candidates else 0.0
        top_calibrated = ScoreCalibrator.calibrate(top_raw, job_code=job_code)

        should_silence, gate_reason = Gatekeeper.should_silence(
            candidate_count=len(final_candidates_items),
            top_score=top_calibrated,
            session_dismissals=len(dismissed_ids),
            confidence_floor=0.15,
        )

        gate_decision = "silenced:" + gate_reason if should_silence else "shown"
        if should_silence:
            final_candidates_items = []

        latency_ms = (time.time() - start_time) * 1000.0

        # 16. Full Replayable Decision Trace (§19)
        build_trace(
            session_id=session.session_id,
            job_code=job_code,
            context_snapshot=safe_context_snapshot,
            candidates_generated=candidates_generated_log,
            filters_applied=filters_applied,
            candidates_after_filter=candidates_after_filter,
            evidence_per_candidate=evidence_per_candidate,
            diversity_pass_applied=True,
            diversity_lambda=job_cfg.mmr_lambda,
            gate_decision=gate_decision,
            selected_items=[it.id for it in final_candidates_items],
            fallback_level_used=fallback_level,
            fallback_trigger=fallback_trigger,
            latency_ms=round(latency_ms, 2),
            experiment_arm=experiment_arm,
            policy_version=policy_version,
        )

        # Extract breakdown dicts for presentation layer
        score_breakdowns = {
            int(k): v.get("breakdown", {})
            for k, v in evidence_per_candidate.items()
        }

        return final_candidates_items, score_breakdowns, source_map
