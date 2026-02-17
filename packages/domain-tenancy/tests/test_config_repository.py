"""Unit tests for ConfigRepository with mock session_factory."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from praecepta.domain.tenancy.infrastructure.config_repository import ConfigRepository


def _make_session_factory(*, rows: list[tuple[Any, ...]] | None = None) -> Any:
    """Create a mock session_factory returning a context-managed mock session."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    if rows is not None:
        mock_result.fetchone.return_value = rows[0] if len(rows) == 1 else None
        mock_result.fetchall.return_value = rows
    else:
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    @contextmanager
    def factory():  # type: ignore[no-untyped-def]
        yield mock_session

    return factory, mock_session


@pytest.mark.unit
class TestConfigRepositoryGet:
    """ConfigRepository.get() tests."""

    def test_returns_none_when_not_found(self) -> None:
        factory, _ = _make_session_factory()
        repo = ConfigRepository(factory)
        assert repo.get("acme-corp", "feature.x") is None

    def test_returns_value_when_found(self) -> None:
        config_value = {"type": "boolean", "value": True}
        factory, _ = _make_session_factory(rows=[(config_value,)])
        repo = ConfigRepository(factory)
        result = repo.get("acme-corp", "feature.x")
        assert result == config_value


@pytest.mark.unit
class TestConfigRepositoryGetAll:
    """ConfigRepository.get_all() tests."""

    def test_returns_empty_dict_when_no_overrides(self) -> None:
        factory, _ = _make_session_factory()
        repo = ConfigRepository(factory)
        assert repo.get_all("acme-corp") == {}

    def test_returns_overrides_as_dict(self) -> None:
        rows = [
            ("feature.x", {"type": "boolean", "value": True}),
            ("limits.max", {"type": "integer", "value": 100}),
        ]
        factory, _ = _make_session_factory(rows=rows)
        repo = ConfigRepository(factory)
        result = repo.get_all("acme-corp")
        assert result == {
            "feature.x": {"type": "boolean", "value": True},
            "limits.max": {"type": "integer", "value": 100},
        }


@pytest.mark.unit
class TestConfigRepositoryUpsert:
    """ConfigRepository.upsert() tests."""

    def test_calls_execute_and_commit(self) -> None:
        factory, mock_session = _make_session_factory()
        repo = ConfigRepository(factory)
        repo.upsert("acme-corp", "feature.x", {"type": "boolean", "value": True}, "admin")
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.unit
class TestConfigRepositoryDelete:
    """ConfigRepository.delete() tests."""

    def test_returns_false_when_no_rows_affected(self) -> None:
        factory, mock_session = _make_session_factory()
        mock_session.execute.return_value.rowcount = 0
        repo = ConfigRepository(factory)
        assert repo.delete("acme-corp", "feature.x") is False

    def test_returns_true_when_row_deleted(self) -> None:
        factory, mock_session = _make_session_factory()
        mock_session.execute.return_value.rowcount = 1
        repo = ConfigRepository(factory)
        assert repo.delete("acme-corp", "feature.x") is True
