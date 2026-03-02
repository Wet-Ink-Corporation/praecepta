"""Full query execution pipeline for code context assembly."""

from __future__ import annotations

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
        fused_chunks = self._build_chunks_from_ranked(fused, seen_names)
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
        """Return a single CodeChunk by qualified name."""
        results = await self._semantic.search_by_name(qualified_name)
        if not results:
            return None

        # Use exact match if available, otherwise first result
        matched_name = qualified_name if qualified_name in results else results[0]

        # Search by the matched name to get score
        # Build a chunk from the semantic index metadata
        chunk = self._symbol_name_to_chunk(
            matched_name,
            relevance_score=1.0,
            retrieval_source="direct",
        )
        if chunk is not None:
            chunk = hydrate_chunk(chunk, self._repo_root)
        return chunk

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

    async def refresh_index(self, file_paths: list[Path] | None = None) -> IndexStats:
        """Re-index specified files or all files."""
        start = time.monotonic()

        if file_paths is None:
            # Discover all supported files
            file_paths = self._discover_files()

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
        """Build metadata filters from query."""
        filters: dict[str, str] = {}
        if query.languages:
            filters["language"] = query.languages[0]
        return filters or None

    def _build_chunks_from_ranked(
        self,
        ranked: list[tuple[str, float]],
        seen: set[str],
    ) -> list[CodeChunk]:
        """Convert (name, score) pairs to CodeChunks, skipping already-seen names."""
        chunks: list[CodeChunk] = []
        for name, score in ranked:
            if name in seen:
                continue
            seen.add(name)
            chunk = self._symbol_name_to_chunk(
                name,
                relevance_score=score,
                retrieval_source="search",
            )
            if chunk is not None:
                chunks.append(chunk)
        return chunks

    def _symbol_name_to_chunk(
        self,
        name: str,
        relevance_score: float,
        retrieval_source: str,
    ) -> CodeChunk | None:
        """Create a CodeChunk stub from a symbol name.

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
        """Create a CodeChunk for a file path."""
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = self._repo_root / file_path

        if not full_path.exists():
            return None

        return CodeChunk(
            qualified_name=file_path,
            name=full_path.name,
            kind="file",
            language="unknown",
            location=SourceLocation(
                file_path=file_path,
                start_line=1,
                end_line=0,
            ),
            signature=file_path,
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
            token_count=10,
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

    def _discover_files(self) -> list[Path]:
        """Walk repo_root and find supported source files."""
        from praecepta.infra.codeintel.parser.language_registry import LANGUAGE_EXTENSIONS

        supported_exts = set(LANGUAGE_EXTENSIONS.keys())
        files: list[Path] = []
        for fp in self._repo_root.rglob("*"):
            if fp.is_file() and fp.suffix in supported_exts:
                files.append(fp)
        return files
