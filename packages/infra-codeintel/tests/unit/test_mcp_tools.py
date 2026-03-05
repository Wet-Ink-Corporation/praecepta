"""Unit tests for MCP tool wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from praecepta.infra.codeintel.assembly.schemas import ContextResponse, RepoSummary
from praecepta.infra.codeintel.surface.mcp_tools import (
    code_context_search,
    code_dependency_graph,
    code_index_refresh,
    code_repo_overview,
    code_symbol_lookup,
)
from praecepta.infra.codeintel.types import IndexStats, QueryIntent


@pytest.mark.unit
class TestMCPTools:
    @pytest.mark.asyncio
    async def test_code_context_search_constructs_query(self) -> None:
        mock_assembler = AsyncMock()
        mock_assembler.query.return_value = ContextResponse(
            chunks=[],
            total_tokens_used=0,
            token_budget=4096,
            chunks_available=0,
        )
        # Call tool function with mock assembler
        result = await code_context_search(
            assembler=mock_assembler,
            query="find authentication functions",
            intent="modify",
            token_budget=8192,
        )
        # Verify assembler.query called with correct ContextQuery
        call_args = mock_assembler.query.call_args[0][0]
        assert call_args.natural_language == "find authentication functions"
        assert call_args.intent == QueryIntent.MODIFY
        assert call_args.token_budget == 8192
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_code_symbol_lookup_returns_dict(self) -> None:
        mock_assembler = AsyncMock()
        mock_assembler.get_symbol.return_value = None
        await code_symbol_lookup(assembler=mock_assembler, qualified_name="auth.login")
        mock_assembler.get_symbol.assert_called_once_with("auth.login")

    @pytest.mark.asyncio
    async def test_code_dependency_graph_passes_params(self) -> None:
        mock_assembler = AsyncMock()
        mock_assembler.get_dependencies.return_value = []
        await code_dependency_graph(
            assembler=mock_assembler,
            qualified_name="auth.login",
            depth=2,
            direction="callers",
        )
        mock_assembler.get_dependencies.assert_called_once_with(
            "auth.login", depth=2, direction="callers"
        )

    @pytest.mark.asyncio
    async def test_code_repo_overview_returns_dict(self) -> None:
        mock_assembler = AsyncMock()
        mock_assembler.get_repo_summary.return_value = RepoSummary(
            total_files=10,
            total_symbols=50,
            languages={"python": 10},
            entry_points=[],
            top_symbols_by_pagerank=[],
            module_clusters=[],
        )
        result = await code_repo_overview(assembler=mock_assembler)
        assert isinstance(result, dict)
        assert result["total_files"] == 10

    @pytest.mark.asyncio
    async def test_code_index_refresh_returns_stats(self) -> None:
        mock_assembler = AsyncMock()
        mock_assembler.refresh_index.return_value = IndexStats(
            files_indexed=5,
            symbols_indexed=20,
            duration_ms=500.0,
            languages={"python": 5},
        )
        result = await code_index_refresh(assembler=mock_assembler)
        assert result["files_indexed"] == 5


@pytest.mark.unit
class TestCreateMCPServer:
    def test_watch_false_no_lifespan(self) -> None:
        """create_mcp_server(watch=False) must not attach a lifespan."""
        from praecepta.infra.codeintel.surface.mcp_tools import create_mcp_server

        mock_assembler = MagicMock()
        server = create_mcp_server(mock_assembler, watch=False)
        # FastMCP stores lifespan on settings; None means no watcher wired
        assert server.settings.lifespan is None

    def test_watch_true_attaches_lifespan(self, tmp_path: Path) -> None:
        """create_mcp_server(watch=True, repo_root=...) must attach a lifespan callable."""
        from praecepta.infra.codeintel.surface.mcp_tools import create_mcp_server

        mock_assembler = MagicMock()
        server = create_mcp_server(mock_assembler, watch=True, repo_root=tmp_path)
        assert server.settings.lifespan is not None

    def test_watch_true_no_repo_root_no_lifespan(self) -> None:
        """watch=True without repo_root must silently skip watcher (no lifespan)."""
        from praecepta.infra.codeintel.surface.mcp_tools import create_mcp_server

        mock_assembler = MagicMock()
        server = create_mcp_server(mock_assembler, watch=True, repo_root=None)
        assert server.settings.lifespan is None

    @pytest.mark.asyncio
    async def test_lifespan_starts_and_stops_watcher(self, tmp_path: Path) -> None:
        """The lifespan context manager must start the watcher on enter and stop on exit."""
        from praecepta.infra.codeintel.surface.mcp_tools import _make_watcher_lifespan

        mock_assembler = MagicMock()
        mock_watcher = MagicMock()
        mock_pipeline = MagicMock()

        # The watcher classes are imported inside _lifespan via `from x import Y`,
        # so patch at the source module where the class is defined.
        with (
            patch(
                "praecepta.infra.codeintel.watcher.file_watcher.WatchdogFileWatcher",
                return_value=mock_watcher,
            ),
            patch(
                "praecepta.infra.codeintel.watcher.incremental_pipeline.IncrementalUpdatePipeline",
                return_value=mock_pipeline,
            ),
        ):
            lifespan = _make_watcher_lifespan(mock_assembler, tmp_path)
            async with lifespan(None):
                mock_watcher.start.assert_called_once_with(tmp_path, mock_pipeline.process_events)
            mock_watcher.stop.assert_called_once()
