"""Integration tests for TenantApplication against real PostgreSQL.

Verifies aggregate persistence, lifecycle transitions, snapshotting,
and configuration updates with a real event store.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestTenantApplicationPostgres:
    """TenantApplication round-trip tests against real PostgreSQL."""

    def test_save_and_retrieve_tenant(self, tenant_app):
        """Create, save, reload, and verify tenant state."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="acme", name="Acme Corp", slug="acme", config=None, metadata=None)
        tenant_app.save(tenant)

        reloaded = tenant_app.repository.get(tenant.id)
        assert reloaded.slug == "acme"
        assert reloaded.name == "Acme Corp"
        assert reloaded.status == "PROVISIONING"

    def test_full_lifecycle_save_and_reload(self, tenant_app):
        """Walk through provision→activate→suspend→reactivate→decommission."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(
            tenant_id="lifecycle", name="Lifecycle Co", slug="lifecycle", config=None, metadata=None
        )
        tenant_app.save(tenant)

        # Activate
        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_activate(initiated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        assert tenant.status == "ACTIVE"

        # Suspend
        tenant.request_suspend(initiated_by="admin", reason="maintenance")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        assert tenant.status == "SUSPENDED"

        # Reactivate
        tenant.request_reactivate(initiated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        assert tenant.status == "ACTIVE"

        # Decommission
        tenant.request_decommission(initiated_by="admin", reason="no longer needed")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        assert tenant.status == "DECOMMISSIONED"

    def test_concurrent_save_raises_conflict(self, tenant_app):
        """Two Application instances saving same aggregate causes conflict."""
        from eventsourcing.persistence import RecordConflictError

        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(
            tenant_id="concur", name="Concurrent Co", slug="concur", config=None, metadata=None
        )
        tenant_app.save(tenant)

        copy1 = tenant_app.repository.get(tenant.id)
        copy2 = tenant_app.repository.get(tenant.id)

        copy1.request_activate(initiated_by="admin1")
        tenant_app.save(copy1)

        copy2.request_activate(initiated_by="admin2")
        with pytest.raises(RecordConflictError):
            tenant_app.save(copy2)

    def test_snapshotting_triggers_after_threshold(self, tenant_app):
        """After 51 events, verify the aggregate can still be loaded (snapshot path)."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(
            tenant_id="snap-co", name="Snap Co", slug="snap-co", config=None, metadata=None
        )
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_activate(initiated_by="admin")
        tenant_app.save(tenant)

        # Generate 49 more events (config updates) to cross the 50-event threshold
        for i in range(49):
            tenant = tenant_app.repository.get(tenant.id)
            tenant.request_update_config(
                config_key=f"key-{i}",
                config_value={"value": i},
                updated_by="admin",
            )
            tenant_app.save(tenant)

        # Total: 1 (Provisioned) + 1 (Activated) + 49 (ConfigUpdated) = 51 events
        # Snapshot should have been created at event 50
        reloaded = tenant_app.repository.get(tenant.id)
        assert reloaded.status == "ACTIVE"
        assert len(reloaded.config) == 49

    def test_config_update_persists_across_reloads(self, tenant_app):
        """Activate, update config, reload, verify config persisted."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(
            tenant_id="cfg-co", name="Config Co", slug="cfg-co", config=None, metadata=None
        )
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_activate(initiated_by="admin")
        tenant_app.save(tenant)

        tenant = tenant_app.repository.get(tenant.id)
        tenant.request_update_config(
            config_key="features",
            config_value={"dark_mode": True, "beta": False},
            updated_by="admin",
        )
        tenant_app.save(tenant)

        reloaded = tenant_app.repository.get(tenant.id)
        assert reloaded.config["features"] == {"dark_mode": True, "beta": False}
