"""Unit tests for CST parser."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from praecepta.infra.codeintel.exceptions import UnsupportedLanguageError
from praecepta.infra.codeintel.parser.cst_parser import TreeSitterCSTParser
from praecepta.infra.codeintel.protocols import CSTParser


@pytest.mark.unit
class TestTreeSitterCSTParser:
    def test_conforms_to_protocol(self) -> None:
        assert isinstance(TreeSitterCSTParser(), CSTParser)

    def test_get_supported_languages(self) -> None:
        parser = TreeSitterCSTParser()
        langs = parser.get_supported_languages()
        assert "python" in langs
        assert "typescript" in langs
        assert "javascript" in langs

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        parser = TreeSitterCSTParser()
        f = tmp_path / "main.rs"
        f.write_text("fn main() {}")
        with pytest.raises(UnsupportedLanguageError):
            parser.parse_file(f)

    def test_repo_relative_path_in_tags(self, tmp_path: Path) -> None:
        """When repo_root is set, tag.rel_fname should be repo-relative (M-3)."""
        sub = tmp_path / "src" / "auth"
        sub.mkdir(parents=True)
        py_file = sub / "service.py"
        py_file.write_text("def login(): pass\n")

        parser = TreeSitterCSTParser(repo_root=tmp_path)
        result = parser.parse_file(py_file)

        for tag in result.tags:
            # rel_fname must be "src/auth/service.py" or equivalent, NOT "service.py"
            assert "service.py" in tag.rel_fname
            assert tag.rel_fname != "service.py"

    def test_fallback_to_filename_without_repo_root(self, tmp_path: Path) -> None:
        """Without repo_root, rel_fname should be the bare filename."""
        py_file = tmp_path / "module.py"
        py_file.write_text("class Foo: pass\n")

        parser = TreeSitterCSTParser()  # no repo_root
        result = parser.parse_file(py_file)

        for tag in result.tags:
            assert tag.rel_fname == "module.py"
