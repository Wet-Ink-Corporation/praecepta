"""MCP tool definitions for code intelligence.

Each tool is a thin wrapper around ContextAssembler methods.
Tools are exposed both as:
  1. Closures inside create_mcp_server() for MCP protocol usage
  2. Module-level async functions accepting assembler as first arg (for testing)
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from praecepta.infra.codeintel.assembly.schemas import ContextQuery
from praecepta.infra.codeintel.types import QueryIntent

# ---------------------------------------------------------------------------
# Module-level functions (for direct testing)
# ---------------------------------------------------------------------------


async def code_context_search(
    assembler: Any,
    query: str = "",
    intent: str = "understand",
    token_budget: int = 4096,
    include_dependencies: bool = True,
    dependency_depth: int = 1,
    languages: list[str] | None = None,
    symbol_kinds: list[str] | None = None,
    include_tests: bool = False,
) -> dict[str, Any]:
    """Search the codebase for relevant context using natural language."""
    ctx_query = ContextQuery(
        natural_language=query,
        intent=QueryIntent(intent),
        token_budget=token_budget,
        include_dependencies=include_dependencies,
        dependency_depth=dependency_depth,
        languages=languages or [],
        symbol_kinds=symbol_kinds or [],
        include_tests=include_tests,
    )
    response = await assembler.query(ctx_query)
    return _response_to_dict(response)


async def code_symbol_lookup(
    assembler: Any,
    qualified_name: str = "",
) -> dict[str, Any]:
    """Look up a specific symbol by its qualified name."""
    chunk = await assembler.get_symbol(qualified_name)
    if chunk is None:
        return {"error": f"Symbol not found: {qualified_name}"}
    result: dict[str, Any] = chunk.to_dict()
    return result


async def code_dependency_graph(
    assembler: Any,
    qualified_name: str = "",
    depth: int = 1,
    direction: str = "both",
) -> dict[str, Any]:
    """Explore the dependency graph around a symbol."""
    chunks = await assembler.get_dependencies(
        qualified_name,
        depth=depth,
        direction=direction,
    )
    return {"symbol": qualified_name, "dependencies": [c.to_dict() for c in chunks]}


async def code_repo_overview(
    assembler: Any,
) -> dict[str, Any]:
    """Get a high-level overview of the repository structure."""
    summary = await assembler.get_repo_summary()
    return asdict(summary)


async def code_index_refresh(
    assembler: Any,
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Refresh the code intelligence index."""
    paths = [Path(p) for p in file_paths] if file_paths else None
    stats = await assembler.refresh_index(paths)
    return asdict(stats)


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------


def create_mcp_server(
    assembler: Any,
    host: str = "127.0.0.1",
    port: int = 8420,
) -> FastMCP:
    """Create and configure the MCP server with all tools.

    Args:
        assembler: A DefaultContextAssembler (or compatible) instance.
        host: Bind host for network transports (default 127.0.0.1).
              Pass "0.0.0.0" to listen on all interfaces.
        port: Bind port for network transports (default 8420).
              Ignored when using stdio transport.

    Note on transport / host / port: ``FastMCP.run()`` accepts a *transport*
    string (``"stdio"``, ``"streamable-http"``, or legacy ``"sse"``), but host
    and port are **constructor** parameters — they cannot be passed to
    ``run()`` directly.  Always use this factory to set them.
    """
    mcp = FastMCP("code-intel", host=host, port=port)

    @mcp.tool()
    async def code_context_search_tool(
        query: str,
        intent: str = "understand",
        token_budget: int = 4096,
        include_dependencies: bool = True,
        dependency_depth: int = 1,
        languages: list[str] | None = None,
        symbol_kinds: list[str] | None = None,
        include_tests: bool = False,
    ) -> dict[str, Any]:
        """Search the codebase for relevant context using natural language.

        Returns ranked code chunks with signatures, source code, and dependency
        relationships, packed to fit within the specified token budget.

        Args:
            query: Natural language description of what you're looking for.
            intent: How you plan to use the context —
                    "understand" (breadth), "modify" (depth + deps),
                    "navigate" (structure), "generate" (similar patterns).
            token_budget: Maximum tokens in the response (default 4096).
            include_dependencies: Whether to expand results with dependency chain.
            dependency_depth: How many hops to walk in the dependency graph.
            languages: Filter results to specific languages.
            symbol_kinds: Filter to specific symbol types.
            include_tests: Whether to include test files in results.
        """
        return await code_context_search(
            assembler,
            query=query,
            intent=intent,
            token_budget=token_budget,
            include_dependencies=include_dependencies,
            dependency_depth=dependency_depth,
            languages=languages,
            symbol_kinds=symbol_kinds,
            include_tests=include_tests,
        )

    @mcp.tool()
    async def code_symbol_lookup_tool(qualified_name: str) -> dict[str, Any]:
        """Look up a specific symbol by its qualified name.

        Returns the full symbol definition including signature, docstring,
        source code, and relationships.

        Args:
            qualified_name: Fully qualified symbol name (e.g., "auth.service.authenticate").
        """
        return await code_symbol_lookup(assembler, qualified_name=qualified_name)

    @mcp.tool()
    async def code_dependency_graph_tool(
        qualified_name: str,
        depth: int = 1,
        direction: str = "both",
    ) -> dict[str, Any]:
        """Explore the dependency graph around a symbol.

        Returns symbols that call or are called by the target symbol,
        traversed up to the specified depth.

        Args:
            qualified_name: Symbol to explore dependencies for.
            depth: How many hops to traverse (default 1).
            direction: "callers", "callees", or "both" (default "both").
        """
        return await code_dependency_graph(
            assembler,
            qualified_name=qualified_name,
            depth=depth,
            direction=direction,
        )

    @mcp.tool()
    async def code_repo_overview_tool() -> dict[str, Any]:
        """Get a high-level overview of the repository structure.

        Returns file counts, symbol counts, language distribution,
        entry points, and top symbols by structural importance.
        """
        return await code_repo_overview(assembler)

    @mcp.tool()
    async def code_index_refresh_tool(file_paths: list[str] | None = None) -> dict[str, Any]:
        """Refresh the code intelligence index.

        Re-indexes specified files or the entire repository.

        Args:
            file_paths: Optional list of file paths to re-index. If None, re-indexes all.
        """
        return await code_index_refresh(assembler, file_paths=file_paths)

    return mcp


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _response_to_dict(response: Any) -> dict[str, Any]:
    """Convert ContextResponse to JSON-serializable dict."""
    return {
        "chunks": [c.to_dict() for c in response.chunks],
        "total_tokens_used": response.total_tokens_used,
        "token_budget": response.token_budget,
        "chunks_available": response.chunks_available,
        "context_string": response.as_context_string,
    }
