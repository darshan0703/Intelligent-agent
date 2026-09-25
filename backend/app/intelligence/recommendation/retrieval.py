"""
app/intelligence/recommendation/retrieval.py
Stage 1: Quota-Bounded Candidate Retrieval — v7 §12

Previous version: uncontrolled multi-source retrieval allowed whichever
generator returned the most candidates to silently dominate the ranked list
(usually 'popularity', since it never returns empty).

v7 fix: Every generator has an explicit max_candidates cap from GENERATOR_QUOTAS.
The pool entering ranking is a bounded, source-balanced mix — not whatever each
generator happened to produce. This also caps ranking cost (§16).

Each candidate is wrapped in a TaggedCandidate that carries its source and
provenance through the full pipeline, enabling the complete decision trace (§19).
"""
from __future__ import annotations
from typing import Any
from app.domain.catalog.entities import MenuItem
from app.domain.session.entities import SessionState
from app.intelligence.recommendation.job_config import GENERATOR_QUOTAS, get_job
from app.intelligence.recommendation.provenance import RelationshipTrust, TaggedCandidate
from app.ports.catalog_port import CatalogRepository


class QuotaBoundedRetriever:
    """
    Retrieves candidates from multiple generators, each strictly bounded by
    GENERATOR_QUOTAS[job_code][generator] = (max_candidates, min_candidates).

    The resulting pool is:
    - Bounded: never more than sum(max_candidates) per job
    - Source-balanced: each generator contributes independently, not crowded out
    - Tagged: every candidate knows which generator produced it (§22 provenance)
    """

    def __init__(self, catalog: CatalogRepository) -> None:
        self.catalog = catalog

    async def retrieve(
        self,
        session: SessionState,
        branch_id: int = 1,
        active_category: str | None = None,
        cart_item_ids: set[int] | None = None,
        job_code: str = "CLOSURE",
    ) -> tuple[list[MenuItem], set[int]]:
        """
        Backward-compatible method: returns (candidate_items, cross_sell_ids).
        Used by engine.py which assembles TaggedCandidates internally.
        """
        tagged, cross_sell_ids = await self.retrieve_tagged(
            session=session,
            branch_id=branch_id,
            active_category=active_category,
            cart_item_ids=cart_item_ids,
            job_code=job_code,
        )
        return [tc.item for tc in tagged], cross_sell_ids

    async def retrieve_tagged(
        self,
        session: SessionState,
        branch_id: int = 1,
        active_category: str | None = None,
        cart_item_ids: set[int] | None = None,
        job_code: str = "CLOSURE",
    ) -> tuple[list[TaggedCandidate], set[int]]:
        """
        Main retrieval entrypoint returning TaggedCandidates with provenance metadata.
        """
        cart_ids = cart_item_ids or set()
        quotas = GENERATOR_QUOTAS.get(job_code, GENERATOR_QUOTAS["CLOSURE"])
        job_cfg = get_job(job_code)
        cross_sell_ids: set[int] = set()
        seen_ids: set[int] = set()  # Deduplication across generators
        tagged_pool: list[TaggedCandidate] = []

        # ── GENERATOR: co_purchase ────────────────────────────────────────────
        max_co, _ = quotas.get("co_purchase", (0, 0))
        if max_co > 0 and "co_purchase" in job_cfg.generators:
            co_items = await self._run_co_purchase(session, cart_ids, max_co)
            for item in co_items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    cross_sell_ids.add(item.id)
                    tagged_pool.append(TaggedCandidate(
                        item=item,
                        source="co_purchase",
                        provenance_type=RelationshipTrust.classify_generator_source("co_purchase"),
                    ))

        # ── GENERATOR: semantic_fit ────────────────────────────────────────────
        max_sem, _ = quotas.get("semantic_fit", (0, 0))
        if max_sem > 0 and "semantic_fit" in job_cfg.generators:
            sem_items = await self._run_semantic_fit(
                session, active_category, branch_id, max_sem, cart_ids | seen_ids
            )
            for item in sem_items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    tagged_pool.append(TaggedCandidate(
                        item=item,
                        source="semantic_fit",
                        provenance_type=RelationshipTrust.classify_generator_source("semantic_fit"),
                    ))

        # ── GENERATOR: popularity ─────────────────────────────────────────────
        max_pop, min_pop = quotas.get("popularity", (0, 0))
        if max_pop > 0 and "popularity" in job_cfg.generators:
            pop_items = await self._run_popularity(active_category, branch_id, max_pop)
            pop_added = 0
            for item in pop_items:
                if item.id not in seen_ids and pop_added < max_pop:
                    seen_ids.add(item.id)
                    tagged_pool.append(TaggedCandidate(
                        item=item,
                        source="popularity",
                        provenance_type=RelationshipTrust.classify_generator_source("popularity"),
                    ))
                    pop_added += 1
            # Enforce min_candidates from popularity (the generator that never returns empty)
            if pop_added < min_pop:
                extra = await self._run_popularity(None, branch_id, min_pop - pop_added + 10)
                for item in extra:
                    if item.id not in seen_ids and pop_added < min_pop:
                        seen_ids.add(item.id)
                        tagged_pool.append(TaggedCandidate(
                            item=item,
                            source="popularity",
                            provenance_type="observed_co_purchase",
                        ))
                        pop_added += 1

        # ── GENERATOR: exploration ────────────────────────────────────────────
        max_exp, _ = quotas.get("exploration", (0, 0))
        if max_exp > 0 and "exploration" in job_cfg.generators:
            exp_items = await self._run_exploration(branch_id, max_exp, seen_ids)
            for item in exp_items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    tagged_pool.append(TaggedCandidate(
                        item=item,
                        source="exploration",
                        provenance_type=RelationshipTrust.classify_generator_source("exploration"),
                    ))

        return tagged_pool, cross_sell_ids

    # ── INDIVIDUAL GENERATOR IMPLEMENTATIONS ─────────────────────────────────

    async def _run_co_purchase(
        self, session: SessionState, cart_ids: set[int], max_count: int
    ) -> list[MenuItem]:
        """
        Co-occurrence generator: fetches cross-sell pairings for items
        currently in cart and the last viewed item.
        """
        trigger_ids = set(cart_ids)
        if session.last_item_id:
            trigger_ids.add(session.last_item_id)

        results: list[MenuItem] = []
        for tid in trigger_ids:
            if len(results) >= max_count:
                break
            try:
                pairs = await self.catalog.get_cross_sells(tid, limit=max_count)
                results.extend(pairs)
            except Exception:
                pass

        # Deduplicate within this generator's results before returning
        seen: set[int] = set()
        deduped = []
        for item in results:
            if item.id not in seen:
                seen.add(item.id)
                deduped.append(item)
        return deduped[:max_count]

    async def _run_semantic_fit(
        self,
        session: SessionState,
        active_category: str | None,
        branch_id: int,
        max_count: int,
        exclude_ids: set[int],
    ) -> list[MenuItem]:
        """
        Semantic fit generator: fetches items in the active category that
        complement the session's known preferences.
        Phase 1: Category-scoped retrieval with session dietary filter.
        Phase 2: Replace with actual embedding similarity lookup.
        """
        try:
            if active_category:
                items = await self.catalog.get_by_category(active_category, branch_id)
            else:
                # No active category: fetch complement categories based on cart gaps
                # Default to 'side' as the most universally complementary category
                items = await self.catalog.get_by_category("side", branch_id)

            # Apply dietary preference filter from session
            if session.food_preference:
                pref = session.food_preference.lower()
                if pref == "veg":
                    items = [
                        i for i in items
                        if i.food_type and "non" not in str(i.food_type).lower()
                    ]

            filtered = [i for i in items if i.id not in exclude_ids]
            return filtered[:max_count]
        except Exception:
            return []

    async def _run_popularity(
        self, category: str | None, branch_id: int, max_count: int
    ) -> list[MenuItem]:
        """
        Popularity generator: the fallback generator that never returns empty.
        Returns items sorted by display_order (a proxy for popularity in Phase 1;
        replaced by actual view/add-to-cart count in Phase 2).
        """
        try:
            if category:
                items = await self.catalog.get_by_category(category, branch_id)
            else:
                items = await self.catalog.get_all_available(branch_id)
            # Phase 1: sort by display_order as popularity proxy
            return sorted(
                [i for i in items if i.is_available],
                key=lambda i: getattr(i, "display_order", 999) or 999,
            )[:max_count]
        except Exception:
            return []

    async def _run_exploration(
        self, branch_id: int, max_count: int, exclude_ids: set[int]
    ) -> list[MenuItem]:
        """
        Exploration generator: surfaces novel or lesser-seen items.
        Phase 1: Returns items with highest display_order (less prominent = less seen).
        Phase 2: Replace with bandit-selected items that have high uncertainty (high Beta variance).
        """
        try:
            all_items = await self.catalog.get_all_available(branch_id)
            # Items with higher display_order numbers are shown less frequently
            # — use them as exploration candidates
            novel = sorted(
                [i for i in all_items if i.is_available and i.id not in exclude_ids],
                key=lambda i: getattr(i, "display_order", 0) or 0,
                reverse=True,  # Highest display_order = least prominent
            )
            return novel[:max_count]
        except Exception:
            return []


# ── BACKWARD-COMPATIBLE ALIAS ─────────────────────────────────────────────────
# Existing engine.py instantiates CandidateRetriever. Aliasing avoids breaking changes.
CandidateRetriever = QuotaBoundedRetriever
