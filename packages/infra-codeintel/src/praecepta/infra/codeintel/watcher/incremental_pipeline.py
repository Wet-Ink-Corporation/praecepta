"""Incremental update pipeline triggered by file watcher events."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from praecepta.infra.codeintel.types import FileEvent, Tag

logger = logging.getLogger(__name__)


def diff_tags(
    old_tags: list[Tag],
    new_tags: list[Tag],
) -> tuple[list[Tag], list[Tag], list[Tag]]:
    """Diff old and new tags to find added, removed, modified definitions.

    Only considers definition tags (not references).

    Returns:
        (added, removed, modified) -- each a list of Tags.
    """
    old_defs = {t.name: t for t in old_tags if t.kind == "definition"}
    new_defs = {t.name: t for t in new_tags if t.kind == "definition"}

    old_names = set(old_defs.keys())
    new_names = set(new_defs.keys())

    added = [new_defs[n] for n in new_names - old_names]
    removed = [old_defs[n] for n in old_names - new_names]
    modified = [
        new_defs[n]
        for n in old_names & new_names
        if old_defs[n].line != new_defs[n].line  # line change implies content change
    ]

    return added, removed, modified


class IncrementalUpdatePipeline:
    """Process file change events and update indexes incrementally."""

    def __init__(
        self,
        parser: Any,  # CSTParser
        extractor: Any,  # SemanticExtractor
        structural_index: Any,  # StructuralIndex
        semantic_index: Any,  # SemanticIndex
    ) -> None:
        self._parser = parser
        self._extractor = extractor
        self._structural = structural_index
        self._semantic = semantic_index
        self._tag_cache: dict[str, list[Tag]] = {}

    async def process_events(self, events: list[FileEvent]) -> None:
        """Process a batch of file change events."""
        for event in events:
            try:
                if event.event_type == "deleted":
                    await self._handle_deleted(event.path)
                elif event.event_type == "created":
                    await self._handle_created(event.path)
                else:
                    await self._handle_modified(event.path)
            except Exception:
                logger.warning(
                    "Failed to process %s event for %s",
                    event.event_type,
                    event.path,
                    exc_info=True,
                )

    async def _handle_deleted(self, file_path: Any) -> None:
        """Remove file from both indexes."""
        logger.info("Removing deleted file: %s", file_path)
        self._structural.remove_file(file_path)

        # Get cached tags to find symbols to remove
        old_tags = self._tag_cache.pop(str(file_path), [])
        names = [t.name for t in old_tags if t.kind == "definition"]
        if names:
            await self._semantic.remove_symbols(names)

    async def _handle_created(self, file_path: Any) -> None:
        """Parse new file and add to both indexes."""
        logger.info("Indexing new file: %s", file_path)
        result = self._parser.parse_file(file_path)

        self._tag_cache[str(file_path)] = result.tags
        self._structural.update_file(file_path, result.tags)

        symbols = self._extractor.extract_symbols(file_path, result.tags, result.tree)
        if symbols:
            await self._semantic.upsert_symbols(symbols)

    async def _handle_modified(self, file_path: Any) -> None:
        """Incremental parse, diff tags, update indexes."""
        logger.info("Updating modified file: %s", file_path)
        result = self._parser.parse_file(file_path)
        new_tags: list[Tag] = result.tags

        old_tags = self._tag_cache.get(str(file_path), [])
        added, removed, modified = diff_tags(old_tags, new_tags)

        self._tag_cache[str(file_path)] = new_tags

        # Update structural index (replace all edges for this file)
        self._structural.update_file(file_path, new_tags)

        # Remove deleted symbols from semantic index
        removed_names = [t.name for t in removed]
        if removed_names:
            await self._semantic.remove_symbols(removed_names)

        # Re-embed added and modified symbols
        changed_tags = added + modified
        if changed_tags:
            symbols = self._extractor.extract_symbols(
                file_path,
                changed_tags,
                result.tree,
            )
            if symbols:
                await self._semantic.upsert_symbols(symbols)
