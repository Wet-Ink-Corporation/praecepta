"""Unit tests for parse cache behavior."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from praecepta.infra.codeintel.parser.cst_parser import TreeSitterCSTParser

SIMPLE_PYTHON = "def hello() -> None:\n    pass\n"


@pytest.mark.unit
class TestParseCache:
    def test_cache_hit_returns_stored_tags(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text(SIMPLE_PYTHON)
        parser = TreeSitterCSTParser(cache_dir=tmp_path / "cache")

        # First parse - miss
        result1 = parser.parse_file(f)
        assert result1.tree is not None

        # Second parse - hit (tree will be None from cache)
        result2 = parser.parse_file(f)
        assert result2.tree is None  # from cache
        assert len(result2.tags) == len(result1.tags)

    def test_mtime_change_causes_cache_miss(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text(SIMPLE_PYTHON)
        parser = TreeSitterCSTParser(cache_dir=tmp_path / "cache")

        parser.parse_file(f)

        # Change file content + mtime
        time.sleep(0.05)  # ensure mtime changes
        f.write_text("def goodbye() -> None:\n    pass\n")

        result2 = parser.parse_file(f)
        assert result2.tree is not None  # cache miss, real parse
        names = [t.name for t in result2.tags if t.kind == "definition"]
        assert "goodbye" in names

    def test_extract_tags_uses_cache(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text(SIMPLE_PYTHON)
        parser = TreeSitterCSTParser(cache_dir=tmp_path / "cache")

        tags1 = parser.extract_tags(f)
        tags2 = parser.extract_tags(f)  # should hit cache
        assert len(tags1) == len(tags2)

    def test_cache_dir_uses_versioned_name(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text(SIMPLE_PYTHON)
        cache_base = tmp_path / "cache"
        parser = TreeSitterCSTParser(cache_dir=cache_base)
        parser.parse_file(f)
        assert (cache_base / "tags.cache.v1").exists()
