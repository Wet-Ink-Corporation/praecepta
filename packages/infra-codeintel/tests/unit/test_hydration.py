"""Unit tests for disk hydration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from praecepta.infra.codeintel.assembly.hydration import hydrate_chunk
from praecepta.infra.codeintel.assembly.schemas import CodeChunk, SourceLocation

if TYPE_CHECKING:
    from pathlib import Path


def _make_chunk(file_path: str, start: int, end: int) -> CodeChunk:
    return CodeChunk(
        qualified_name="mod.func",
        name="func",
        kind="function",
        language="python",
        location=SourceLocation(file_path=file_path, start_line=start, end_line=end),
        signature="def func():",
        docstring=None,
        source_code=None,
        context_snippet=None,
        relevance_score=0.9,
        structural_rank=0.5,
        semantic_similarity=0.8,
        retrieval_source="semantic",
        calls=[],
        called_by=[],
        imports=[],
        imported_by=[],
        token_count=20,
    )


@pytest.mark.unit
class TestHydration:
    def test_extracts_correct_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        lines = ["line 1\n", "def func():\n", "    pass\n", "line 4\n"]
        f.write_text("".join(lines))
        chunk = _make_chunk(str(f), start=2, end=3)
        hydrated = hydrate_chunk(chunk, repo_root=tmp_path)
        assert hydrated.source_code == "def func():\n    pass\n"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        chunk = _make_chunk(str(tmp_path / "nonexistent.py"), start=1, end=5)
        hydrated = hydrate_chunk(chunk, repo_root=tmp_path)
        assert hydrated.source_code is None

    def test_signatures_only_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("def func():\n    pass\n")
        chunk = _make_chunk(str(f), start=1, end=2)
        hydrated = hydrate_chunk(chunk, repo_root=tmp_path, include_source=False)
        assert hydrated.source_code is None

    def test_does_not_mutate_original(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("def func():\n    pass\n")
        chunk = _make_chunk(str(f), start=1, end=2)
        assert chunk.source_code is None
        hydrated = hydrate_chunk(chunk, repo_root=tmp_path)
        assert hydrated.source_code is not None
        assert chunk.source_code is None  # original unchanged

    def test_relative_path_resolved(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("def func():\n    pass\n")
        chunk = _make_chunk("mod.py", start=1, end=2)  # relative path
        hydrated = hydrate_chunk(chunk, repo_root=tmp_path)
        assert hydrated.source_code is not None
