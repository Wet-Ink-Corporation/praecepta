"""Unit tests for tag extractor."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.exceptions import UnsupportedLanguageError
from praecepta.infra.codeintel.parser.tag_extractor import TagExtractor


@pytest.mark.unit
class TestTagExtractor:
    def test_unsupported_language_raises(self) -> None:
        extractor = TagExtractor()
        with pytest.raises(UnsupportedLanguageError):
            extractor._load_query("rust")

    def test_scm_loaded_via_importlib(self) -> None:
        extractor = TagExtractor()
        query_text = extractor._load_query("python")
        assert "(function_definition" in query_text

    def test_query_is_cached(self) -> None:
        extractor = TagExtractor()
        q1 = extractor._load_query("python")
        q2 = extractor._load_query("python")
        assert q1 is q2  # same string object from cache

    def test_supported_languages_all_loadable(self) -> None:
        extractor = TagExtractor()
        for lang in ["python", "typescript", "javascript"]:
            text = extractor._load_query(lang)
            assert len(text) > 0
