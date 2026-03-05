"""Dataclass schemas for the context assembly pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

from praecepta.infra.codeintel.types import QueryIntent


@dataclass(frozen=True)
class SourceLocation:
    """Source file location with line and column ranges."""

    file_path: str
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0


@dataclass
class CodeChunk:
    """A single code chunk with identity, content, ranking, and relationships."""

    # Identity
    qualified_name: str
    name: str
    kind: str
    language: str
    location: SourceLocation
    signature: str
    docstring: str | None

    # Content
    source_code: str | None
    context_snippet: str | None

    # Ranking
    relevance_score: float
    structural_rank: float
    semantic_similarity: float
    retrieval_source: str

    # Relationships
    calls: list[str]
    called_by: list[str]
    imports: list[str]
    imported_by: list[str]

    # Token count
    token_count: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary, including nested SourceLocation."""
        result: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, SourceLocation):
                result[f.name] = {sf.name: getattr(value, sf.name) for sf in fields(value)}
            else:
                result[f.name] = value
        return result


@dataclass
class RepoSummary:
    """High-level summary of the indexed repository."""

    total_files: int
    total_symbols: int
    languages: dict[str, int]
    entry_points: list[str]
    top_symbols_by_pagerank: list[str]
    module_clusters: list[dict[str, Any]]


@dataclass
class ContextQuery:
    """A query for assembling code context."""

    natural_language: str | None = None
    symbol_names: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    intent: QueryIntent = QueryIntent.UNDERSTAND
    token_budget: int = 4096
    max_chunks: int = 20
    languages: list[str] = field(default_factory=list)
    symbol_kinds: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    include_dependencies: bool = True
    dependency_depth: int = 1
    include_tests: bool = False
    include_source_code: bool = True
    structural_weight: float = 0.5
    semantic_weight: float = 0.5

    def validate(self) -> None:
        """Raise CodeIntelError if no query criteria are set."""
        if not self.natural_language and not self.symbol_names and not self.file_paths:
            from praecepta.infra.codeintel.exceptions import CodeIntelError

            msg = "ContextQuery requires at least one of natural_language, symbol_names, or file_paths"
            raise CodeIntelError(msg, {})


@dataclass
class ContextResponse:
    """Response from the context assembly pipeline."""

    chunks: list[CodeChunk]
    total_tokens_used: int
    token_budget: int
    chunks_available: int
    repo_summary: RepoSummary | None = None
    query_echo: str | None = None
    intent_detected: QueryIntent | None = None
    search_terms_used: list[str] = field(default_factory=list)
    files_scanned: int = 0
    index_timestamp: str | None = None
    stale_files: list[str] = field(default_factory=list)

    @property
    def as_context_string(self) -> str:
        """Render as XML for LLM prompt injection."""
        from praecepta.infra.codeintel.assembly.renderer import render_context_xml

        return render_context_xml(self)
