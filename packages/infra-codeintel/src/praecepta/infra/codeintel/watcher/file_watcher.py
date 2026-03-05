"""File watcher using watchdog with debouncing and filtering."""

from __future__ import annotations

import asyncio
import fnmatch
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from praecepta.infra.codeintel.parser.language_registry import LANGUAGE_EXTENSIONS
from praecepta.infra.codeintel.settings import get_settings
from praecepta.infra.codeintel.types import FileEvent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class _DebouncedHandler(FileSystemEventHandler):
    """Collects events and debounces before dispatching."""

    def __init__(
        self,
        callback: Callable[[list[FileEvent]], Awaitable[None]],
        debounce_ms: int,
        exclude_patterns: list[str],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._callback = callback
        self._debounce_s = debounce_ms / 1000.0
        self._exclude_patterns = exclude_patterns
        self._loop = loop
        self._pending: dict[str, FileEvent] = {}
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _should_process(self, path: str) -> bool:
        """Check if file has a supported extension and isn't excluded."""
        p = Path(path)
        if p.suffix.lower() not in LANGUAGE_EXTENSIONS:
            return False
        return all(not fnmatch.fnmatch(path, pattern) for pattern in self._exclude_patterns)

    def _map_event_type(self, event: FileSystemEvent) -> str:
        """Map watchdog event types to our event types."""
        if event.event_type == "created":
            return "created"
        elif event.event_type == "deleted":
            return "deleted"
        return "modified"

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src_path = str(event.src_path)
        if not self._should_process(src_path):
            return

        file_event = FileEvent(
            path=Path(src_path),
            event_type=self._map_event_type(event),  # type: ignore[arg-type]
            timestamp=datetime.now(tz=UTC),
        )

        with self._lock:
            self._pending[src_path] = file_event
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_s, self._flush)
            self._timer.start()

    def _flush(self) -> None:
        """Dispatch accumulated events."""
        with self._lock:
            events = list(self._pending.values())
            self._pending.clear()

        if events:
            coro = self._callback(events)
            asyncio.run_coroutine_threadsafe(coro, self._loop)  # type: ignore[arg-type]


class WatchdogFileWatcher:
    """FileWatcher implementation using watchdog."""

    def __init__(self) -> None:
        self._observer: Any = None

    def start(
        self,
        repo_root: Path,
        on_change: Callable[[list[FileEvent]], Awaitable[None]],
    ) -> None:
        """Begin watching repo_root recursively."""
        settings = get_settings()
        loop = asyncio.get_running_loop()

        handler = _DebouncedHandler(
            callback=on_change,
            debounce_ms=settings.watcher_debounce_ms,
            exclude_patterns=settings.exclude_patterns,
            loop=loop,
        )

        self._observer = Observer()
        self._observer.schedule(handler, str(repo_root), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stop watching and clean up."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None
