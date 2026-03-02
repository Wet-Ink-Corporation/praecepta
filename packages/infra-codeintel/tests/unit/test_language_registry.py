"""Unit tests for language registry."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.parser.language_registry import (
    LANGUAGE_EXTENSIONS,
    SUPPORTED_LANGUAGES,
    detect_language,
)


@pytest.mark.unit
class TestDetectLanguage:
    def test_python_py(self) -> None:
        assert detect_language("src/main.py") == "python"

    def test_python_pyi(self) -> None:
        assert detect_language("src/types.pyi") == "python"

    def test_typescript_ts(self) -> None:
        assert detect_language("src/app.ts") == "typescript"

    def test_typescript_tsx(self) -> None:
        assert detect_language("src/App.tsx") == "typescript"

    def test_javascript_js(self) -> None:
        assert detect_language("src/index.js") == "javascript"

    def test_javascript_jsx(self) -> None:
        assert detect_language("src/App.jsx") == "javascript"

    def test_javascript_mjs(self) -> None:
        assert detect_language("lib/utils.mjs") == "javascript"

    def test_javascript_cjs(self) -> None:
        assert detect_language("lib/config.cjs") == "javascript"

    def test_unknown_extension(self) -> None:
        assert detect_language("readme.md") is None

    def test_no_extension(self) -> None:
        assert detect_language("Makefile") is None

    def test_case_insensitive(self) -> None:
        assert detect_language("Main.PY") == "python"


@pytest.mark.unit
class TestConstants:
    def test_supported_languages_is_frozenset(self) -> None:
        assert isinstance(SUPPORTED_LANGUAGES, frozenset)

    def test_supported_languages_derived_from_extensions(self) -> None:
        assert frozenset(LANGUAGE_EXTENSIONS.values()) == SUPPORTED_LANGUAGES

    def test_contains_python(self) -> None:
        assert "python" in SUPPORTED_LANGUAGES

    def test_contains_typescript(self) -> None:
        assert "typescript" in SUPPORTED_LANGUAGES

    def test_contains_javascript(self) -> None:
        assert "javascript" in SUPPORTED_LANGUAGES
