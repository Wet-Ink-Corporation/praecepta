"""CLI commands for code intelligence: serve, index, stats."""

from __future__ import annotations

import click


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
def serve(repo: str, transport: str, port: int, device: str, config: str | None) -> None:
    """Start the MCP server."""
    import os

    os.environ["CODE_INTEL_REPO_ROOT"] = repo
    os.environ["CODE_INTEL_EMBEDDING_DEVICE"] = device

    from praecepta.infra.codeintel.settings import get_settings

    get_settings.cache_clear()

    # Build assembler with all components
    # Create MCP server
    # Start server with specified transport
    click.echo(f"Starting code-intel MCP server (transport={transport}, repo={repo})")


@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option("--device", default="cpu", help="Embedding model device")
@click.option("--config", default=None, help="Path to code-intel.json config file")
def index(repo: str, device: str, config: str | None) -> None:
    """Run a one-time full index of the repository."""
    import os

    os.environ["CODE_INTEL_REPO_ROOT"] = repo
    os.environ["CODE_INTEL_EMBEDDING_DEVICE"] = device

    click.echo(f"Indexing repository: {repo}")
    # Walk files, parse, extract, build indexes
    # Report stats


@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option("--config", default=None, help="Path to code-intel.json config file")
def stats(repo: str, config: str | None) -> None:
    """Print index statistics for the repository."""
    import os

    os.environ["CODE_INTEL_REPO_ROOT"] = repo

    # Load existing indexes
    # Print: files, symbols, languages, index age
    click.echo(f"Index statistics for: {repo}")
