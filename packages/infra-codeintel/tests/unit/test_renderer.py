"""Unit tests for XML context renderer."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.assembly.renderer import render_context_xml
from praecepta.infra.codeintel.assembly.schemas import (
    CodeChunk,
    ContextResponse,
    SourceLocation,
)


def _make_chunk(
    name: str = "func",
    source_code: str | None = "def func(): pass",
    calls: list[str] | None = None,
    called_by: list[str] | None = None,
) -> CodeChunk:
    return CodeChunk(
        qualified_name=f"mod.{name}",
        name=name,
        kind="function",
        language="python",
        location=SourceLocation(file_path="src/mod.py", start_line=10, end_line=20),
        signature=f"def {name}():",
        docstring=None,
        source_code=source_code,
        context_snippet=None,
        relevance_score=0.95,
        structural_rank=0.8,
        semantic_similarity=0.9,
        retrieval_source="both",
        calls=calls or [],
        called_by=called_by or [],
        imports=[],
        imported_by=[],
        token_count=50,
    )


@pytest.mark.unit
class TestRenderContextXML:
    def test_root_element_attributes(self) -> None:
        resp = ContextResponse(
            chunks=[_make_chunk()],
            total_tokens_used=50,
            token_budget=4096,
            chunks_available=5,
        )
        xml = render_context_xml(resp)
        assert "<code_context" in xml
        assert 'tokens_used="50"' in xml
        assert 'budget="4096"' in xml
        assert 'chunks="1"' in xml
        assert 'more_available="5"' in xml
        assert "</code_context>" in xml

    def test_chunk_attributes(self) -> None:
        resp = ContextResponse(
            chunks=[_make_chunk(name="login")],
            total_tokens_used=50,
            token_budget=4096,
            chunks_available=0,
        )
        xml = render_context_xml(resp)
        assert 'rank="1"' in xml
        assert 'relevance="0.95"' in xml
        assert 'source="both"' in xml
        assert 'symbol="login"' in xml
        assert 'kind="function"' in xml
        assert 'location="src/mod.py:10-20"' in xml

    def test_relationship_comments(self) -> None:
        resp = ContextResponse(
            chunks=[_make_chunk(calls=["validate", "hash"], called_by=["handler"])],
            total_tokens_used=50,
            token_budget=4096,
            chunks_available=0,
        )
        xml = render_context_xml(resp)
        assert "# Calls: validate, hash" in xml
        assert "# Called by: handler" in xml

    def test_signature_only_chunk(self) -> None:
        resp = ContextResponse(
            chunks=[_make_chunk(source_code=None)],
            total_tokens_used=10,
            token_budget=4096,
            chunks_available=0,
        )
        xml = render_context_xml(resp)
        assert "def func():" in xml

    def test_empty_response(self) -> None:
        resp = ContextResponse(
            chunks=[],
            total_tokens_used=0,
            token_budget=4096,
            chunks_available=0,
        )
        xml = render_context_xml(resp)
        assert 'chunks="0"' in xml

    def test_multiple_chunks_ranked(self) -> None:
        resp = ContextResponse(
            chunks=[_make_chunk("a"), _make_chunk("b")],
            total_tokens_used=100,
            token_budget=4096,
            chunks_available=0,
        )
        xml = render_context_xml(resp)
        assert 'rank="1"' in xml
        assert 'rank="2"' in xml

    def test_as_context_string_property(self) -> None:
        """Verify the property on ContextResponse works."""
        resp = ContextResponse(
            chunks=[_make_chunk()],
            total_tokens_used=50,
            token_budget=4096,
            chunks_available=0,
        )
        xml = resp.as_context_string
        assert "<code_context" in xml
