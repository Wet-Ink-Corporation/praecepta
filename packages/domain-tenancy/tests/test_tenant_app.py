"""Unit tests for TenantApplication."""

from __future__ import annotations

import pytest

from praecepta.domain.tenancy.tenant import Tenant
from praecepta.domain.tenancy.tenant_app import TenantApplication


@pytest.mark.unit
class TestTenantApplication:
    """TenantApplication configuration and instantiation."""

    def test_snapshotting_interval_configured(self) -> None:
        assert TenantApplication.snapshotting_intervals == {Tenant: 50}

    def test_can_instantiate(self) -> None:
        app = TenantApplication()
        assert app is not None

    def test_save_and_retrieve(self) -> None:
        """Round-trip: save tenant and retrieve from in-memory event store."""
        app = TenantApplication()
        tenant = Tenant(
            tenant_id="test-slug", name="Test", slug="test-slug", config=None, metadata=None
        )
        app.save(tenant)

        retrieved = app.repository.get(tenant.id)
        assert retrieved.tenant_id == "test-slug"
        assert retrieved.name == "Test"
        assert retrieved.version == 1

    def test_save_with_multiple_events(self) -> None:
        """Aggregate with multiple events reconstitutes correctly."""
        app = TenantApplication()
        tenant = Tenant(
            tenant_id="multi-ev", name="Multi", slug="multi-ev", config=None, metadata=None
        )
        tenant.request_activate(initiated_by="system")
        app.save(tenant)

        retrieved = app.repository.get(tenant.id)
        assert retrieved.status == "ACTIVE"
        assert retrieved.version == 2
