"""Unit tests for code intelligence protocol interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import pytest

from praecepta.infra.codeintel.protocols import (
    ContextAssembler,
    CSTParser,
    FileWatcher,
    SemanticExtractor,
    SemanticIndex,
    StructuralIndex,
)
from praecepta.infra.codeintel.types import (
    FileEvent,
    IndexStats,
    ParseResult,
    SymbolRelationship,
    SymbolSignature,
    Tag,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

# ---------------------------------------------------------------------------
# Stub implementations
# ---------------------------------------------------------------------------


class StubCSTParser:
    def parse_file(self, file_path: Path) -> ParseResult:
        return ParseResult(tree=object(), tags=[], language="python", parse_duration_ms=0.0)

    def parse_file_incremental(self, file_path: Path, old_tree: object) -> ParseResult:
        return ParseResult(tree=object(), tags=[], language="python", parse_duration_ms=0.0)

    def extract_tags(self, file_path: Path) -> list[Tag]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["python"]


class StubSemanticExtractor:
    def extract_symbols(
        self, file_path: Path, tags: list[Tag], tree: object
    ) -> list[SymbolSignature]:
        return []

    def extract_relationships(self, file_path: Path, tags: list[Tag]) -> list[SymbolRelationship]:
        return []


class StubStructuralIndex:
    def build(self, all_tags: dict[Path, list[Tag]]) -> None:
        pass

    def update_file(self, file_path: Path, new_tags: list[Tag]) -> None:
        pass

    def remove_file(self, file_path: Path) -> None:
        pass

    def get_ranked_symbols(
        self,
        personalization: dict[str, float] | None = None,
        top_k: int = 50,
    ) -> list[tuple[str, float]]:
        return []

    def get_dependencies(
        self,
        qualified_name: str,
        direction: Literal["callers", "callees", "both"] = "both",
        depth: int = 1,
    ) -> list[tuple[str, str]]:
        return []

    def get_repo_summary(self) -> Any:
        return None


class StubSemanticIndex:
    async def upsert_symbols(self, symbols: list[SymbolSignature]) -> int:
        return 0

    async def remove_symbols(self, qualified_names: list[str]) -> int:
        return 0

    async def search(
        self,
        query_text: str,
        query_type: Literal["nl2code", "code2code", "techqa"] = "nl2code",
        top_k: int = 20,
        filters: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        return []

    async def search_by_name(self, symbol_name: str, top_k: int = 10) -> list[str]:
        return []

    async def get_symbol_record(self, qualified_name: str) -> SymbolSignature | None:
        return None


class StubContextAssembler:
    async def query(self, query: Any) -> Any:
        return None

    async def get_symbol(self, qualified_name: str) -> Any:
        return None

    async def get_dependencies(
        self,
        qualified_name: str,
        depth: int = 1,
        direction: Literal["callers", "callees", "both"] = "both",
    ) -> list[Any]:
        return []

    async def get_repo_summary(self) -> Any:
        return None

    async def refresh_index(self, file_paths: list[Path] | None = None) -> IndexStats:
        return IndexStats(files_indexed=0, symbols_indexed=0, duration_ms=0.0, languages={})


class StubFileWatcher:
    def start(
        self,
        repo_root: Path,
        on_change: Callable[[list[FileEvent]], Awaitable[None]],
    ) -> None:
        pass

    def stop(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCSTParserProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubCSTParser(), CSTParser)


@pytest.mark.unit
class TestSemanticExtractorProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubSemanticExtractor(), SemanticExtractor)


@pytest.mark.unit
class TestStructuralIndexProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubStructuralIndex(), StructuralIndex)


@pytest.mark.unit
class TestSemanticIndexProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubSemanticIndex(), SemanticIndex)


@pytest.mark.unit
class TestContextAssemblerProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubContextAssembler(), ContextAssembler)


@pytest.mark.unit
class TestFileWatcherProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubFileWatcher(), FileWatcher)
