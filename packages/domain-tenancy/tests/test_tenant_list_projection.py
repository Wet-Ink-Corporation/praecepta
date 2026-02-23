"""Unit tests for TenantListProjection with mock repository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.domain.tenancy.infrastructure.projections.tenant_list import (
    TenantListProjection,
)


def _make_event(
    *,
    event_name: str,
    originator_id: str | None = None,
    slug: str = "acme-corp",
    name: str = "ACME",
    **kwargs: object,
) -> MagicMock:
    """Create a mock lifecycle event."""
    event = MagicMock()
    event.__class__ = type(event_name, (), {})
    event.__class__.__name__ = event_name
    event.originator_id = originator_id or uuid4()
    event.timestamp = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
    event.slug = slug
    event.name = name
    for k, v in kwargs.items():
        setattr(event, k, v)
    return event


@pytest.mark.unit
class TestTenantListProjectionUpstream:
    """Upstream application declaration."""

    def test_declares_upstream_application(self) -> None:
        from praecepta.domain.tenancy.tenant_app import TenantApplication

        assert TenantListProjection.upstream_application is TenantApplication


@pytest.mark.unit
class TestTenantListProjectionTopics:
    """Topic configuration."""

    def test_subscribes_to_lifecycle_events(self) -> None:
        assert len(TenantListProjection.topics) == 5

    def test_includes_provisioned(self) -> None:
        topics = TenantListProjection.topics
        assert any("Tenant.Provisioned" in t for t in topics)

    def test_includes_activated(self) -> None:
        topics = TenantListProjection.topics
        assert any("Tenant.Activated" in t for t in topics)

    def test_includes_suspended(self) -> None:
        topics = TenantListProjection.topics
        assert any("Tenant.Suspended" in t for t in topics)

    def test_includes_reactivated(self) -> None:
        topics = TenantListProjection.topics
        assert any("Tenant.Reactivated" in t for t in topics)

    def test_includes_decommissioned(self) -> None:
        topics = TenantListProjection.topics
        assert any("Tenant.Decommissioned" in t for t in topics)


@pytest.mark.unit
class TestTenantListProjectionPolicy:
    """Event handling via policy method."""

    def test_upserts_on_provisioned(self) -> None:
        mock_repo = MagicMock()
        projection = TenantListProjection(repository=mock_repo)
        event = _make_event(event_name="Provisioned", slug="acme-corp", name="ACME")
        mock_processing = MagicMock()

        projection.policy(event, mock_processing)

        mock_repo.upsert.assert_called_once_with(
            tenant_id=str(event.originator_id),
            slug="acme-corp",
            name="ACME",
            status="PROVISIONING",
            timestamp="2026-01-15T10:30:00+00:00",
        )

    def test_updates_status_on_activated(self) -> None:
        mock_repo = MagicMock()
        projection = TenantListProjection(repository=mock_repo)
        event = _make_event(event_name="Activated")

        projection.policy(event, MagicMock())

        mock_repo.update_status.assert_called_once_with(
            tenant_id=str(event.originator_id),
            status="ACTIVE",
            timestamp_column="activated_at",
            timestamp="2026-01-15T10:30:00+00:00",
        )

    def test_updates_status_on_suspended(self) -> None:
        mock_repo = MagicMock()
        projection = TenantListProjection(repository=mock_repo)
        event = _make_event(event_name="Suspended")

        projection.policy(event, MagicMock())

        mock_repo.update_status.assert_called_once_with(
            tenant_id=str(event.originator_id),
            status="SUSPENDED",
            timestamp_column="suspended_at",
            timestamp="2026-01-15T10:30:00+00:00",
        )

    def test_updates_status_on_reactivated(self) -> None:
        mock_repo = MagicMock()
        projection = TenantListProjection(repository=mock_repo)
        event = _make_event(event_name="Reactivated")

        projection.policy(event, MagicMock())

        mock_repo.update_status.assert_called_once_with(
            tenant_id=str(event.originator_id),
            status="ACTIVE",
            timestamp_column="activated_at",
            timestamp="2026-01-15T10:30:00+00:00",
        )

    def test_updates_status_on_decommissioned(self) -> None:
        mock_repo = MagicMock()
        projection = TenantListProjection(repository=mock_repo)
        event = _make_event(event_name="Decommissioned")

        projection.policy(event, MagicMock())

        mock_repo.update_status.assert_called_once_with(
            tenant_id=str(event.originator_id),
            status="DECOMMISSIONED",
            timestamp_column="decommissioned_at",
            timestamp="2026-01-15T10:30:00+00:00",
        )

    def test_ignores_config_updated_events(self) -> None:
        mock_repo = MagicMock()
        projection = TenantListProjection(repository=mock_repo)
        event = _make_event(event_name="ConfigUpdated")

        projection.policy(event, MagicMock())

        mock_repo.upsert.assert_not_called()
        mock_repo.update_status.assert_not_called()
