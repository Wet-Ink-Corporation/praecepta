"""Unit tests for MCP tool wrappers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

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
