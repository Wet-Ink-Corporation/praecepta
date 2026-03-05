"""Full query execution pipeline for code context assembly."""

from __future__ import annotations

import fnmatch
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from praecepta.infra.codeintel.assembly.hydration import hydrate_chunk, hydrate_chunks
from praecepta.infra.codeintel.assembly.packing import pack_to_budget
from praecepta.infra.codeintel.assembly.ranking import fuse_rankings
from praecepta.infra.codeintel.assembly.schemas import (
    CodeChunk,
    ContextQuery,
    ContextResponse,
    RepoSummary,
    SourceLocation,
)
from praecepta.infra.codeintel.types import IndexStats, SymbolSignature, Tag

if TYPE_CHECKING:
    from praecepta.infra.codeintel.protocols import (
        CSTParser,
        SemanticExtractor,
        SemanticIndex,
        StructuralIndex,
    )


def _is_test_file(fp: Path) -> bool:
    """Return True when *fp* looks like a test file."""
    parts = fp.parts
    if any(p in ("tests", "test", "__tests__", "spec") for p in parts):
        return True
    name = fp.name
    return (
        name.startswith("test_")
        or name.endswith(("_test.py", ".spec.ts", ".spec.js", ".test.ts", ".test.js"))
    )


class DefaultContextAssembler:
    """ContextAssembler implementation orchestrating the full pipeline.

    Accepts all dependencies via constructor for testability.
    """

    def __init__(
        self,
        structural_index: StructuralIndex,
        semantic_index: SemanticIndex,
        parser: CSTParser,
        extractor: SemanticExtractor,
        repo_root: Path,
    ) -> None:
        self._structural = structural_index
        self._semantic = semantic_index
        self._parser = parser
        self._extractor = extractor
        self._repo_root = repo_root

    async def query(self, query: ContextQuery) -> ContextResponse:
        """Execute the full query pipeline."""
        query.validate()

        # Step 2: Parallel retrieval
        semantic_results: list[tuple[str, float]] = []
        structural_results: list[tuple[str, float]] = []

        if query.natural_language:
            semantic_results = await self._semantic.search(
                query.natural_language,
                top_k=query.max_chunks,
                filters=self._build_filters(query),
            )
            structural_results = self._structural.get_ranked_symbols(
                top_k=query.max_chunks,
            )

        # Step 3: Direct results (highest priority)
        direct_chunks: list[CodeChunk] = []
        seen_names: set[str] = set()
        for name in query.symbol_names:
            chunk = await self.get_symbol(name)
            if chunk and chunk.qualified_name not in seen_names:
                direct_chunks.append(chunk)
                seen_names.add(chunk.qualified_name)

        # File-path based direct results
        for file_path in query.file_paths:
            file_chunk = self._file_path_to_chunk(file_path)
            if file_chunk and file_chunk.qualified_name not in seen_names:
                direct_chunks.append(file_chunk)
                seen_names.add(file_chunk.qualified_name)

        # Step 4: Ranking fusion
        fused = fuse_rankings(
            structural_results,
            semantic_results,
            query.intent,
            structural_weight=query.structural_weight,
            semantic_weight=query.semantic_weight,
        )

        # Build CodeChunks from fused results, deduplicating against direct results
        fused_chunks = await self._build_chunks_from_ranked(fused, seen_names)
        chunks = direct_chunks + fused_chunks

        # Step 5: Dependency expansion
        if query.include_dependencies and chunks:
            chunks = self._expand_dependencies(chunks, query.dependency_depth)

        # Step 6: Disk hydration
        chunks = hydrate_chunks(chunks, self._repo_root, query.include_source_code)

        # Step 7: Token budget packing
        selected, tokens_used, remaining = pack_to_budget(chunks, query.token_budget)

        return ContextResponse(
            chunks=selected,
            total_tokens_used=tokens_used,
            token_budget=query.token_budget,
            chunks_available=remaining,
            intent_detected=query.intent,
        )

    async def get_symbol(self, qualified_name: str) -> CodeChunk | None:
        """Return a single CodeChunk by qualified name.

        Looks up the full symbol record from the semantic index so that the
        returned chunk carries accurate kind, language, and source location.
        """
        # First try exact qualified-name lookup
        record = await self._semantic.get_symbol_record(qualified_name)
        if record is None:
            # Fall back: search by short name then re-resolve
            short_name = qualified_name.rsplit(".", maxsplit=1)[-1]
            results = await self._semantic.search_by_name(short_name)
            if not results:
                return None
            matched = qualified_name if qualified_name in results else results[0]
            record = await self._semantic.get_symbol_record(matched)
            if record is None:
                return None

        chunk = self._symbol_record_to_chunk(record, relevance_score=1.0, retrieval_source="direct")
        return hydrate_chunk(chunk, self._repo_root)

    async def get_dependencies(
        self,
        qualified_name: str,
        depth: int = 1,
        direction: Literal["callers", "callees", "both"] = "both",
    ) -> list[CodeChunk]:
        """Return dependency subgraph as CodeChunk list."""
        deps = self._structural.get_dependencies(qualified_name, direction, depth)
        seen: set[str] = {qualified_name}
        chunks: list[CodeChunk] = []

        for source, target in deps:
            for name in (source, target):
                if name not in seen:
                    seen.add(name)
                    chunk = self._symbol_name_to_chunk(
                        name,
                        relevance_score=0.5,
                        retrieval_source="dependency",
                    )
                    if chunk is not None:
                        chunks.append(chunk)

        return hydrate_chunks(chunks, self._repo_root)

    async def get_repo_summary(self) -> RepoSummary:
        """Delegate to structural index."""
        return self._structural.get_repo_summary()

    async def refresh_index(
        self,
        file_paths: list[Path] | None = None,
        include_tests: bool = False,
    ) -> IndexStats:
        """Re-index specified files or all files."""
        start = time.monotonic()

        if file_paths is None:
            file_paths = self._discover_files(include_tests=include_tests)

        all_tags: dict[Path, list[Tag]] = {}
        all_symbols: list[SymbolSignature] = []
        languages: dict[str, int] = {}

        for fp in file_paths:
            try:
                result = self._parser.parse_file(fp)
            except Exception:
                continue

            all_tags[fp] = result.tags
            lang = result.language
            languages[lang] = languages.get(lang, 0) + 1

            if result.tree is not None:
                symbols = self._extractor.extract_symbols(fp, result.tags, result.tree)
                all_symbols.extend(symbols)

        # Update structural index
        self._structural.build(all_tags)
        # Update semantic index
        symbols_count = await self._semantic.upsert_symbols(all_symbols)
        duration = (time.monotonic() - start) * 1000

        return IndexStats(
            files_indexed=len(file_paths),
            symbols_indexed=symbols_count,
            duration_ms=duration,
            languages=languages,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_filters(self, query: ContextQuery) -> dict[str, str] | None:
        """Build metadata filters from query (language + symbol_kinds)."""
        filters: dict[str, str] = {}
        if query.languages:
            filters["language"] = query.languages[0]
        if query.symbol_kinds:
            filters["kind"] = query.symbol_kinds[0]
        return filters or None

    async def _build_chunks_from_ranked(
        self,
        ranked: list[tuple[str, float]],
        seen: set[str],
    ) -> list[CodeChunk]:
        """Convert (name, score) pairs to CodeChunks, skipping already-seen names.

        Tries to look up the full symbol record for each name so the chunk
        carries accurate metadata; falls back to a hollow stub for file-path
        entries (structural results).
        """
        chunks: list[CodeChunk] = []
        for name, score in ranked:
            if name in seen:
                continue
            seen.add(name)

            resolved: CodeChunk | None = None

            # Try semantic lookup for symbol-level entries
            record = await self._semantic.get_symbol_record(name)
            if record is not None:
                resolved = self._symbol_record_to_chunk(
                    record,
                    relevance_score=score,
                    retrieval_source="search",
                )
            else:
                # Structural result is a file path — use file-path chunk
                file_chunk = self._file_path_to_chunk(name)
                if file_chunk is not None:
                    file_chunk.relevance_score = score
                    resolved = file_chunk
                else:
                    resolved = self._symbol_name_to_chunk(
                        name, relevance_score=score, retrieval_source="search"
                    )

            if resolved is not None:
                chunks.append(resolved)
        return chunks

    def _symbol_record_to_chunk(
        self,
        record: SymbolSignature,
        relevance_score: float,
        retrieval_source: str,
    ) -> CodeChunk:
        """Build a populated CodeChunk from a full SymbolSignature record."""
        # Compute a repo-relative path if possible
        fp = Path(record.file_path)
        try:
            rel = str(fp.relative_to(self._repo_root))
        except ValueError:
            rel = record.file_path

        return CodeChunk(
            qualified_name=record.qualified_name,
            name=record.name,
            kind=record.kind,
            language=record.language,
            location=SourceLocation(
                file_path=rel,
                start_line=record.start_line,
                end_line=record.end_line,
            ),
            signature=record.signature,
            docstring=record.docstring,
            source_code=None,  # populated by hydration
            context_snippet=None,
            relevance_score=relevance_score,
            structural_rank=0.0,
            semantic_similarity=0.0,
            retrieval_source=retrieval_source,
            calls=[],
            called_by=[],
            imports=[],
            imported_by=[],
            token_count=record.token_count_estimate,
        )

    def _symbol_name_to_chunk(
        self,
        name: str,
        relevance_score: float,
        retrieval_source: str,
    ) -> CodeChunk | None:
        """Create a hollow CodeChunk stub from a symbol/file-path name.

        Used as a last-resort fallback when no record is found in the index.
        Source code is NOT populated here — that's done by hydration.
        """
        return CodeChunk(
            qualified_name=name,
            name=name.rsplit(".", maxsplit=1)[-1] if "." in name else name,
            kind="unknown",
            language="unknown",
            location=SourceLocation(file_path=name, start_line=0, end_line=0),
            signature=name,
            docstring=None,
            source_code=None,
            context_snippet=None,
            relevance_score=relevance_score,
            structural_rank=0.0,
            semantic_similarity=0.0,
            retrieval_source=retrieval_source,
            calls=[],
            called_by=[],
            imports=[],
            imported_by=[],
            token_count=10,
        )

    def _file_path_to_chunk(self, file_path: str) -> CodeChunk | None:
        """Create a CodeChunk for a file path with accurate line count (fixes B-3)."""
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = self._repo_root / file_path

        if not full_path.exists():
            return None

        try:
            line_count = sum(1 for _ in full_path.open(encoding="utf-8", errors="replace"))
        except OSError:
            line_count = 0

        try:
            rel = str(full_path.relative_to(self._repo_root))
        except ValueError:
            rel = file_path

        return CodeChunk(
            qualified_name=rel,
            name=full_path.name,
            kind="file",
            language="unknown",
            location=SourceLocation(
                file_path=rel,
                start_line=1,
                end_line=line_count,
            ),
            signature=rel,
            docstring=None,
            source_code=None,
            context_snippet=None,
            relevance_score=1.0,
            structural_rank=0.0,
            semantic_similarity=0.0,
            retrieval_source="direct",
            calls=[],
            called_by=[],
            imports=[],
            imported_by=[],
            token_count=max(line_count * 8, 10),  # rough estimate
        )

    def _expand_dependencies(
        self,
        chunks: list[CodeChunk],
        depth: int,
    ) -> list[CodeChunk]:
        """Add dependency symbols to chunk list."""
        seen = {c.qualified_name for c in chunks}
        expanded = list(chunks)

        for chunk in chunks:
            deps = self._structural.get_dependencies(chunk.qualified_name, "both", depth)
            for source, target in deps:
                for name in (source, target):
                    if name not in seen:
                        seen.add(name)
                        dep_chunk = self._symbol_name_to_chunk(
                            name,
                            relevance_score=chunk.relevance_score * 0.5,
                            retrieval_source="dependency",
                        )
                        if dep_chunk is not None:
                            expanded.append(dep_chunk)

        return expanded

    def _discover_files(self, include_tests: bool = False) -> list[Path]:
        """Walk repo_root and return supported source files.

        Applies exclude_patterns from settings (S-3) and respects the
        include_tests flag (S-2).  exclude_paths from a ContextQuery are
        not relevant here — they're applied at query time via _build_filters.
        """
        from praecepta.infra.codeintel.parser.language_registry import LANGUAGE_EXTENSIONS
        from praecepta.infra.codeintel.settings import get_settings

        settings = get_settings()
        supported_exts = set(LANGUAGE_EXTENSIONS.keys())
        exclude_patterns = settings.exclude_patterns
        files: list[Path] = []

        for fp in self._repo_root.rglob("*"):
            if not fp.is_file():
                continue
            if fp.suffix not in supported_exts:
                continue
            fp_str = str(fp)
            if any(fnmatch.fnmatch(fp_str, pat) for pat in exclude_patterns):
                continue
            if not include_tests and _is_test_file(fp):
                continue
            files.append(fp)

        return files
