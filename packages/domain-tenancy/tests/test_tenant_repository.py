"""Unit tests for TenantRepository with mock session."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.domain.tenancy.infrastructure.tenant_repository import TenantRepository


def _mock_session_factory() -> MagicMock:
    """Create a mock session factory."""
    session = MagicMock()
    factory = MagicMock(return_value=session)
    factory.__enter__ = MagicMock(return_value=session)
    factory.__exit__ = MagicMock(return_value=False)
    # Make the factory work as a context manager
    session_cm = MagicMock()
    session_cm.__enter__ = MagicMock(return_value=session)
    session_cm.__exit__ = MagicMock(return_value=False)
    factory.return_value = session_cm
    return factory


@pytest.mark.unit
class TestTenantRepositoryGet:
    """Read operations."""

    def test_get_returns_none_when_not_found(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)
        session = factory.return_value.__enter__.return_value
        session.execute.return_value.fetchone.return_value = None

        result = repo.get("acme-corp")
        assert result is None

    def test_get_returns_tenant_dict(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)
        session = factory.return_value.__enter__.return_value
        session.execute.return_value.fetchone.return_value = (
            "uuid-1",
            "acme-corp",
            "ACME",
            "ACTIVE",
            "2026-01-15",
            "2026-01-16",
            None,
            None,
        )

        result = repo.get("acme-corp")
        assert result is not None
        assert result["slug"] == "acme-corp"
        assert result["status"] == "ACTIVE"


@pytest.mark.unit
class TestTenantRepositoryListAll:
    """List operations."""

    def test_list_all_returns_empty(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)
        session = factory.return_value.__enter__.return_value
        session.execute.return_value.fetchall.return_value = []

        result = repo.list_all()
        assert result == []

    def test_list_all_with_status_filter(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)
        session = factory.return_value.__enter__.return_value
        session.execute.return_value.fetchall.return_value = []

        repo.list_all(status="ACTIVE")
        session.execute.assert_called_once()


@pytest.mark.unit
class TestTenantRepositoryUpsert:
    """Write operations."""

    def test_upsert_calls_execute_and_commit(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)
        session = factory.return_value.__enter__.return_value

        repo.upsert(
            tenant_id="uuid-1",
            slug="acme-corp",
            name="ACME",
            status="PROVISIONING",
            timestamp="2026-01-15T10:30:00+00:00",
        )
        session.execute.assert_called_once()
        session.commit.assert_called_once()


@pytest.mark.unit
class TestTenantRepositoryUpdateStatus:
    """Status update operations."""

    def test_update_status_calls_execute_and_commit(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)
        session = factory.return_value.__enter__.return_value

        repo.update_status(
            tenant_id="uuid-1",
            status="ACTIVE",
            timestamp_column="activated_at",
            timestamp="2026-01-16T10:30:00+00:00",
        )
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    def test_rejects_invalid_timestamp_column(self) -> None:
        factory = _mock_session_factory()
        repo = TenantRepository(session_factory=factory)

        with pytest.raises(ValueError, match="Invalid timestamp column"):
            repo.update_status(
                tenant_id="uuid-1",
                status="ACTIVE",
                timestamp_column="malicious_column",
                timestamp="2026-01-16T10:30:00+00:00",
            )
