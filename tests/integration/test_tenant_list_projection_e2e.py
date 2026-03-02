"""End-to-end tests for TenantListProjection against real PostgreSQL.

Saves aggregates via TenantApplication (real event store), creates
projection with real TrackingRecorder and repository, processes
events, and verifies the tenants read model table.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.domain.tenancy.infrastructure.projections.tenant_list import (
    TenantListProjection,
)
from praecepta.domain.tenancy.infrastructure.tenant_repository import TenantRepository


@pytest.mark.integration
class TestTenantListProjectionE2E:
    """TenantListProjection end-to-end tests with real PostgreSQL."""

    def _make_projection(self, sync_session_factory):
        """Create projection with real repository and a mock view for tracking."""
        repo = TenantRepository(session_factory=sync_session_factory)
        view = MagicMock()
        return TenantListProjection(view=view, repository=repo), repo

    def _get_events(self, tenant_app, aggregate_id):
        """Retrieve domain events from the notification log."""
        events = []
        start = 1
        while True:
            notifications = tenant_app.notification_log.select(start=start, limit=10)
            if not notifications:
                break
            for notification in notifications:
                event = tenant_app.mapper.to_domain_event(notification)
                if event.originator_id == aggregate_id:
                    events.append(event)
            if len(notifications) < 10:
                break
            start += 10
        return events

    def test_provisioned_event_materializes_to_tenants_table(
        self, tenant_app, sync_session_factory
    ):
        """Provisioned event should INSERT into tenants table."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="proj-co", name="Proj Co", slug="proj-co", config=None, metadata=None)
        tenant_app.save(tenant)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(tenant_app, tenant.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        row = repo.get("proj-co")
        assert row is not None
        assert row["status"] == "PROVISIONING"
        assert row["name"] == "Proj Co"

    def test_full_lifecycle_updates_projection(self, tenant_app, sync_session_factory):
        """Walk through lifecycle and verify projection updates."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="life-proj", name="Life Proj", slug="life-proj", config=None, metadata=None)
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_activate(initiated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_suspend(initiated_by="admin", reason="test")
        tenant_app.save(tenant)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(tenant_app, tenant.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        row = repo.get("life-proj")
        assert row is not None
        assert row["status"] == "SUSPENDED"
        assert row["suspended_at"] is not None

    def test_projection_is_idempotent_on_replay(self, tenant_app, sync_session_factory):
        """Replaying events should produce the same read model state."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="idem-proj", name="Idem Proj", slug="idem-proj", config=None, metadata=None)
        tenant_app.save(tenant)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(tenant_app, tenant.id)
        tracking = MagicMock()

        # Process events twice (simulate replay)
        for event in events:
            projection.process_event(event, tracking)
        for event in events:
            projection.process_event(event, tracking)

        row = repo.get("idem-proj")
        assert row is not None
        assert row["status"] == "PROVISIONING"
