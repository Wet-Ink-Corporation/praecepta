"""End-to-end tests for TenantConfigProjection against real PostgreSQL.

Saves config updates via TenantApplication, processes events through
the projection, and verifies the tenant_configuration table.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.domain.tenancy.infrastructure.config_repository import ConfigRepository
from praecepta.domain.tenancy.infrastructure.projections.tenant_config import (
    TenantConfigProjection,
)


@pytest.mark.integration
class TestTenantConfigProjectionE2E:
    """TenantConfigProjection end-to-end tests with real PostgreSQL."""

    def _make_projection(self, sync_session_factory):
        repo = ConfigRepository(session_factory=sync_session_factory)
        view = MagicMock()
        return TenantConfigProjection(view=view, repository=repo), repo

    def _get_events(self, tenant_app, aggregate_id):
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

    def test_config_updated_materializes_to_table(self, tenant_app, sync_session_factory):
        """ConfigUpdated event should UPSERT into tenant_configuration."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(
            tenant_id="cfg-proj", name="Config Proj", slug="cfg-proj", config=None, metadata=None
        )
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_activate(initiated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_update_config("features", {"beta": True}, updated_by="admin")
        tenant_app.save(tenant)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(tenant_app, tenant.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        result = repo.get("cfg-proj", "features")
        assert result == {"beta": True}

    def test_config_update_overwrites_on_upsert(self, tenant_app, sync_session_factory):
        """Second config update to same key should overwrite."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(
            tenant_id="cfg-ow", name="Config Overwrite", slug="cfg-ow", config=None, metadata=None
        )
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_activate(initiated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_update_config("theme", {"color": "blue"}, updated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_update_config("theme", {"color": "red"}, updated_by="admin")
        tenant_app.save(tenant)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(tenant_app, tenant.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        result = repo.get("cfg-ow", "theme")
        assert result == {"color": "red"}
