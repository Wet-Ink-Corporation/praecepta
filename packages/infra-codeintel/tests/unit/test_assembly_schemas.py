"""Unit tests for assembly schemas."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.assembly.schemas import (
    CodeChunk,
    ContextQuery,
    ContextResponse,
    SourceLocation,
)
from praecepta.infra.codeintel.exceptions import CodeIntelError
from praecepta.infra.codeintel.types import QueryIntent


@pytest.mark.unit
class TestContextQueryValidation:
    def test_valid_with_natural_language(self) -> None:
        q = ContextQuery(natural_language="find auth functions")
        q.validate()

    def test_valid_with_symbol_names(self) -> None:
        q = ContextQuery(symbol_names=["auth.login"])
        q.validate()

    def test_valid_with_file_paths(self) -> None:
        q = ContextQuery(file_paths=["src/auth.py"])
        q.validate()

    def test_invalid_empty_query(self) -> None:
        q = ContextQuery()
        with pytest.raises(CodeIntelError, match="at least one"):
            q.validate()

    def test_default_intent(self) -> None:
        q = ContextQuery(natural_language="test")
        assert q.intent == QueryIntent.UNDERSTAND

    def test_default_token_budget(self) -> None:
        q = ContextQuery(natural_language="test")
        assert q.token_budget == 4096


@pytest.mark.unit
class TestContextResponseRendering:
    def test_as_context_string_with_chunks(self) -> None:
        chunk = CodeChunk(
            qualified_name="auth.login",
            name="login",
            kind="function",
            language="python",
            location=SourceLocation(file_path="src/auth.py", start_line=10, end_line=25),
            signature="def login(username: str, password: str) -> bool:",
            docstring="Authenticate a user.",
            source_code="def login(username: str, password: str) -> bool:\n    ...",
            context_snippet=None,
            relevance_score=0.95,
            structural_rank=0.8,
            semantic_similarity=0.9,
            retrieval_source="both",
            calls=["validate_password"],
            called_by=["login_handler"],
            imports=[],
            imported_by=[],
            token_count=50,
        )
        response = ContextResponse(
            chunks=[chunk],
            total_tokens_used=50,
            token_budget=4096,
            chunks_available=0,
        )
        xml = response.as_context_string
        assert "<code_context" in xml
        assert 'tokens_used="50"' in xml
        assert 'budget="4096"' in xml
        assert 'chunks="1"' in xml
        assert "<chunk" in xml
        assert 'symbol="login"' in xml
        assert "</code_context>" in xml

    def test_as_context_string_empty(self) -> None:
        response = ContextResponse(
            chunks=[],
            total_tokens_used=0,
            token_budget=4096,
            chunks_available=0,
        )
        xml = response.as_context_string
        assert 'chunks="0"' in xml

    def test_as_context_string_signature_only(self) -> None:
        chunk = CodeChunk(
            qualified_name="a.b",
            name="b",
            kind="function",
            language="python",
            location=SourceLocation(file_path="a.py", start_line=1, end_line=5),
            signature="def b() -> None:",
            docstring=None,
            source_code=None,
            context_snippet=None,
            relevance_score=0.5,
            structural_rank=0.3,
            semantic_similarity=0.4,
            retrieval_source="structural",
            calls=[],
            called_by=[],
            imports=[],
            imported_by=[],
            token_count=10,
        )
        response = ContextResponse(
            chunks=[chunk],
            total_tokens_used=10,
            token_budget=4096,
            chunks_available=5,
        )
        xml = response.as_context_string
        assert 'more_available="5"' in xml


@pytest.mark.unit
class TestCodeChunkSerialization:
    def test_to_dict_round_trip(self) -> None:
        chunk = CodeChunk(
            qualified_name="main.foo",
            name="foo",
            kind="function",
            language="python",
            location=SourceLocation(file_path="main.py", start_line=1, end_line=10),
            signature="def foo():",
            docstring=None,
            source_code="def foo():\n    pass",
            context_snippet=None,
            relevance_score=0.9,
            structural_rank=0.5,
            semantic_similarity=0.8,
            retrieval_source="semantic",
            calls=[],
            called_by=[],
            imports=[],
            imported_by=[],
            token_count=20,
        )
        d = chunk.to_dict()
        assert d["qualified_name"] == "main.foo"
        assert d["location"]["file_path"] == "main.py"
        assert d["token_count"] == 20
