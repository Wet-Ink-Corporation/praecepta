"""Unit tests for context assembler."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from praecepta.infra.codeintel.assembly.context_assembler import DefaultContextAssembler
from praecepta.infra.codeintel.assembly.schemas import ContextQuery, RepoSummary
from praecepta.infra.codeintel.exceptions import CodeIntelError
from praecepta.infra.codeintel.protocols import ContextAssembler
from praecepta.infra.codeintel.types import QueryIntent, SymbolSignature


def _make_sym(qualified_name: str = "mod.func_a", file_path: str = "mod.py") -> SymbolSignature:
    """Minimal SymbolSignature for test mocks."""
    return SymbolSignature(
        qualified_name=qualified_name,
        name=qualified_name.rsplit(".", 1)[-1],
        kind="function",
        language="python",
        file_path=file_path,
        start_line=1,
        end_line=5,
        signature=f"def {qualified_name.rsplit('.', 1)[-1]}():",
        docstring=None,
        parent_symbol=None,
        embedding_text="",
        token_count_estimate=10,
        last_modified=datetime.now(tz=UTC),
    )


def _make_assembler(
    structural: Any = None,
    semantic: Any = None,
    parser: Any = None,
    extractor: Any = None,
    repo_root: Path | None = None,
) -> DefaultContextAssembler:
    if semantic is None:
        semantic = AsyncMock()
        semantic.get_symbol_record.return_value = None
        semantic.search_by_name.return_value = []
        semantic.search.return_value = []
    return DefaultContextAssembler(
        structural_index=structural or cast("Any", MagicMock()),
        semantic_index=semantic,
        parser=parser or cast("Any", MagicMock()),
        extractor=extractor or cast("Any", MagicMock()),
        repo_root=repo_root or Path("."),
    )


@pytest.mark.unit
class TestDefaultContextAssembler:
    def test_conforms_to_protocol(self) -> None:
        assembler = _make_assembler()
        assert isinstance(assembler, ContextAssembler)

    @pytest.mark.asyncio
    async def test_query_validation_rejects_empty(self) -> None:
        assembler = _make_assembler()
        with pytest.raises(CodeIntelError, match="at least one"):
            await assembler.query(ContextQuery())

    @pytest.mark.asyncio
    async def test_natural_language_query_triggers_search(self) -> None:
        mock_semantic = AsyncMock()
        mock_semantic.search.return_value = [("mod.func_a", 0.9), ("mod.func_b", 0.7)]
        mock_semantic.search_by_name.return_value = []
        mock_semantic.get_symbol_record.return_value = None  # fall back to stub

        mock_structural = MagicMock()
        mock_structural.get_ranked_symbols.return_value = [("mod.func_a", 0.8)]
        mock_structural.get_dependencies.return_value = []

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
        )

        result = await assembler.query(
            ContextQuery(natural_language="how does login work?", token_budget=8000)
        )

        mock_semantic.search.assert_called_once()
        mock_structural.get_ranked_symbols.assert_called_once()
        assert result.total_tokens_used >= 0
        assert result.intent_detected == QueryIntent.UNDERSTAND

    @pytest.mark.asyncio
    async def test_direct_symbol_lookup_bypasses_search(self) -> None:
        sym = _make_sym("auth.login")

        mock_semantic = AsyncMock()
        mock_semantic.get_symbol_record.return_value = sym
        mock_semantic.search.return_value = []

        mock_structural = MagicMock()
        mock_structural.get_dependencies.return_value = []

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
        )

        result = await assembler.query(ContextQuery(symbol_names=["auth.login"], token_budget=8000))

        # search() should NOT be called for natural_language since it's None
        mock_semantic.search.assert_not_called()
        assert result.chunks_available >= 0

    @pytest.mark.asyncio
    async def test_deduplication_across_sources(self) -> None:
        sym = _make_sym("mod.func_a")

        mock_semantic = AsyncMock()
        mock_semantic.search.return_value = [("mod.func_a", 0.9)]
        mock_semantic.get_symbol_record.return_value = sym

        mock_structural = MagicMock()
        mock_structural.get_ranked_symbols.return_value = [("mod.func_a", 0.8)]
        mock_structural.get_dependencies.return_value = []

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
        )

        result = await assembler.query(
            ContextQuery(
                natural_language="func_a",
                symbol_names=["mod.func_a"],
                token_budget=8000,
            )
        )

        # mod.func_a appears in direct + semantic + structural but should only be included once
        names = [c.qualified_name for c in result.chunks]
        assert names.count("mod.func_a") == 1

    @pytest.mark.asyncio
    async def test_dependency_expansion(self) -> None:
        sym = _make_sym("mod.func_a")

        mock_semantic = AsyncMock()
        mock_semantic.get_symbol_record.return_value = sym
        mock_semantic.search.return_value = []

        mock_structural = MagicMock()
        mock_structural.get_dependencies.return_value = [
            ("mod.func_a", "mod.helper"),
        ]

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
        )

        result = await assembler.query(
            ContextQuery(
                symbol_names=["mod.func_a"],
                include_dependencies=True,
                dependency_depth=1,
                token_budget=8000,
            )
        )

        names = [c.qualified_name for c in result.chunks]
        assert "mod.helper" in names

    @pytest.mark.asyncio
    async def test_no_dependency_expansion_when_disabled(self) -> None:
        sym = _make_sym("mod.func_a")

        mock_semantic = AsyncMock()
        mock_semantic.get_symbol_record.return_value = sym
        mock_semantic.search.return_value = []

        mock_structural = MagicMock()
        mock_structural.get_dependencies.return_value = []

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
        )

        await assembler.query(
            ContextQuery(
                symbol_names=["mod.func_a"],
                include_dependencies=False,
                token_budget=8000,
            )
        )

        mock_structural.get_dependencies.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_symbol_returns_single_chunk(self) -> None:
        sym = _make_sym("mod.func_a")

        mock_semantic = AsyncMock()
        mock_semantic.get_symbol_record.return_value = sym

        assembler = _make_assembler(semantic=mock_semantic)

        chunk = await assembler.get_symbol("mod.func_a")
        assert chunk is not None
        assert chunk.qualified_name == "mod.func_a"
        assert chunk.kind == "function"
        assert chunk.language == "python"

    @pytest.mark.asyncio
    async def test_get_symbol_falls_back_to_search_by_name(self) -> None:
        """When exact lookup misses, fall back through search_by_name."""
        sym = _make_sym("mod.func_a")

        mock_semantic = AsyncMock()
        # First call (exact lookup) → None; second call (after search) → sym
        mock_semantic.get_symbol_record.side_effect = [None, sym]
        mock_semantic.search_by_name.return_value = ["mod.func_a"]

        assembler = _make_assembler(semantic=mock_semantic)

        chunk = await assembler.get_symbol("mod.func_a")
        assert chunk is not None
        assert chunk.qualified_name == "mod.func_a"

    @pytest.mark.asyncio
    async def test_get_symbol_returns_none_for_unknown(self) -> None:
        mock_semantic = AsyncMock()
        mock_semantic.get_symbol_record.return_value = None
        mock_semantic.search_by_name.return_value = []

        assembler = _make_assembler(semantic=mock_semantic)

        chunk = await assembler.get_symbol("nonexistent")
        assert chunk is None

    @pytest.mark.asyncio
    async def test_get_dependencies_delegates(self) -> None:
        mock_structural = MagicMock()
        mock_structural.get_dependencies.return_value = [
            ("mod.a", "mod.b"),
            ("mod.a", "mod.c"),
        ]

        assembler = _make_assembler(structural=mock_structural)

        chunks = await assembler.get_dependencies("mod.a", depth=1)
        mock_structural.get_dependencies.assert_called_once_with("mod.a", "both", 1)
        names = {c.qualified_name for c in chunks}
        assert "mod.b" in names
        assert "mod.c" in names

    @pytest.mark.asyncio
    async def test_get_repo_summary_delegates(self) -> None:
        summary = RepoSummary(
            total_files=10,
            total_symbols=50,
            languages={"python": 10},
            entry_points=[],
            top_symbols_by_pagerank=["main"],
            module_clusters=[],
        )
        mock_structural = MagicMock()
        mock_structural.get_repo_summary.return_value = summary

        assembler = _make_assembler(structural=mock_structural)

        result = await assembler.get_repo_summary()
        assert result.total_files == 10
        mock_structural.get_repo_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_semantic_index_still_works(self) -> None:
        """Cold start: semantic index empty, structural should still return results."""
        mock_semantic = AsyncMock()
        mock_semantic.search.return_value = []
        mock_semantic.get_symbol_record.return_value = None

        mock_structural = MagicMock()
        mock_structural.get_ranked_symbols.return_value = [("mod.main", 0.5)]
        mock_structural.get_dependencies.return_value = []

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
        )

        result = await assembler.query(ContextQuery(natural_language="anything", token_budget=8000))

        assert len(result.chunks) >= 1

    def test_discover_files_excludes_tests_by_default(self, tmp_path: Path) -> None:
        """_discover_files() must skip test files when include_tests=False (S-2)."""
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "service.py").write_text("def foo(): pass\n")
        (tmp_path / "tests" / "test_service.py").write_text("def test_foo(): pass\n")

        assembler = _make_assembler(repo_root=tmp_path)
        files = assembler._discover_files(include_tests=False)

        names = [f.name for f in files]
        assert "service.py" in names
        assert "test_service.py" not in names

    def test_discover_files_includes_tests_when_opted_in(self, tmp_path: Path) -> None:
        """_discover_files(include_tests=True) must include test files (S-2)."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_service.py").write_text("def test_foo(): pass\n")

        assembler = _make_assembler(repo_root=tmp_path)
        files = assembler._discover_files(include_tests=True)

        names = [f.name for f in files]
        assert "test_service.py" in names

    def test_discover_files_respects_exclude_patterns(self, tmp_path: Path) -> None:
        """_discover_files() must apply settings.exclude_patterns (S-3)."""
        from unittest.mock import patch

        from praecepta.infra.codeintel.settings import CodeIntelSettings

        node_modules = tmp_path / "node_modules" / "lodash"
        node_modules.mkdir(parents=True)
        (node_modules / "lodash.js").write_text("module.exports = {};")
        (tmp_path / "src.py").write_text("def foo(): pass\n")

        fake_settings = CodeIntelSettings(
            repo_root=str(tmp_path),
            exclude_patterns=["**/node_modules/**"],
        )
        assembler = _make_assembler(repo_root=tmp_path)
        with patch(
            "praecepta.infra.codeintel.settings.get_settings",
            return_value=fake_settings,
        ):
            files = assembler._discover_files()

        names = [f.name for f in files]
        assert "src.py" in names
        assert "lodash.js" not in names

    @pytest.mark.asyncio
    async def test_refresh_index(self, tmp_path: Path) -> None:
        py_file = tmp_path / "main.py"
        py_file.write_text("def hello(): pass\n")

        mock_parser = MagicMock()
        mock_parser.parse_file.return_value = MagicMock(
            tags=[], language="python", tree=MagicMock()
        )

        mock_extractor = MagicMock()
        mock_extractor.extract_symbols.return_value = []

        mock_structural = MagicMock()
        mock_semantic = AsyncMock()
        mock_semantic.upsert_symbols.return_value = 0

        assembler = _make_assembler(
            structural=mock_structural,
            semantic=mock_semantic,
            parser=mock_parser,
            extractor=mock_extractor,
            repo_root=tmp_path,
        )

        stats = await assembler.refresh_index(file_paths=[py_file])

        assert stats.files_indexed == 1
        mock_parser.parse_file.assert_called_once_with(py_file)
        mock_structural.build.assert_called_once()
