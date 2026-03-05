"""Integration tests for file watcher."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from praecepta.infra.codeintel.watcher.file_watcher import WatchdogFileWatcher

if TYPE_CHECKING:
    from pathlib import Path

    from praecepta.infra.codeintel.types import FileEvent


@pytest.mark.integration
class TestFileWatcherIntegration:
    @pytest.mark.asyncio
    async def test_create_file_emits_event(self, tmp_path: Path) -> None:
        events_received: list[FileEvent] = []

        async def on_change(events: list[FileEvent]) -> None:
            events_received.extend(events)

        watcher = WatchdogFileWatcher()
        watcher.start(tmp_path, on_change)

        try:
            # Create a Python file
            (tmp_path / "new_file.py").write_text("print('hello')")
            await asyncio.sleep(2.0)  # wait for debounce + processing

            assert len(events_received) > 0
            # On Windows, watchdog may report "created" as "modified"
            assert any(e.event_type in ("created", "modified") for e in events_received)
        finally:
            watcher.stop()

    @pytest.mark.asyncio
    async def test_modify_file_emits_event(self, tmp_path: Path) -> None:
        f = tmp_path / "existing.py"
        f.write_text("original")

        events_received: list[FileEvent] = []

        async def on_change(events: list[FileEvent]) -> None:
            events_received.extend(events)

        watcher = WatchdogFileWatcher()
        watcher.start(tmp_path, on_change)

        try:
            await asyncio.sleep(0.5)  # let watcher settle
            f.write_text("modified")
            await asyncio.sleep(2.0)

            assert len(events_received) > 0
            assert any(e.event_type == "modified" for e in events_received)
        finally:
            watcher.stop()

    @pytest.mark.asyncio
    async def test_delete_file_emits_event(self, tmp_path: Path) -> None:
        f = tmp_path / "to_delete.py"
        f.write_text("delete me")

        events_received: list[FileEvent] = []

        async def on_change(events: list[FileEvent]) -> None:
            events_received.extend(events)

        watcher = WatchdogFileWatcher()
        watcher.start(tmp_path, on_change)

        try:
            await asyncio.sleep(0.5)  # let watcher settle
            f.unlink()
            await asyncio.sleep(2.0)

            assert len(events_received) > 0
            assert any(e.event_type == "deleted" for e in events_received)
        finally:
            watcher.stop()

    @pytest.mark.asyncio
    async def test_unsupported_extension_ignored(self, tmp_path: Path) -> None:
        events_received: list[FileEvent] = []

        async def on_change(events: list[FileEvent]) -> None:
            events_received.extend(events)

        watcher = WatchdogFileWatcher()
        watcher.start(tmp_path, on_change)

        try:
            (tmp_path / "readme.md").write_text("# Hello")
            await asyncio.sleep(2.0)

            assert len(events_received) == 0
        finally:
            watcher.stop()
