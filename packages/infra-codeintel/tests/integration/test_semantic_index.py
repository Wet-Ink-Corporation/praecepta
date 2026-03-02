"""Integration tests for semantic index with real LanceDB."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from praecepta.infra.codeintel.index.semantic_index import LanceDBSemanticIndex
from praecepta.infra.codeintel.types import SymbolSignature


def _make_symbol(name: str, embedding_text: str) -> SymbolSignature:
    return SymbolSignature(
        qualified_name=f"module.{name}",
        name=name,
        kind="function",
        language="python",
        file_path="module.py",
        start_line=1,
        end_line=10,
        signature=f"def {name}():",
        docstring=f"The {name} function.",
        parent_symbol=None,
        embedding_text=embedding_text,
        token_count_estimate=20,
        last_modified=datetime.now(tz=UTC),
    )


def _make_mock_encoder() -> MagicMock:
    """Create a mock encoder that returns deterministic vectors."""
    mock = MagicMock()
    call_count = [0]

    def encode_side_effect(texts: list[str], **kwargs: object) -> list[list[float]]:
        result = []
        for i, _ in enumerate(texts):
            call_count[0] += 1
            # Create slightly different vectors for each text
            vec = [float(call_count[0] + i) / 1024.0] * 1024
            result.append(vec)
        return result

    mock.encode.side_effect = encode_side_effect
    return mock


@pytest.mark.integration
class TestLanceDBIntegration:
    @pytest.mark.asyncio
    async def test_upsert_and_search(self, tmp_path: Path) -> None:
        mock_encoder = _make_mock_encoder()
        idx = LanceDBSemanticIndex(db_path=tmp_path / "lance.db", encoder=mock_encoder)
        symbols = [_make_symbol("foo", "def foo(): pass"), _make_symbol("bar", "def bar(): pass")]
        count = await idx.upsert_symbols(symbols)
        assert count == 2

        results = await idx.search("find foo", top_k=5)
        assert len(results) > 0
        names = [name for name, _ in results]
        assert any("foo" in n or "bar" in n for n in names)

    @pytest.mark.asyncio
    async def test_remove_symbol(self, tmp_path: Path) -> None:
        mock_encoder = _make_mock_encoder()
        idx = LanceDBSemanticIndex(db_path=tmp_path / "lance.db", encoder=mock_encoder)
        await idx.upsert_symbols([_make_symbol("foo", "def foo():")])
        removed = await idx.remove_symbols(["module.foo"])
        assert removed == 1

    @pytest.mark.asyncio
    async def test_search_by_name(self, tmp_path: Path) -> None:
        mock_encoder = _make_mock_encoder()
        idx = LanceDBSemanticIndex(db_path=tmp_path / "lance.db", encoder=mock_encoder)
        await idx.upsert_symbols(
            [_make_symbol("foo", "def foo():"), _make_symbol("bar", "def bar():")]
        )
        results = await idx.search_by_name("foo")
        assert "module.foo" in results

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, tmp_path: Path) -> None:
        mock_encoder = _make_mock_encoder()
        idx = LanceDBSemanticIndex(db_path=tmp_path / "lance.db", encoder=mock_encoder)
        await idx.upsert_symbols([_make_symbol("foo", "def foo(): v1")])
        await idx.upsert_symbols([_make_symbol("foo", "def foo(): v2")])
        # Should still have exactly 1 foo
        results = await idx.search_by_name("foo")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_metadata_filter(self, tmp_path: Path) -> None:
        mock_encoder = _make_mock_encoder()
        idx = LanceDBSemanticIndex(db_path=tmp_path / "lance.db", encoder=mock_encoder)
        await idx.upsert_symbols([_make_symbol("foo", "def foo():")])
        results = await idx.search("foo", filters={"language": "typescript"})
        assert len(results) == 0  # filtered out
