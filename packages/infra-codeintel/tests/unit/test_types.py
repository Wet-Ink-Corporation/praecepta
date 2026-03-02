"""Unit tests for code intelligence value objects."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from praecepta.infra.codeintel.types import (
    FileEvent,
    IndexStats,
    ParseResult,
    QueryIntent,
    SymbolRelationship,
    SymbolSignature,
    Tag,
)


@pytest.mark.unit
class TestTag:
    def test_tag_creation(self) -> None:
        tag = Tag(
            rel_fname="src/main.py",
            fname="/repo/src/main.py",
            line=10,
            name="foo",
            kind="definition",
        )
        assert tag.rel_fname == "src/main.py"
        assert tag.fname == "/repo/src/main.py"
        assert tag.line == 10
        assert tag.name == "foo"
        assert tag.kind == "definition"

    def test_tag_equality(self) -> None:
        t1 = Tag("a.py", "/a.py", 1, "x", "definition")
        t2 = Tag("a.py", "/a.py", 1, "x", "definition")
        assert t1 == t2

    def test_tag_hashable(self) -> None:
        tag = Tag("a.py", "/a.py", 1, "x", "definition")
        assert hash(tag) == hash(Tag("a.py", "/a.py", 1, "x", "definition"))
        assert len({tag, tag}) == 1

    def test_tag_as_namedtuple_indexing(self) -> None:
        tag = Tag("a.py", "/a.py", 1, "x", "reference")
        assert tag[0] == "a.py"
        assert tag[4] == "reference"


@pytest.mark.unit
class TestFileEvent:
    def test_file_event_creation(self) -> None:
        ts = datetime.now(tz=UTC)
        event = FileEvent(path=Path("/repo/src/a.py"), event_type="modified", timestamp=ts)
        assert event.path == Path("/repo/src/a.py")
        assert event.event_type == "modified"
        assert event.timestamp == ts

    def test_file_event_is_frozen(self) -> None:
        ts = datetime.now(tz=UTC)
        event = FileEvent(path=Path("/a.py"), event_type="created", timestamp=ts)
        with pytest.raises(AttributeError):
            event.path = Path("/b.py")  # type: ignore[misc]


@pytest.mark.unit
class TestParseResult:
    def test_parse_result_creation(self) -> None:
        tag = Tag("a.py", "/a.py", 1, "x", "definition")
        result = ParseResult(tree=object(), tags=[tag], language="python", parse_duration_ms=1.5)
        assert result.language == "python"
        assert len(result.tags) == 1
        assert result.parse_duration_ms == 1.5


@pytest.mark.unit
class TestSymbolSignature:
    def test_symbol_signature_creation(self) -> None:
        now = datetime.now(tz=UTC)
        sig = SymbolSignature(
            qualified_name="main.foo",
            name="foo",
            kind="function",
            language="python",
            file_path="src/main.py",
            start_line=10,
            end_line=20,
            signature="def foo() -> None:",
            docstring="A function.",
            parent_symbol=None,
            embedding_text="def foo() -> None:\n    A function.",
            token_count_estimate=25,
            last_modified=now,
        )
        assert sig.qualified_name == "main.foo"
        assert sig.docstring == "A function."
        assert sig.last_modified == now

    def test_symbol_signature_is_mutable(self) -> None:
        now = datetime.now(tz=UTC)
        sig = SymbolSignature(
            qualified_name="a",
            name="a",
            kind="function",
            language="python",
            file_path="a.py",
            start_line=1,
            end_line=2,
            signature="def a():",
            docstring=None,
            parent_symbol=None,
            embedding_text="def a():",
            token_count_estimate=10,
            last_modified=now,
        )
        sig.docstring = "Updated."
        assert sig.docstring == "Updated."


@pytest.mark.unit
class TestSymbolRelationship:
    def test_relationship_creation(self) -> None:
        rel = SymbolRelationship(source="a.foo", target="b.bar", kind="calls")
        assert rel.source == "a.foo"
        assert rel.target == "b.bar"
        assert rel.kind == "calls"

    def test_relationship_is_frozen(self) -> None:
        rel = SymbolRelationship(source="a", target="b", kind="imports")
        with pytest.raises(AttributeError):
            rel.source = "c"  # type: ignore[misc]


@pytest.mark.unit
class TestQueryIntent:
    def test_intent_values(self) -> None:
        assert QueryIntent.UNDERSTAND.value == "understand"
        assert QueryIntent.MODIFY.value == "modify"
        assert QueryIntent.NAVIGATE.value == "navigate"
        assert QueryIntent.GENERATE.value == "generate"

    def test_intent_is_string(self) -> None:
        assert isinstance(QueryIntent.UNDERSTAND, str)


@pytest.mark.unit
class TestIndexStats:
    def test_index_stats_creation(self) -> None:
        stats = IndexStats(
            files_indexed=100,
            symbols_indexed=500,
            duration_ms=1234.5,
            languages={"python": 80, "typescript": 20},
        )
        assert stats.files_indexed == 100
        assert stats.languages["python"] == 80
