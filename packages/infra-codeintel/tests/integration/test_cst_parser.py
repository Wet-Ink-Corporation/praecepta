"""Integration tests for CST parser with real tree-sitter parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from praecepta.infra.codeintel.parser.cst_parser import TreeSitterCSTParser

PYTHON_SOURCE = """\
def greet(name: str) -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello, {name}!"

class Greeter:
    def say_hi(self) -> None:
        greet("world")
"""


@pytest.mark.integration
class TestCSTParserIntegration:
    def test_parse_python_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text(PYTHON_SOURCE)
        parser = TreeSitterCSTParser()
        result = parser.parse_file(f)
        assert result.language == "python"
        assert result.tree is not None
        assert len(result.tags) > 0
        assert result.parse_duration_ms >= 0

    def test_extract_tags(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text(PYTHON_SOURCE)
        parser = TreeSitterCSTParser()
        tags = parser.extract_tags(f)
        names = [t.name for t in tags if t.kind == "definition"]
        assert "greet" in names
        assert "Greeter" in names

    def test_incremental_parse_same_result(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text(PYTHON_SOURCE)
        parser = TreeSitterCSTParser()
        result1 = parser.parse_file(f)
        result2 = parser.parse_file_incremental(f, result1.tree)
        assert len(result2.tags) == len(result1.tags)

    def test_incremental_parse_detects_changes(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text(PYTHON_SOURCE)
        parser = TreeSitterCSTParser()
        result1 = parser.parse_file(f)

        f.write_text(PYTHON_SOURCE + "\ndef extra() -> None:\n    pass\n")
        result2 = parser.parse_file_incremental(f, result1.tree)
        names2 = [t.name for t in result2.tags if t.kind == "definition"]
        assert "extra" in names2
