"""Unit tests for OidcSubRegistry with mock app/datastore."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.oidc_sub_registry import OidcSubRegistry


def _make_mock_app() -> tuple[MagicMock, MagicMock]:
    """Create a mock Application with a datastore that supports transactions."""
    app = MagicMock()
    cursor = MagicMock()

    @contextmanager
    def transaction(commit: bool = False):  # type: ignore[no-untyped-def]
        yield cursor

    app.factory.datastore.transaction = transaction
    return app, cursor


@pytest.mark.unit
class TestOidcSubRegistryReserve:
    def test_executes_reserve_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = OidcSubRegistry(app)
        registry.reserve("test-sub", "acme-corp")
        cursor.execute.assert_called_once()
        args = cursor.execute.call_args[0]
        assert "test-sub" in args[1]
        assert "acme-corp" in args[1]


@pytest.mark.unit
class TestOidcSubRegistryConfirm:
    def test_executes_confirm_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = OidcSubRegistry(app)
        user_id = uuid4()
        registry.confirm("test-sub", user_id)
        cursor.execute.assert_called_once()
        args = cursor.execute.call_args[0]
        assert str(user_id) in args[1]


@pytest.mark.unit
class TestOidcSubRegistryRelease:
    def test_executes_release_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = OidcSubRegistry(app)
        registry.release("test-sub")
        cursor.execute.assert_called_once()


@pytest.mark.unit
class TestOidcSubRegistryLookup:
    def test_returns_none_when_not_found(self) -> None:
        app, cursor = _make_mock_app()
        cursor.fetchone.return_value = None
        registry = OidcSubRegistry(app)
        assert registry.lookup("unknown-sub") is None

    def test_returns_user_id_when_found(self) -> None:
        app, cursor = _make_mock_app()
        user_id = uuid4()
        cursor.fetchone.return_value = {"user_id": user_id}
        registry = OidcSubRegistry(app)
        assert registry.lookup("test-sub") == user_id


@pytest.mark.unit
class TestOidcSubRegistryTableCreation:
    def test_skips_when_no_datastore(self) -> None:
        app = MagicMock(spec=[])
        app.factory = MagicMock(spec=[])
        OidcSubRegistry.ensure_table_exists(app)

    def test_creates_table_when_datastore_available(self) -> None:
        app, cursor = _make_mock_app()
        OidcSubRegistry.ensure_table_exists(app)
        cursor.execute.assert_called_once()
