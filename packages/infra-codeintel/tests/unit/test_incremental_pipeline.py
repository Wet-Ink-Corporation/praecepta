"""Unit tests for incremental update pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from praecepta.infra.codeintel.types import FileEvent, Tag
from praecepta.infra.codeintel.watcher.incremental_pipeline import (
    IncrementalUpdatePipeline,
    diff_tags,
)


@pytest.mark.unit
class TestTagDiff:
    def test_added_symbols_detected(self) -> None:
        old = [Tag("a.py", "/a.py", 1, "foo", "definition")]
        new = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 5, "bar", "definition"),
        ]
        added, removed, _modified = diff_tags(old, new)
        assert "bar" in [t.name for t in added]
        assert len(removed) == 0

    def test_removed_symbols_detected(self) -> None:
        old = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 5, "bar", "definition"),
        ]
        new = [Tag("a.py", "/a.py", 1, "foo", "definition")]
        added, removed, _modified = diff_tags(old, new)
        assert "bar" in [t.name for t in removed]
        assert len(added) == 0

    def test_modified_symbols_detected(self) -> None:
        old = [Tag("a.py", "/a.py", 1, "foo", "definition")]
        new = [Tag("a.py", "/a.py", 5, "foo", "definition")]  # moved to line 5
        _added, _removed, modified = diff_tags(old, new)
        assert "foo" in [t.name for t in modified]

    def test_references_ignored(self) -> None:
        old = [Tag("a.py", "/a.py", 1, "foo", "reference")]
        new: list[Tag] = []
        _added, removed, _modified = diff_tags(old, new)
        # References don't count as symbol changes
        assert len(removed) == 0

    def test_empty_inputs(self) -> None:
        added, removed, modified = diff_tags([], [])
        assert added == []
        assert removed == []
        assert modified == []

    def test_empty_old_all_added(self) -> None:
        new = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 5, "bar", "definition"),
        ]
        added, removed, modified = diff_tags([], new)
        assert len(added) == 2
        assert len(removed) == 0
        assert len(modified) == 0

    def test_empty_new_all_removed(self) -> None:
        old = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 5, "bar", "definition"),
        ]
        added, removed, modified = diff_tags(old, [])
        assert len(removed) == 2
        assert len(added) == 0
        assert len(modified) == 0

    def test_same_line_no_modification(self) -> None:
        old = [Tag("a.py", "/a.py", 1, "foo", "definition")]
        new = [Tag("a.py", "/a.py", 1, "foo", "definition")]
        added, removed, modified = diff_tags(old, new)
        assert len(added) == 0
        assert len(removed) == 0
        assert len(modified) == 0

    def test_mixed_definitions_and_references(self) -> None:
        old = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 10, "foo", "reference"),
            Tag("a.py", "/a.py", 3, "bar", "reference"),
        ]
        new = [
            Tag("a.py", "/a.py", 5, "foo", "definition"),  # modified (line changed)
            Tag("a.py", "/a.py", 7, "baz", "definition"),  # added
        ]
        added, removed, modified = diff_tags(old, new)
        assert "baz" in [t.name for t in added]
        assert len(removed) == 0  # bar was reference, not counted
        assert "foo" in [t.name for t in modified]


@pytest.mark.unit
class TestIncrementalUpdatePipeline:
    @pytest.mark.asyncio
    async def test_on_modified_updates_indexes(self) -> None:
        mock_parser = MagicMock()
        mock_parser.parse_file.return_value = MagicMock(
            tags=[Tag("a.py", "/a.py", 1, "foo", "definition")],
            tree=MagicMock(),
        )
        mock_extractor = MagicMock()
        mock_extractor.extract_symbols.return_value = []
        mock_structural = MagicMock()
        mock_semantic = AsyncMock()

        pipeline = IncrementalUpdatePipeline(
            parser=mock_parser,
            extractor=mock_extractor,
            structural_index=mock_structural,
            semantic_index=mock_semantic,
        )

        events = [
            FileEvent(
                path=Path("/repo/a.py"),
                event_type="modified",
                timestamp=datetime.now(tz=UTC),
            )
        ]
        await pipeline.process_events(events)

        mock_parser.parse_file.assert_called_once()
        mock_structural.update_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_created_adds_to_indexes(self) -> None:
        mock_parser = MagicMock()
        tags = [Tag("a.py", "/a.py", 1, "foo", "definition")]
        mock_parser.parse_file.return_value = MagicMock(
            tags=tags,
            tree=MagicMock(),
        )
        mock_extractor = MagicMock()
        mock_extractor.extract_symbols.return_value = [MagicMock()]
        mock_structural = MagicMock()
        mock_semantic = AsyncMock()

        pipeline = IncrementalUpdatePipeline(
            parser=mock_parser,
            extractor=mock_extractor,
            structural_index=mock_structural,
            semantic_index=mock_semantic,
        )

        events = [
            FileEvent(
                path=Path("/repo/a.py"),
                event_type="created",
                timestamp=datetime.now(tz=UTC),
            )
        ]
        await pipeline.process_events(events)

        mock_parser.parse_file.assert_called_once()
        mock_structural.update_file.assert_called_once()
        mock_extractor.extract_symbols.assert_called_once()
        mock_semantic.upsert_symbols.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_deleted_removes_from_indexes(self) -> None:
        mock_structural = MagicMock()
        mock_semantic = AsyncMock()

        pipeline = IncrementalUpdatePipeline(
            parser=MagicMock(),
            extractor=MagicMock(),
            structural_index=mock_structural,
            semantic_index=mock_semantic,
        )

        # Pre-populate tag cache so delete knows what to remove
        pipeline._tag_cache[str(Path("/repo/a.py"))] = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
        ]

        events = [
            FileEvent(
                path=Path("/repo/a.py"),
                event_type="deleted",
                timestamp=datetime.now(tz=UTC),
            )
        ]
        await pipeline.process_events(events)

        mock_structural.remove_file.assert_called_once()
        mock_semantic.remove_symbols.assert_called_once()

    @pytest.mark.asyncio
    async def test_deleted_without_cache_still_removes_file(self) -> None:
        mock_structural = MagicMock()
        mock_semantic = AsyncMock()

        pipeline = IncrementalUpdatePipeline(
            parser=MagicMock(),
            extractor=MagicMock(),
            structural_index=mock_structural,
            semantic_index=mock_semantic,
        )

        events = [
            FileEvent(
                path=Path("/repo/a.py"),
                event_type="deleted",
                timestamp=datetime.now(tz=UTC),
            )
        ]
        await pipeline.process_events(events)

        mock_structural.remove_file.assert_called_once()
        # No cached tags, so remove_symbols should not be called
        mock_semantic.remove_symbols.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_on_one_file_does_not_block_others(self) -> None:
        mock_parser = MagicMock()
        # First call raises, second succeeds
        mock_parser.parse_file.side_effect = [
            RuntimeError("parse error"),
            MagicMock(
                tags=[Tag("b.py", "/b.py", 1, "bar", "definition")],
                tree=MagicMock(),
            ),
        ]
        mock_extractor = MagicMock()
        mock_extractor.extract_symbols.return_value = []
        mock_structural = MagicMock()
        mock_semantic = AsyncMock()

        pipeline = IncrementalUpdatePipeline(
            parser=mock_parser,
            extractor=mock_extractor,
            structural_index=mock_structural,
            semantic_index=mock_semantic,
        )

        events = [
            FileEvent(
                path=Path("/repo/a.py"),
                event_type="created",
                timestamp=datetime.now(tz=UTC),
            ),
            FileEvent(
                path=Path("/repo/b.py"),
                event_type="created",
                timestamp=datetime.now(tz=UTC),
            ),
        ]
        await pipeline.process_events(events)

        # Second file should still be processed
        assert mock_structural.update_file.call_count == 1

    @pytest.mark.asyncio
    async def test_modified_with_cache_diffs_tags(self) -> None:
        """Modified event with pre-existing cache performs a diff."""
        old_tags = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 5, "bar", "definition"),
        ]
        new_tags = [
            Tag("a.py", "/a.py", 1, "foo", "definition"),
            Tag("a.py", "/a.py", 10, "baz", "definition"),  # bar removed, baz added
        ]

        mock_parser = MagicMock()
        mock_parser.parse_file.return_value = MagicMock(
            tags=new_tags,
            tree=MagicMock(),
        )
        mock_extractor = MagicMock()
        mock_extractor.extract_symbols.return_value = [MagicMock()]
        mock_structural = MagicMock()
        mock_semantic = AsyncMock()

        pipeline = IncrementalUpdatePipeline(
            parser=mock_parser,
            extractor=mock_extractor,
            structural_index=mock_structural,
            semantic_index=mock_semantic,
        )
        pipeline._tag_cache[str(Path("/repo/a.py"))] = old_tags

        events = [
            FileEvent(
                path=Path("/repo/a.py"),
                event_type="modified",
                timestamp=datetime.now(tz=UTC),
            )
        ]
        await pipeline.process_events(events)

        mock_structural.update_file.assert_called_once()
        mock_semantic.remove_symbols.assert_called_once_with(["bar"])
        mock_semantic.upsert_symbols.assert_called_once()
