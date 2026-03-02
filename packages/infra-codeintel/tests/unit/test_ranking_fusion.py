"""Unit tests for ranking fusion algorithm."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.assembly.ranking import fuse_rankings
from praecepta.infra.codeintel.types import QueryIntent


@pytest.mark.unit
class TestFuseRankings:
    def test_known_scores_fused_correctly(self) -> None:
        structural = [("auth.login", 0.9), ("db.query", 0.5), ("api.handler", 0.3)]
        semantic = [("auth.login", 0.8), ("util.hash", 0.6), ("api.handler", 0.4)]
        result = fuse_rankings(structural, semantic, QueryIntent.UNDERSTAND)
        names = [name for name, _ in result]
        assert names[0] == "auth.login"

    def test_understand_equal_weights(self) -> None:
        structural = [("a", 1.0)]
        semantic = [("b", 1.0)]
        result = fuse_rankings(structural, semantic, QueryIntent.UNDERSTAND)
        scores = dict(result)
        assert abs(scores["a"] - scores["b"]) < 0.01

    def test_modify_favors_structural(self) -> None:
        structural = [("a", 1.0)]
        semantic = [("b", 1.0)]
        result = fuse_rankings(structural, semantic, QueryIntent.MODIFY)
        scores = dict(result)
        assert scores["a"] > scores["b"]

    def test_generate_favors_semantic(self) -> None:
        structural = [("a", 1.0)]
        semantic = [("b", 1.0)]
        result = fuse_rankings(structural, semantic, QueryIntent.GENERATE)
        scores = dict(result)
        assert scores["b"] > scores["a"]

    def test_both_set_bonus_applied(self) -> None:
        structural = [("a", 0.5)]
        semantic = [("a", 0.5)]
        result_both = fuse_rankings(structural, semantic, QueryIntent.UNDERSTAND)

        structural_only = [("a", 0.5)]
        semantic_only: list[tuple[str, float]] = []
        result_one = fuse_rankings(structural_only, semantic_only, QueryIntent.UNDERSTAND)

        score_both = dict(result_both)["a"]
        score_one = dict(result_one)["a"]
        assert score_both > score_one

    def test_both_set_bonus_capped_at_one(self) -> None:
        structural = [("a", 1.0)]
        semantic = [("a", 1.0)]
        result = fuse_rankings(structural, semantic, QueryIntent.UNDERSTAND)
        score = dict(result)["a"]
        assert score <= 1.0

    def test_weight_overrides(self) -> None:
        structural = [("a", 1.0)]
        semantic = [("b", 1.0)]
        result = fuse_rankings(
            structural,
            semantic,
            QueryIntent.UNDERSTAND,
            structural_weight=0.9,
            semantic_weight=0.1,
        )
        scores = dict(result)
        assert scores["a"] > scores["b"]

    def test_empty_results(self) -> None:
        result = fuse_rankings([], [], QueryIntent.UNDERSTAND)
        assert result == []

    def test_output_sorted_descending(self) -> None:
        structural = [("a", 0.3), ("b", 0.7), ("c", 0.5)]
        semantic = [("d", 0.9), ("a", 0.1)]
        result = fuse_rankings(structural, semantic, QueryIntent.UNDERSTAND)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)
