"""Unit tests for SlugRegistry with mock app/datastore."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.domain.tenancy.infrastructure.slug_registry import SlugRegistry


def _make_mock_app() -> MagicMock:
    """Create a mock Application with a datastore that supports transactions."""
    app = MagicMock()
    cursor = MagicMock()

    @contextmanager
    def transaction(commit: bool = False):  # type: ignore[no-untyped-def]
        yield cursor

    app.factory.datastore.transaction = transaction
    return app, cursor


@pytest.mark.unit
class TestSlugRegistryReserve:
    """SlugRegistry.reserve() tests."""

    def test_executes_reserve_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = SlugRegistry(app)
        registry.reserve("acme-corp")
        cursor.execute.assert_called_once()
        args = cursor.execute.call_args
        assert "acme-corp" in args[0][1]

    def test_raises_conflict_on_unique_violation(self) -> None:
        from psycopg.errors import UniqueViolation

        from praecepta.foundation.domain.exceptions import ConflictError

        app = MagicMock()

        @contextmanager
        def failing_transaction(commit: bool = False):  # type: ignore[no-untyped-def]
            raise UniqueViolation()
            yield  # type: ignore[misc]  # unreachable but needed for generator

        app.factory.datastore.transaction = failing_transaction
        registry = SlugRegistry(app)
        with pytest.raises(ConflictError, match="already taken"):
            registry.reserve("taken-slug")


@pytest.mark.unit
class TestSlugRegistryConfirm:
    """SlugRegistry.confirm() tests."""

    def test_executes_confirm_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = SlugRegistry(app)
        tenant_id = uuid4()
        registry.confirm("acme-corp", tenant_id)
        cursor.execute.assert_called_once()
        args = cursor.execute.call_args
        assert str(tenant_id) in args[0][1]


@pytest.mark.unit
class TestSlugRegistryRelease:
    """SlugRegistry.release() tests."""

    def test_executes_release_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = SlugRegistry(app)
        registry.release("acme-corp")
        cursor.execute.assert_called_once()


@pytest.mark.unit
class TestSlugRegistryDecommission:
    """SlugRegistry.decommission() tests."""

    def test_executes_decommission_sql(self) -> None:
        app, cursor = _make_mock_app()
        registry = SlugRegistry(app)
        registry.decommission("acme-corp")
        cursor.execute.assert_called_once()


@pytest.mark.unit
class TestSlugRegistryTableCreation:
    """SlugRegistry.ensure_table_exists() tests."""

    def test_skips_when_no_datastore(self) -> None:
        app = MagicMock(spec=[])  # no factory attribute
        app.factory = MagicMock(spec=[])  # no datastore attribute
        SlugRegistry.ensure_table_exists(app)
        # Should not raise

    def test_creates_table_when_datastore_available(self) -> None:
        app, cursor = _make_mock_app()
        SlugRegistry.ensure_table_exists(app)
        cursor.execute.assert_called_once()
