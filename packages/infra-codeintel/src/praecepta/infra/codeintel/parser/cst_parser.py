"""Tree-sitter CST parser with incremental parsing and disk cache support."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import tree_sitter_language_pack as tslp

if TYPE_CHECKING:
    from pathlib import Path

from praecepta.infra.codeintel.exceptions import ParseError, UnsupportedLanguageError
from praecepta.infra.codeintel.parser.language_registry import (
    SUPPORTED_LANGUAGES,
    detect_language,
)
from praecepta.infra.codeintel.parser.tag_extractor import TagExtractor
from praecepta.infra.codeintel.types import ParseResult, Tag

_CACHE_VERSION = "tags.cache.v1"


class TreeSitterCSTParser:
    """CSTParser implementation using tree-sitter."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._tag_extractor = TagExtractor()
        self._cache: object | None = None  # diskcache.Cache
        if cache_dir is not None:
            import diskcache

            self._cache = diskcache.Cache(str(cache_dir / _CACHE_VERSION))

    @staticmethod
    def _cache_key(file_path: Path) -> str:
        """Return a cache key based on file path and mtime."""
        mtime = file_path.stat().st_mtime
        return f"{file_path}:{mtime}"

    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a source file and extract tags."""
        language = detect_language(str(file_path))
        if language is None:
            raise UnsupportedLanguageError(language=file_path.suffix, file_path=str(file_path))

        # Check cache first
        if self._cache is not None:
            key = self._cache_key(file_path)
            cached_tags = self._cache.get(key)  # type: ignore[union-attr]
            if cached_tags is not None:
                return ParseResult(
                    tree=None,
                    tags=cached_tags,
                    language=language,
                    parse_duration_ms=0.0,
                )

        start = time.perf_counter()
        try:
            source = file_path.read_bytes()
        except OSError as e:
            raise ParseError(file_path=str(file_path), reason=str(e)) from e

        parser = tslp.get_parser(language)
        tree = parser.parse(source)
        duration_ms = (time.perf_counter() - start) * 1000

        rel_path = file_path.name
        tags = self._tag_extractor.extract_tags_from_tree(
            tree=tree,
            language=language,
            file_path=file_path,
            rel_path=rel_path,
        )

        # Store in cache
        if self._cache is not None:
            key = self._cache_key(file_path)
            self._cache.set(key, tags)  # type: ignore[union-attr]

        return ParseResult(
            tree=tree,
            tags=tags,
            language=language,
            parse_duration_ms=duration_ms,
        )

    def parse_file_incremental(self, file_path: Path, old_tree: object) -> ParseResult:
        """Incremental parse using old_tree reference. Does NOT use cache."""
        language = detect_language(str(file_path))
        if language is None:
            raise UnsupportedLanguageError(language=file_path.suffix, file_path=str(file_path))

        start = time.perf_counter()
        source = file_path.read_bytes()
        parser = tslp.get_parser(language)
        # tree-sitter 0.25+ supports old_tree parameter for incremental parsing.
        # If it fails, fall back to a full parse.
        try:
            tree = parser.parse(source, old_tree=old_tree)  # type: ignore[arg-type]
        except TypeError:
            tree = parser.parse(source)
        duration_ms = (time.perf_counter() - start) * 1000

        rel_path = file_path.name
        tags = self._tag_extractor.extract_tags_from_tree(
            tree=tree,
            language=language,
            file_path=file_path,
            rel_path=rel_path,
        )

        return ParseResult(
            tree=tree,
            tags=tags,
            language=language,
            parse_duration_ms=duration_ms,
        )

    def extract_tags(self, file_path: Path) -> list[Tag]:
        """Parse file and return only tags."""
        return self.parse_file(file_path).tags

    def get_supported_languages(self) -> list[str]:
        """Return list of supported language names."""
        return sorted(SUPPORTED_LANGUAGES)
