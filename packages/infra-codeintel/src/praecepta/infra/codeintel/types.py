from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


class Tag(NamedTuple):
    """A structural tag extracted from source code via tree-sitter .scm queries."""

    rel_fname: str
    fname: str
    line: int
    name: str
    kind: Literal["definition", "reference"]


@dataclass(frozen=True)
class FileEvent:
    path: Path
    event_type: Literal["created", "modified", "deleted"]
    timestamp: datetime


@dataclass(frozen=True)
class ParseResult:
    tree: object  # tree_sitter.Tree
    tags: list[Tag]
    language: str
    parse_duration_ms: float


@dataclass
class SymbolSignature:
    qualified_name: str
    name: str
    kind: str  # function, class, method, etc.
    language: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: str | None
    parent_symbol: str | None
    embedding_text: str
    token_count_estimate: int
    last_modified: datetime


@dataclass(frozen=True)
class SymbolRelationship:
    source: str
    target: str
    kind: str  # calls, imports, inherits, implements, decorates


class QueryIntent(StrEnum):
    UNDERSTAND = "understand"
    MODIFY = "modify"
    NAVIGATE = "navigate"
    GENERATE = "generate"


@dataclass
class IndexStats:
    files_indexed: int
    symbols_indexed: int
    duration_ms: float
    languages: dict[str, int]
