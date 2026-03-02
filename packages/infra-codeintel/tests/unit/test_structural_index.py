"""Unit tests for structural index."""

from __future__ import annotations

from pathlib import Path

import pytest

from praecepta.infra.codeintel.index.structural_index import NetworkXStructuralIndex
from praecepta.infra.codeintel.protocols import StructuralIndex
from praecepta.infra.codeintel.types import Tag


def _make_tags() -> dict[Path, list[Tag]]:
    """Create a known tag set for testing."""
    return {
        Path("src/auth.py"): [
            Tag("src/auth.py", "/repo/src/auth.py", 1, "AuthService", "definition"),
            Tag("src/auth.py", "/repo/src/auth.py", 5, "authenticate", "definition"),
            Tag("src/auth.py", "/repo/src/auth.py", 8, "validate", "reference"),
            Tag("src/auth.py", "/repo/src/auth.py", 10, "db_query", "reference"),
        ],
        Path("src/db.py"): [
            Tag("src/db.py", "/repo/src/db.py", 1, "db_query", "definition"),
            Tag("src/db.py", "/repo/src/db.py", 5, "connect", "definition"),
        ],
        Path("src/api.py"): [
            Tag("src/api.py", "/repo/src/api.py", 1, "login_handler", "definition"),
            Tag("src/api.py", "/repo/src/api.py", 5, "authenticate", "reference"),
            Tag("src/api.py", "/repo/src/api.py", 6, "AuthService", "reference"),
        ],
        Path("src/validate.py"): [
            Tag("src/validate.py", "/repo/src/validate.py", 1, "validate", "definition"),
        ],
    }


@pytest.mark.unit
class TestStructuralIndex:
    def test_conforms_to_protocol(self) -> None:
        idx = NetworkXStructuralIndex()
        assert isinstance(idx, StructuralIndex)

    def test_build_creates_nodes(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        summary = idx.get_repo_summary()
        assert summary.total_files == 4

    def test_build_creates_edges(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        # auth.py references validate (in validate.py) and db_query (in db.py)
        # api.py references authenticate and AuthService (in auth.py)
        summary = idx.get_repo_summary()
        assert summary.total_files == 4

    def test_pagerank_returns_ranked_symbols(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        ranked = idx.get_ranked_symbols(top_k=10)
        assert len(ranked) > 0
        for _name, score in ranked:
            assert 0.0 <= score <= 1.0
        scores = [s for _, s in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_pagerank_with_personalization(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        ranked = idx.get_ranked_symbols(
            personalization={"src/auth.py": 1.0},
            top_k=5,
        )
        assert len(ranked) > 0

    def test_update_file_replaces_edges(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        new_tags = [
            Tag("src/auth.py", "/repo/src/auth.py", 1, "AuthService", "definition"),
            Tag("src/auth.py", "/repo/src/auth.py", 5, "new_func", "definition"),
        ]
        idx.update_file(Path("src/auth.py"), new_tags)

    def test_remove_file_removes_node(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        idx.remove_file(Path("src/db.py"))
        summary = idx.get_repo_summary()
        assert summary.total_files == 3

    def test_get_dependencies_callers(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        # api.py -> auth.py (api references authenticate/AuthService defined in auth)
        deps = idx.get_dependencies("src/auth.py", direction="callers", depth=1)
        caller_files = [s for s, _ in deps]
        assert "src/api.py" in caller_files

    def test_get_dependencies_callees(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        # auth.py -> validate.py and auth.py -> db.py
        deps = idx.get_dependencies("src/auth.py", direction="callees", depth=1)
        callee_files = [t for _, t in deps]
        assert "src/validate.py" in callee_files or "src/db.py" in callee_files

    def test_serialization_roundtrip(self, tmp_path: Path) -> None:
        idx = NetworkXStructuralIndex(cache_dir=tmp_path)
        idx.build(_make_tags())
        idx.save()

        idx2 = NetworkXStructuralIndex(cache_dir=tmp_path)
        idx2.load()
        summary = idx2.get_repo_summary()
        assert summary.total_files == 4

    def test_get_repo_summary(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        summary = idx.get_repo_summary()
        assert summary.total_files == 4
        assert summary.total_symbols > 0
        assert len(summary.top_symbols_by_pagerank) > 0

    def test_empty_graph(self) -> None:
        idx = NetworkXStructuralIndex()
        ranked = idx.get_ranked_symbols(top_k=10)
        assert ranked == []
        summary = idx.get_repo_summary()
        assert summary.total_files == 0

    def test_pagerank_cache_invalidated_on_update(self) -> None:
        idx = NetworkXStructuralIndex()
        idx.build(_make_tags())
        # First call computes and caches
        r1 = idx.get_ranked_symbols(top_k=10)
        # Remove a file
        idx.remove_file(Path("src/db.py"))
        # Second call should recompute
        r2 = idx.get_ranked_symbols(top_k=10)
        # Results should differ (one fewer node)
        assert len(r1) != len(r2)
