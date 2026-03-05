"""Protocol interfaces for code intelligence components.

Each protocol defines the boundary contract for a major subsystem.
All protocols are @runtime_checkable for isinstance() validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from praecepta.infra.codeintel.assembly.schemas import (
        CodeChunk,
        ContextQuery,
        ContextResponse,
        RepoSummary,
    )
    from praecepta.infra.codeintel.types import (
        FileEvent,
        IndexStats,
        ParseResult,
        SymbolRelationship,
        SymbolSignature,
        Tag,
    )


@runtime_checkable
class CSTParser(Protocol):
    def parse_file(self, file_path: Path) -> ParseResult: ...
    def parse_file_incremental(self, file_path: Path, old_tree: object) -> ParseResult: ...
    def extract_tags(self, file_path: Path) -> list[Tag]: ...
    def get_supported_languages(self) -> list[str]: ...


@runtime_checkable
class SemanticExtractor(Protocol):
    def extract_symbols(
        self, file_path: Path, tags: list[Tag], tree: object
    ) -> list[SymbolSignature]: ...
    def extract_relationships(
        self, file_path: Path, tags: list[Tag]
    ) -> list[SymbolRelationship]: ...


@runtime_checkable
class StructuralIndex(Protocol):
    def build(self, all_tags: dict[Path, list[Tag]]) -> None: ...
    def update_file(self, file_path: Path, new_tags: list[Tag]) -> None: ...
    def remove_file(self, file_path: Path) -> None: ...
    def get_ranked_symbols(
        self,
        personalization: dict[str, float] | None = None,
        top_k: int = 50,
    ) -> list[tuple[str, float]]: ...
    def get_dependencies(
        self,
        qualified_name: str,
        direction: Literal["callers", "callees", "both"] = "both",
        depth: int = 1,
    ) -> list[tuple[str, str]]: ...
    def get_repo_summary(self) -> RepoSummary: ...


@runtime_checkable
class SemanticIndex(Protocol):
    async def upsert_symbols(self, symbols: list[SymbolSignature]) -> int: ...
    async def remove_symbols(self, qualified_names: list[str]) -> int: ...
    async def search(
        self,
        query_text: str,
        query_type: Literal["nl2code", "code2code", "techqa"] = "nl2code",
        top_k: int = 20,
        filters: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]: ...
    async def search_by_name(self, symbol_name: str, top_k: int = 10) -> list[str]: ...
    async def get_symbol_record(self, qualified_name: str) -> SymbolSignature | None: ...


@runtime_checkable
class ContextAssembler(Protocol):
    async def query(self, query: ContextQuery) -> ContextResponse: ...
    async def get_symbol(self, qualified_name: str) -> CodeChunk | None: ...
    async def get_dependencies(
        self,
        qualified_name: str,
        depth: int = 1,
        direction: Literal["callers", "callees", "both"] = "both",
    ) -> list[CodeChunk]: ...
    async def get_repo_summary(self) -> RepoSummary: ...
    async def refresh_index(self, file_paths: list[Path] | None = None) -> IndexStats: ...


@runtime_checkable
class FileWatcher(Protocol):
    def start(
        self,
        repo_root: Path,
        on_change: Callable[[list[FileEvent]], Awaitable[None]],
    ) -> None: ...
    def stop(self) -> None: ...
