"""
app/intelligence/recommendation/diversity.py
Maximal Marginal Relevance (MMR) re-ranking for recommendation diversity.
"""
from __future__ import annotations
from app.domain.recommendation.entities import Candidate


class MMRDiversity:
    def rerank(self, candidates: list[Candidate], top_k: int = 8, lambda_param: float = 0.7) -> list[Candidate]:
        if not candidates or len(candidates) <= top_k:
            return sorted(candidates, key=lambda c: c.weighted_score, reverse=True)

        selected: list[Candidate] = []
        remaining = list(candidates)

        remaining.sort(key=lambda c: c.weighted_score, reverse=True)
        selected.append(remaining.pop(0))

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_mmr = -999.0

            for i, cand in enumerate(remaining):
                relevance = cand.weighted_score
                similarity = max(
                    1.0 if cand.item.category == s.item.category and cand.item.food_type == s.item.food_type else 0.2
                    for s in selected
                )
                mmr_score = lambda_param * relevance - (1.0 - lambda_param) * similarity
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected
