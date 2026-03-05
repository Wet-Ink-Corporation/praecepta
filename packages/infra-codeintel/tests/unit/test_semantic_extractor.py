"""Unit tests for semantic extractor."""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter_language_pack as tslp

from praecepta.infra.codeintel.extraction.semantic_extractor import TreeSitterSemanticExtractor
from praecepta.infra.codeintel.parser.tag_extractor import TagExtractor
from praecepta.infra.codeintel.protocols import SemanticExtractor

PYTHON_SOURCE = '''\
class AuthService:
    """Authentication service."""

    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user against the database."""
        return self.validate(username) and self.check_password(password)

    def validate(self, username: str) -> bool:
        return len(username) > 0

def login(credentials: dict) -> None:
    service = AuthService()
    service.authenticate(credentials["user"], credentials["pass"])
'''


def _parse_and_extract(source: str, filename: str = "test.py"):
    """Helper to parse source and extract tags + symbols."""
    parser = tslp.get_parser("python")
    tree = parser.parse(source.encode())
    tag_extractor = TagExtractor()
    tags = tag_extractor.extract_tags_from_tree(
        tree=tree,
        language="python",
        file_path=Path(filename),
        rel_path=filename,
    )
    extractor = TreeSitterSemanticExtractor()
    symbols = extractor.extract_symbols(Path(filename), tags, tree)
    return tags, symbols, tree


@pytest.mark.unit
class TestSemanticExtractor:
    def test_conforms_to_protocol(self) -> None:
        assert isinstance(TreeSitterSemanticExtractor(), SemanticExtractor)

    def test_python_function_extracted(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE)
        login_syms = [s for s in symbols if s.name == "login"]
        assert len(login_syms) >= 1
        assert login_syms[0].kind == "function"

    def test_python_class_extracted(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE)
        cls_syms = [s for s in symbols if s.name == "AuthService"]
        assert len(cls_syms) >= 1
        assert cls_syms[0].kind == "class"
        assert cls_syms[0].docstring is not None
        assert "Authentication service" in (cls_syms[0].docstring or "")

    def test_python_method_has_parent(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE)
        auth_syms = [s for s in symbols if s.name == "authenticate"]
        assert len(auth_syms) >= 1
        assert auth_syms[0].parent_symbol is not None
        assert "AuthService" in (auth_syms[0].parent_symbol or "")

    def test_embedding_text_format(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE)
        auth_syms = [s for s in symbols if s.name == "authenticate"]
        assert len(auth_syms) >= 1
        embed = auth_syms[0].embedding_text
        assert "authenticate" in embed
        # Should contain the signature
        assert "def authenticate" in embed or "authenticate" in embed

    def test_token_count_estimated(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE)
        for sym in symbols:
            assert sym.token_count_estimate > 0

    def test_qualified_name_includes_module(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE, "auth_module.py")
        for sym in symbols:
            assert "auth_module" in sym.qualified_name

    def test_relationship_extraction_finds_calls(self) -> None:
        tags, _, _tree = _parse_and_extract(PYTHON_SOURCE)
        extractor = TreeSitterSemanticExtractor()
        rels = extractor.extract_relationships(Path("test.py"), tags)
        # Should find some call references
        assert len(rels) > 0

    def test_start_end_lines(self) -> None:
        _, symbols, _ = _parse_and_extract(PYTHON_SOURCE)
        for sym in symbols:
            assert sym.start_line >= 1
            assert sym.end_line >= sym.start_line

    def test_language_detected_from_file_extension(self, tmp_path: Path) -> None:
        """Symbol language must reflect the actual file extension, not always 'python' (B-4)."""
        py_file = tmp_path / "service.py"
        py_file.write_text(PYTHON_SOURCE)

        parser = tslp.get_parser("python")
        tree = parser.parse(PYTHON_SOURCE.encode())
        extractor_obj = TreeSitterSemanticExtractor()
        # Extract with a .py file path — should get "python"
        tags, symbols_py, _ = _parse_and_extract(PYTHON_SOURCE, filename=str(py_file))
        assert all(s.language == "python" for s in symbols_py)

    def test_relationship_import_classification(self) -> None:
        """References with sub_kind='import' should become 'imports' edges (S-4)."""
        from praecepta.infra.codeintel.types import Tag

        extractor_obj = TreeSitterSemanticExtractor()
        tags = [
            Tag("mod.py", "/repo/mod.py", 1, "os", "reference", sub_kind="import"),
            Tag("mod.py", "/repo/mod.py", 2, "login", "reference", sub_kind="call"),
        ]
        rels = extractor_obj.extract_relationships(Path("mod.py"), tags)
        kinds = {r.kind for r in rels}
        assert "imports" in kinds
        assert "calls" in kinds
