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
