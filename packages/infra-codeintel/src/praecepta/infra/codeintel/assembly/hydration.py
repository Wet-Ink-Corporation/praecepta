"""Hydrate CodeChunks with source code from disk at query time."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from praecepta.infra.codeintel.assembly.schemas import CodeChunk


def hydrate_chunk(
    chunk: CodeChunk,
    repo_root: Path,
    include_source: bool = True,
) -> CodeChunk:
    """Read source file and populate chunk.source_code."""
    result = copy.copy(chunk)

    if not include_source:
        result.source_code = None
        return result

    file_path = Path(chunk.location.file_path)
    if not file_path.is_absolute():
        file_path = repo_root / file_path

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        start = chunk.location.start_line - 1
        end = chunk.location.end_line
        result.source_code = "".join(lines[start:end])
    except (FileNotFoundError, OSError):
        result.source_code = None

    return result


def hydrate_chunks(
    chunks: list[CodeChunk],
    repo_root: Path,
    include_source: bool = True,
) -> list[CodeChunk]:
    """Hydrate multiple chunks."""
    return [hydrate_chunk(c, repo_root, include_source) for c in chunks]
