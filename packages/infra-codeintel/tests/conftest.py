"""Shared fixtures for code intelligence tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from praecepta.infra.codeintel.types import SymbolSignature, Tag


def make_tag(
    name: str = "my_func",
    kind: Literal["definition", "reference"] = "definition",
    rel_fname: str = "src/main.py",
    fname: str = "/repo/src/main.py",
    line: int = 10,
) -> Tag:
    return Tag(rel_fname=rel_fname, fname=fname, line=line, name=name, kind=kind)


def make_symbol(
    qualified_name: str = "main.my_func",
    name: str = "my_func",
    kind: str = "function",
    language: str = "python",
    file_path: str = "src/main.py",
    start_line: int = 10,
    end_line: int = 20,
    signature: str = "def my_func() -> None:",
    docstring: str | None = "A test function.",
    parent_symbol: str | None = None,
    embedding_text: str = "def my_func() -> None:\n    A test function.",
    token_count_estimate: int = 50,
) -> SymbolSignature:
    return SymbolSignature(
        qualified_name=qualified_name,
        name=name,
        kind=kind,
        language=language,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        signature=signature,
        docstring=docstring,
        parent_symbol=parent_symbol,
        embedding_text=embedding_text,
        token_count_estimate=token_count_estimate,
        last_modified=datetime.now(tz=UTC),
    )
