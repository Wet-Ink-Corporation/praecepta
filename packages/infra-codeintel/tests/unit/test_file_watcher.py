"""Unit tests for file watcher."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praecepta.infra.codeintel.protocols import FileWatcher
from praecepta.infra.codeintel.watcher.file_watcher import WatchdogFileWatcher, _DebouncedHandler


@pytest.mark.unit
class TestWatchdogFileWatcher:
    def test_conforms_to_protocol(self) -> None:
        watcher = WatchdogFileWatcher()
        assert isinstance(watcher, FileWatcher)

    def test_supported_extensions_pass(self) -> None:
        """Verify .py, .ts, .js trigger events."""
        handler = _DebouncedHandler(
            callback=AsyncMock(),
            debounce_ms=300,
            exclude_patterns=[],
            loop=None,  # type: ignore[arg-type]
        )
        assert handler._should_process("/repo/src/main.py") is True
        assert handler._should_process("/repo/src/app.ts") is True
        assert handler._should_process("/repo/src/index.js") is True
        assert handler._should_process("/repo/src/component.tsx") is True
        assert handler._should_process("/repo/src/module.mjs") is True

    def test_unsupported_extensions_filtered(self) -> None:
        """Verify that .md, .txt, etc. don't trigger events."""
        handler = _DebouncedHandler(
            callback=AsyncMock(),
            debounce_ms=300,
            exclude_patterns=[],
            loop=None,  # type: ignore[arg-type]
        )
        assert handler._should_process("/repo/README.md") is False
        assert handler._should_process("/repo/notes.txt") is False
        assert handler._should_process("/repo/image.png") is False
        assert handler._should_process("/repo/data.json") is False
        assert handler._should_process("/repo/style.css") is False

    def test_gitignore_patterns_filter(self) -> None:
        """Verify that files matching exclude_patterns are not reported."""
        handler = _DebouncedHandler(
            callback=AsyncMock(),
            debounce_ms=300,
            exclude_patterns=["**/node_modules/**", "**/__pycache__/**", "**/dist/**"],
            loop=None,  # type: ignore[arg-type]
        )
        # These should be filtered out despite having supported extensions
        assert handler._should_process("/repo/node_modules/pkg/index.js") is False
        assert handler._should_process("/repo/src/__pycache__/module.py") is False
        assert handler._should_process("/repo/dist/bundle.js") is False

        # These should pass
        assert handler._should_process("/repo/src/main.py") is True
        assert handler._should_process("/repo/src/utils.ts") is True

    def test_stop_without_start(self) -> None:
        """Calling stop() before start() should not raise."""
        watcher = WatchdogFileWatcher()
        watcher.stop()  # Should not raise
