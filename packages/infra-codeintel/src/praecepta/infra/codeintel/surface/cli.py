"""CLI commands for code intelligence: serve, index, stats."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_assembler(repo: str, device: str) -> object:
    """Wire up the full assembler with real components.

    Returns a DefaultContextAssembler ready to use.
    Heavy imports are kept inside this function so `--help` stays instant.
    """
    from praecepta.infra.codeintel.assembly.context_assembler import DefaultContextAssembler
    from praecepta.infra.codeintel.extraction.semantic_extractor import TreeSitterSemanticExtractor
    from praecepta.infra.codeintel.index.embedding_encoder import JinaEmbeddingEncoder
    from praecepta.infra.codeintel.index.semantic_index import LanceDBSemanticIndex
    from praecepta.infra.codeintel.index.structural_index import NetworkXStructuralIndex
    from praecepta.infra.codeintel.parser.cst_parser import TreeSitterCSTParser
    from praecepta.infra.codeintel.settings import get_settings

    settings = get_settings()
    repo_path = Path(settings.repo_root).resolve()
    cache_dir = repo_path / settings.cache_dir

    parser = TreeSitterCSTParser(
        cache_dir=cache_dir / "cst",
        repo_root=repo_path,
    )
    extractor = TreeSitterSemanticExtractor()
    structural_index = NetworkXStructuralIndex(cache_dir=cache_dir)
    structural_index.load()

    encoder = JinaEmbeddingEncoder()
    semantic_index = LanceDBSemanticIndex(
        db_path=cache_dir / "lance.db",
        encoder=encoder,
    )

    return DefaultContextAssembler(
        structural_index=structural_index,
        semantic_index=semantic_index,
        parser=parser,
        extractor=extractor,
        repo_root=repo_path,
    )


@click.group()
@click.version_option()
def cli() -> None:
    """Code intelligence and context assembly for AI agents."""


@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="MCP transport",
)
@click.option("--port", default=8420, help="Port for SSE transport")
@click.option("--device", default="cpu", help="Embedding model device (cpu/cuda/mps)")
@click.option("--config", default=None, help="Path to code-intel.json config file")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def serve(
    repo: str, transport: str, port: int, device: str, config: str | None, verbose: bool
) -> None:
    """Start the MCP server."""
    import os

    _setup_logging(verbose)
    log = logging.getLogger(__name__)

    os.environ["CODE_INTEL_REPO_ROOT"] = str(Path(repo).resolve())
    os.environ["CODE_INTEL_EMBEDDING_DEVICE"] = device

    from praecepta.infra.codeintel.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    log.info("serve: repo=%s transport=%s port=%d", settings.repo_root, transport, port)

    try:
        from praecepta.infra.codeintel.surface.mcp_tools import create_mcp_server
    except ImportError as exc:
        click.echo(
            f"ERROR: MCP server dependencies missing ({exc}). Install with extras [mcp].",
            err=True,
        )
        sys.exit(1)

    assembler = _build_assembler(repo, device)
    server: Any = create_mcp_server(assembler)

    click.echo(f"Starting code-intel MCP server (transport={transport}, repo={repo})")

    # FastMCP.run() manages its own event loop
    if transport == "stdio":
        server.run()
    else:
        server.run(transport="sse", host="0.0.0.0", port=port)


@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option("--device", default="cpu", help="Embedding model device")
@click.option("--config", default=None, help="Path to code-intel.json config file")
@click.option("--include-tests", is_flag=True, default=False, help="Include test files in index")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def index(repo: str, device: str, config: str | None, include_tests: bool, verbose: bool) -> None:
    """Run a one-time full index of the repository."""
    import os

    _setup_logging(verbose)
    log = logging.getLogger(__name__)

    os.environ["CODE_INTEL_REPO_ROOT"] = str(Path(repo).resolve())
    os.environ["CODE_INTEL_EMBEDDING_DEVICE"] = device

    from praecepta.infra.codeintel.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    log.info("index: repo=%s device=%s include_tests=%s", settings.repo_root, device, include_tests)

    click.echo(f"Indexing repository: {settings.repo_root}")

    assembler = _build_assembler(repo, device)

    from praecepta.infra.codeintel.assembly.context_assembler import DefaultContextAssembler

    if not isinstance(assembler, DefaultContextAssembler):
        click.echo("ERROR: assembler construction failed", err=True)
        sys.exit(1)

    async def _run() -> None:
        stats = await assembler.refresh_index(include_tests=include_tests)
        click.echo(
            f"  Files indexed : {stats.files_indexed}\n"
            f"  Symbols found : {stats.symbols_indexed}\n"
            f"  Duration      : {stats.duration_ms:.0f} ms\n"
            f"  Languages     : {dict(sorted(stats.languages.items()))}"
        )

    asyncio.run(_run())


@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option("--config", default=None, help="Path to code-intel.json config file")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def stats(repo: str, config: str | None, output_json: bool, verbose: bool) -> None:
    """Print index statistics for the repository."""
    import os

    _setup_logging(verbose)

    os.environ["CODE_INTEL_REPO_ROOT"] = str(Path(repo).resolve())

    from praecepta.infra.codeintel.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    repo_path = Path(settings.repo_root).resolve()
    cache_dir = repo_path / settings.cache_dir

    # Structural index stats
    from praecepta.infra.codeintel.index.structural_index import NetworkXStructuralIndex

    structural = NetworkXStructuralIndex(cache_dir=cache_dir)
    structural.load()
    summary = structural.get_repo_summary()

    # LanceDB row count
    lancedb_rows: int = 0
    try:
        import lancedb  # type: ignore[import-untyped]

        db = lancedb.connect(str(cache_dir / "lance.db"))
        if "symbols" in db.list_tables():
            table = db.open_table("symbols")
            lancedb_rows = table.count_rows()
    except Exception:
        pass

    # graph.pkl size
    pkl_path = cache_dir / "graph.pkl"
    pkl_size = pkl_path.stat().st_size if pkl_path.exists() else 0

    data: dict[str, Any] = {
        "repo": str(repo_path),
        "cache_dir": str(cache_dir),
        "total_files": summary.total_files,
        "total_symbols": summary.total_symbols,
        "languages": summary.languages,
        "entry_points": summary.entry_points,
        "top_symbols_by_pagerank": summary.top_symbols_by_pagerank[:10],
        "semantic_index_rows": lancedb_rows,
        "structural_index_size_bytes": pkl_size,
    }

    if output_json:
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Repository     : {data['repo']}")
        click.echo(f"Cache dir      : {data['cache_dir']}")
        click.echo(f"Files indexed  : {data['total_files']}")
        click.echo(f"Symbols        : {data['total_symbols']}")
        click.echo(f"Semantic rows  : {data['semantic_index_rows']}")
        click.echo(f"Graph size     : {data['structural_index_size_bytes']:,} bytes")
        click.echo(f"Languages      : {data['languages']}")
        if data["entry_points"]:
            click.echo(f"Entry points   : {data['entry_points']}")
        if data["top_symbols_by_pagerank"]:
            click.echo("Top symbols (PageRank):")
            for sym in data["top_symbols_by_pagerank"]:
                click.echo(f"  {sym}")
