"""Intent-aware ranking fusion for structural and semantic results."""

from __future__ import annotations

from praecepta.infra.codeintel.types import QueryIntent

INTENT_WEIGHTS: dict[QueryIntent, tuple[float, float]] = {
    # (semantic_weight, structural_weight)
    QueryIntent.UNDERSTAND: (0.5, 0.5),
    QueryIntent.MODIFY: (0.3, 0.7),
    QueryIntent.NAVIGATE: (0.2, 0.8),
    QueryIntent.GENERATE: (0.7, 0.3),
}

BOTH_SET_BOOST = 1.2


def _normalize(results: list[tuple[str, float]]) -> dict[str, float]:
    """Normalize scores to [0.0, 1.0]."""
    if not results:
        return {}
    max_score = max(score for _, score in results)
    min_score = min(score for _, score in results)
    range_ = max_score - min_score
    if range_ == 0:
        return {name: 1.0 for name, _ in results}
    return {name: (score - min_score) / range_ for name, score in results}


def fuse_rankings(
    structural_results: list[tuple[str, float]],
    semantic_results: list[tuple[str, float]],
    intent: QueryIntent,
    structural_weight: float | None = None,
    semantic_weight: float | None = None,
) -> list[tuple[str, float]]:
    """Fuse structural and semantic results with intent-aware weights."""
    sem_w, struct_w = INTENT_WEIGHTS[intent]
    if structural_weight is not None:
        struct_w = structural_weight
    if semantic_weight is not None:
        sem_w = semantic_weight

    norm_structural = _normalize(structural_results)
    norm_semantic = _normalize(semantic_results)

    all_names = set(norm_structural.keys()) | set(norm_semantic.keys())
    structural_names = set(norm_structural.keys())
    semantic_names = set(norm_semantic.keys())

    fused: dict[str, float] = {}
    for name in all_names:
        s_score = norm_structural.get(name, 0.0) * struct_w
        e_score = norm_semantic.get(name, 0.0) * sem_w
        score = s_score + e_score

        if name in structural_names and name in semantic_names:
            score *= BOTH_SET_BOOST

        fused[name] = min(score, 1.0)

    return sorted(fused.items(), key=lambda x: x[1], reverse=True)
