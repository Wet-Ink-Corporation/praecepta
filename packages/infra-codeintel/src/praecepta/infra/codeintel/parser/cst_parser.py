"""Tree-sitter CST parser with incremental parsing and disk cache support."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import tree_sitter_language_pack as tslp
from tree_sitter import Tree

try:
    import diskcache  # type: ignore[import-untyped]

    _DISKCACHE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DISKCACHE_AVAILABLE = False

from praecepta.infra.codeintel.exceptions import ParseError, UnsupportedLanguageError
from praecepta.infra.codeintel.parser.language_registry import (
    SUPPORTED_LANGUAGES,
    as_language_name,
    detect_language,
)
from praecepta.infra.codeintel.parser.tag_extractor import TagExtractor
from praecepta.infra.codeintel.types import ParseResult, Tag

_CACHE_VERSION = "tags.cache.v1"


class TreeSitterCSTParser:
    """CSTParser implementation using tree-sitter."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._tag_extractor = TagExtractor()
        self._cache: Any = None  # diskcache.Cache when available
        self._repo_root = repo_root
        if cache_dir is not None and _DISKCACHE_AVAILABLE:
            self._cache = diskcache.Cache(str(cache_dir / _CACHE_VERSION))

    @staticmethod
    def _cache_key(file_path: Path) -> str:
        """Return a cache key based on file path and mtime."""
        mtime = file_path.stat().st_mtime
        return f"{file_path}:{mtime}"

    def _rel_path(self, file_path: Path) -> str:
        """Compute a repo-relative path string for tag rel_fname.

        Falls back to the bare filename when repo_root is not set or
        the file is outside the repo root.
        """
        if self._repo_root is not None:
            try:
                return str(file_path.relative_to(self._repo_root))
            except ValueError:
                pass
        return file_path.name

    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a source file and extract tags."""
        language = detect_language(str(file_path))
        if language is None:
            raise UnsupportedLanguageError(language=file_path.suffix, file_path=str(file_path))

        # Check cache first
        if self._cache is not None:
            key = self._cache_key(file_path)
            cached_tags = self._cache.get(key)
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

        parser = tslp.get_parser(as_language_name(language))
        tree = parser.parse(source)
        duration_ms = (time.perf_counter() - start) * 1000

        rel_path = self._rel_path(file_path)
        tags = self._tag_extractor.extract_tags_from_tree(
            tree=tree,
            language=language,
            file_path=file_path,
            rel_path=rel_path,
        )

        # Store in cache
        if self._cache is not None:
            key = self._cache_key(file_path)
            self._cache.set(key, tags)

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
        parser = tslp.get_parser(as_language_name(language))

        # tree-sitter 0.25+ supports old_tree parameter for incremental parsing.
        # Cast old_tree to Tree | None to satisfy the typed API; fall back to full
        # parse if the cast is wrong at runtime.
        tree_ref: Tree | None = old_tree if isinstance(old_tree, Tree) else None
        try:
            tree = parser.parse(source, old_tree=tree_ref)
        except TypeError:
            tree = parser.parse(source)
        duration_ms = (time.perf_counter() - start) * 1000

        rel_path = self._rel_path(file_path)
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
