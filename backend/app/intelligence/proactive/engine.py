"""
app/intelligence/proactive/engine.py
TheAtom Proactive Commercial Intelligence Engine.

Discovers high-utility opportunities (Bundles, Gaps, Complements, Upgrades, Preferences),
evaluates them against the Usefulness Gate (Fatigue, Timing, Confidence),
and decides whether to surface an intervention or DO NOTHING.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime
from app.domain.catalog.entities import MenuItem
from app.domain.session.entities import SessionState
from app.ports.catalog_port import CatalogRepository
from app.intelligence.memory.memory_service import MemoryService
from app.observability.logging import get_logger

logger = get_logger("proactive_intelligence")

OpportunityType = Literal[
    "bundle_gap",
    "taste_pairing",
    "smart_upgrade",
    "dietary_favorite",
    "recovery",
]


@dataclass
class ProactiveOpportunity:
    opportunity_type: OpportunityType
    title: str
    description: str
    item: MenuItem
    savings_amount: Optional[float] = None
    confidence_score: float = 0.0
    rationale: str = ""
    spoken_hint: Optional[str] = None


class UsefulnessGate:
    MIN_CONFIDENCE_THRESHOLD = 0.65
    MAX_SESSION_DISMISSALS = 2

    @classmethod
    def evaluate(
        cls,
        opportunity: ProactiveOpportunity | None,
        session: SessionState,
        dismissals: list,
        current_screen: str | None = None,
    ) -> tuple[bool, str]:
        if not opportunity:
            return False, "no_opportunity_generated"

        screen_lower = (current_screen or "").lower()
        if any(w in screen_lower for w in ["payment", "paying", "pay", "complete", "order-complete"]):
            return False, "payment_moment_shield"

        # Check fatigue limit
        recent_dismissals = [
            d for d in dismissals
            if getattr(d, "predicate", "") == "dismissed"
        ]
        if len(recent_dismissals) >= cls.MAX_SESSION_DISMISSALS:
            return False, f"fatigue_limit_reached_{len(recent_dismissals)}_dismissals"

        # Check confidence threshold
        if opportunity.confidence_score < cls.MIN_CONFIDENCE_THRESHOLD:
            return False, f"confidence_too_low_{opportunity.confidence_score:.2f}"

        # Category level suppression
        opp_cat = str(getattr(opportunity.item, "category", "")).lower()
        for d in recent_dismissals:
            if getattr(d, "value", "") == opp_cat:
                return False, f"category_dismissed_recently_{opp_cat}"

        return True, "passed_usefulness_gate"


class ProactiveIntelligenceEngine:
    def __init__(self, catalog: CatalogRepository, memory: MemoryService):
        self.catalog = catalog
        self.memory = memory
        self.gate = UsefulnessGate()

    async def evaluate_opportunity(
        self,
        session: SessionState,
        cart_lines: list,
        current_screen: str | None = None,
        branch_id: int = 1,
    ) -> ProactiveOpportunity | None:
        # 1. Fast Moment Shield Check (Zero DB queries if on payment/completion screen)
        screen_lower = (current_screen or "").lower()
        if any(w in screen_lower for w in ["payment", "paying", "pay", "complete", "order-complete"]):
            logger.info("proactive_opportunity_filtered_by_gate", reason="payment_moment_shield")
            return None

        # 2. Check dismissals in session memory
        dismissals = await self.memory.store.get_observations(
            session_id=session.session_id,
            subject="proactive_offer",
        )
        recent_dismissals = [d for d in dismissals if getattr(d, "predicate", "") == "dismissed"]
        if len(recent_dismissals) >= UsefulnessGate.MAX_SESSION_DISMISSALS:
            logger.info("proactive_opportunity_filtered_by_gate", reason="fatigue_limit_reached")
            return None

        cart_item_ids = {getattr(l, "item_id", None) for l in cart_lines if getattr(l, "item_id", None) is not None}

        has_burger = False
        has_drink = False
        has_side = False
        has_dessert = False

        for l in cart_lines:
            cat = str(getattr(l, "category", "")).lower()
            l_type = getattr(l, "line_type", "")
            if "burger" in cat or l_type == "meal":
                has_burger = True
            if "drink" in cat or l_type == "meal":
                has_drink = True
            if "side" in cat or l_type == "meal":
                has_side = True
            if "dessert" in cat:
                has_dessert = True

        raw_candidates = await self.catalog.get_all_available(branch_id)
        pref = session.food_preference or ""
        if "veg" in pref.lower() and "non" not in pref.lower():
            raw_candidates = [c for c in raw_candidates if c.food_type and "veg" in str(c.food_type).lower()]

        candidates = [c for c in raw_candidates if c.id not in cart_item_ids and c.is_in_stock]

        opportunity: ProactiveOpportunity | None = None

        if has_drink and not has_side and not has_burger and candidates:
            side_candidates = [c for c in candidates if "side" in str(c.category).lower()]
            if side_candidates:
                best_side = side_candidates[0]
                opportunity = ProactiveOpportunity(
                    opportunity_type="taste_pairing",
                    title="Crispy Snack Pairing",
                    description=f"Pair your drink with hot, golden {best_side.name}",
                    item=best_side,
                    confidence_score=0.85,
                    rationale="Customer selected a beverage alone; suggest hot crispy side accompaniment.",
                    spoken_hint=f"Would you like some hot crispy {best_side.name} to enjoy with your drink?",
                )

        elif has_side and not has_drink and not has_burger and candidates:
            drink_candidates = [c for c in candidates if "drink" in str(c.category).lower()]
            if drink_candidates:
                best_drink = drink_candidates[0]
                opportunity = ProactiveOpportunity(
                    opportunity_type="bundle_gap",
                    title="Quench Your Thirst",
                    description=f"Wash down your crispy snacks with chilled {best_drink.name}",
                    item=best_drink,
                    confidence_score=0.86,
                    rationale="Customer selected crispy fries alone; thirst-quenching beverage needed.",
                    spoken_hint=f"Would you like a chilled {best_drink.name} to go with your fries?",
                )

        elif has_burger and not has_drink and candidates:
            drink_candidates = [c for c in candidates if "drink" in str(c.category).lower()]
            if drink_candidates:
                best_drink = drink_candidates[0]
                for cid in cart_item_ids:
                    try:
                        pairs = await self.catalog.get_cross_sells(cid, limit=2)
                        for p in pairs:
                            if "drink" in str(p.category).lower() and p.id not in cart_item_ids:
                                best_drink = p
                                break
                    except Exception:
                        pass

                opportunity = ProactiveOpportunity(
                    opportunity_type="bundle_gap",
                    title="Complete Your Order",
                    description=f"Add {best_drink.name} to quench your thirst",
                    item=best_drink,
                    confidence_score=0.88,
                    rationale="Customer selected burger without a beverage; high pairing affinity.",
                    spoken_hint=f"Would you like to pair your burger with a {best_drink.name}?",
                )

        elif has_burger and has_drink and not has_side and candidates:
            side_candidates = [c for c in candidates if "side" in str(c.category).lower()]
            if side_candidates:
                best_side = side_candidates[0]
                opportunity = ProactiveOpportunity(
                    opportunity_type="bundle_gap",
                    title="Add a Crispy Side",
                    description=f"Complement your meal with {best_side.name}",
                    item=best_side,
                    confidence_score=0.82,
                    rationale="Cart has burger and drink; missing crispy side companion.",
                    spoken_hint=f"How about adding some {best_side.name} to complete your meal?",
                )

        elif has_burger and has_side and not has_drink and candidates:
            drink_candidates = [c for c in candidates if "drink" in str(c.category).lower()]
            if drink_candidates:
                best_drink = drink_candidates[0]
                opportunity = ProactiveOpportunity(
                    opportunity_type="bundle_gap",
                    title="Complete Your Meal",
                    description=f"Quench your thirst with a chilled {best_drink.name}",
                    item=best_drink,
                    confidence_score=0.84,
                    rationale="Cart has burger and side; missing refreshing beverage.",
                    spoken_hint=f"Would you like a {best_drink.name} to complete your combo?",
                )

        elif has_burger and has_drink and has_side and not has_dessert and candidates:
            dessert_candidates = [c for c in candidates if "dessert" in str(c.category).lower()]
            if dessert_candidates:
                best_dessert = dessert_candidates[0]
                opportunity = ProactiveOpportunity(
                    opportunity_type="taste_pairing",
                    title="Sweet Finish",
                    description=f"Treat yourself to a {best_dessert.name}",
                    item=best_dessert,
                    confidence_score=0.74,
                    rationale="Full combo detected; post-meal sweet indulgence opportunity.",
                    spoken_hint=f"Would you like a {best_dessert.name} to finish off your meal?",
                )

        elif not cart_lines and current_screen and "burger" in current_screen.lower() and candidates:
            whopper = next((c for c in candidates if "whopper" in c.name.lower()), candidates[0])
            opportunity = ProactiveOpportunity(
                opportunity_type="dietary_favorite",
                title="Signature Favorite",
                description="Flame-grilled perfection, loved across India",
                item=whopper,
                confidence_score=0.70,
                rationale="Guest browsing burgers; surface signature hero item.",
                spoken_hint=f"Our {whopper.name} is a customer favorite today!",
            )

        passed, reason = UsefulnessGate.evaluate(
            opportunity=opportunity,
            session=session,
            dismissals=dismissals,
            current_screen=current_screen,
        )

        if not passed:
            logger.info("proactive_opportunity_filtered_by_gate", reason=reason)
            return None

        logger.info(
            "proactive_opportunity_surfaced",
            type=opportunity.opportunity_type,
            item=opportunity.item.name,
            confidence=opportunity.confidence_score,
            reason=reason,
        )
        return opportunity