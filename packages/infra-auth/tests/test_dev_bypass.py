"""Tests for development bypass resolution."""

from __future__ import annotations

import pytest

from praecepta.infra.auth.dev_bypass import resolve_dev_bypass


@pytest.mark.unit
class TestResolveDevBypass:
    """Test resolve_dev_bypass production lockout and activation."""

    def test_not_requested_returns_false(self) -> None:
        assert resolve_dev_bypass(False) is False

    def test_production_blocks_bypass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert resolve_dev_bypass(True) is False

    def test_development_allows_bypass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert resolve_dev_bypass(True) is True

    def test_staging_allows_bypass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "staging")
        assert resolve_dev_bypass(True) is True

    def test_default_environment_allows_bypass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        assert resolve_dev_bypass(True) is True
