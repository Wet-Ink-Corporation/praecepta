"""Integration tests — parse real files and verify tag extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
import tree_sitter_language_pack as tslp

from praecepta.infra.codeintel.parser.tag_extractor import TagExtractor

PYTHON_CODE = """\
class Foo:
    def bar(self) -> None:
        self.baz()

    def baz(self) -> None:
        pass

def standalone() -> None:
    Foo().bar()
"""


@pytest.mark.integration
class TestTagExtractorIntegration:
    def test_python_definitions_extracted(self, tmp_path: Path) -> None:
        extractor = TagExtractor()
        parser = tslp.get_parser("python")
        tree = parser.parse(PYTHON_CODE.encode())

        tags = extractor.extract_tags_from_tree(
            tree=tree,
            language="python",
            file_path=tmp_path / "test.py",
            rel_path="test.py",
        )

        def_names = [t.name for t in tags if t.kind == "definition"]
        assert "Foo" in def_names
        assert "standalone" in def_names

    def test_python_references_extracted(self, tmp_path: Path) -> None:
        extractor = TagExtractor()
        parser = tslp.get_parser("python")
        tree = parser.parse(PYTHON_CODE.encode())

        tags = extractor.extract_tags_from_tree(
            tree=tree,
            language="python",
            file_path=tmp_path / "test.py",
            rel_path="test.py",
        )

        ref_names = [t.name for t in tags if t.kind == "reference"]
        assert "baz" in ref_names or "bar" in ref_names

    def test_tag_line_numbers_correct(self, tmp_path: Path) -> None:
        extractor = TagExtractor()
        parser = tslp.get_parser("python")
        tree = parser.parse(PYTHON_CODE.encode())

        tags = extractor.extract_tags_from_tree(
            tree=tree,
            language="python",
            file_path=tmp_path / "test.py",
            rel_path="test.py",
        )

        foo_tags = [t for t in tags if t.name == "Foo" and t.kind == "definition"]
        assert len(foo_tags) >= 1
        assert foo_tags[0].line == 1  # Foo is on line 1

    def test_tag_fields_populated(self, tmp_path: Path) -> None:
        extractor = TagExtractor()
        parser = tslp.get_parser("python")
        tree = parser.parse(PYTHON_CODE.encode())

        tags = extractor.extract_tags_from_tree(
            tree=tree,
            language="python",
            file_path=tmp_path / "test.py",
            rel_path="test.py",
        )

        assert len(tags) > 0
        for tag in tags:
            assert tag.rel_fname == "test.py"
            assert tag.kind in ("definition", "reference")
            assert tag.line >= 1
            assert len(tag.name) > 0
