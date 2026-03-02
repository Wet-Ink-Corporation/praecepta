"""Unit tests for token budget packing."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.assembly.packing import pack_to_budget
from praecepta.infra.codeintel.assembly.schemas import CodeChunk, SourceLocation
from praecepta.infra.codeintel.exceptions import BudgetExceededError


def _make_chunk(name: str, tokens: int) -> CodeChunk:
    return CodeChunk(
        qualified_name=f"module.{name}",
        name=name,
        kind="function",
        language="python",
        location=SourceLocation(file_path="mod.py", start_line=1, end_line=10),
        signature=f"def {name}():",
        docstring=None,
        source_code=f"def {name}():\n    pass",
        context_snippet=None,
        relevance_score=0.9,
        structural_rank=0.5,
        semantic_similarity=0.8,
        retrieval_source="semantic",
        calls=[],
        called_by=[],
        imports=[],
        imported_by=[],
        token_count=tokens,
    )


@pytest.mark.unit
class TestPackToBudget:
    def test_all_fit(self) -> None:
        chunks = [_make_chunk("a", 100), _make_chunk("b", 100), _make_chunk("c", 100)]
        selected, tokens_used, remaining = pack_to_budget(chunks, budget=500)
        assert len(selected) == 3
        assert tokens_used == 300
        assert remaining == 0

    def test_exact_budget_match(self) -> None:
        chunks = [_make_chunk("a", 200), _make_chunk("b", 200)]
        selected, tokens_used, remaining = pack_to_budget(chunks, budget=400)
        assert len(selected) == 2
        assert tokens_used == 400
        assert remaining == 0

    def test_overflow_packs_subset(self) -> None:
        chunks = [_make_chunk("a", 200), _make_chunk("b", 200), _make_chunk("c", 200)]
        selected, tokens_used, _remaining = pack_to_budget(chunks, budget=450)
        assert len(selected) >= 2
        assert tokens_used <= 450

    def test_zero_budget_raises(self) -> None:
        chunks = [_make_chunk("a", 100)]
        with pytest.raises(BudgetExceededError):
            pack_to_budget(chunks, budget=0)

    def test_single_chunk_exceeds_budget_raises(self) -> None:
        chunks = [_make_chunk("a", 1000)]
        with pytest.raises(BudgetExceededError):
            pack_to_budget(chunks, budget=50)

    def test_empty_chunks(self) -> None:
        selected, tokens_used, remaining = pack_to_budget([], budget=1000)
        assert selected == []
        assert tokens_used == 0
        assert remaining == 0

    def test_preserves_order(self) -> None:
        chunks = [_make_chunk("a", 100), _make_chunk("b", 100), _make_chunk("c", 100)]
        selected, _, _ = pack_to_budget(chunks, budget=250)
        names = [c.name for c in selected]
        assert names[0] == "a"
        assert names[1] == "b"
