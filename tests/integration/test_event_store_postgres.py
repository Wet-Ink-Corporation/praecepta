"""Integration tests for event store against real PostgreSQL.

Verifies event storage, retrieval, and optimistic concurrency control
using the eventsourcing library's PostgreSQL infrastructure.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestEventStorePostgres:
    """Event store round-trip tests against a real PostgreSQL container."""

    def test_recorder_creates_tables_on_first_access(self, tenant_app):
        """Verify the stored_events table is created on first Application use."""
        # Creating TenantApplication with CREATE_TABLE=true should create tables
        # If we can save and retrieve, the tables exist
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="test-co", name="Test Co", slug="test-co", config=None, metadata=None)
        tenant_app.save(tenant)

        reloaded = tenant_app.repository.get(tenant.id)
        assert reloaded.slug == "test-co"

    def test_recorder_stores_and_reads_events(self, tenant_app):
        """Round-trip: store domain events then read them back."""
        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="round-trip", name="Round Trip", slug="round-trip", config=None, metadata=None)
        tenant_app.save(tenant)

        # Read events from notification log
        events = tenant_app.repository.get(tenant.id)
        assert events is not None
        assert events.slug == "round-trip"
        assert events.status == "PROVISIONING"

    def test_optimistic_concurrency_conflict(self, tenant_app):
        """Saving with stale version raises RecordConflictError."""
        from eventsourcing.persistence import RecordConflictError

        from praecepta.domain.tenancy.tenant import Tenant

        tenant = Tenant(tenant_id="conflict-co", name="Conflict Co", slug="conflict-co", config=None, metadata=None)
        tenant_app.save(tenant)

        # Load two copies of the same aggregate
        copy1 = tenant_app.repository.get(tenant.id)
        copy2 = tenant_app.repository.get(tenant.id)

        # Mutate and save the first copy
        copy1.request_activate(initiated_by="admin")
        tenant_app.save(copy1)

        # Mutate and save the second copy (stale version) — should conflict
        copy2.request_activate(initiated_by="admin2")
        with pytest.raises(RecordConflictError):
            tenant_app.save(copy2)
