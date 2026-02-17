"""Shared fixtures for domain-tenancy tests."""

from __future__ import annotations

import pytest

from praecepta.domain.tenancy.tenant import Tenant


@pytest.fixture()
def new_tenant() -> Tenant:
    """Create a Tenant in PROVISIONING state."""
    return Tenant(tenant_id="acme-corp", name="ACME", slug="acme-corp", config=None, metadata=None)


@pytest.fixture()
def active_tenant() -> Tenant:
    """Create a Tenant in ACTIVE state."""
    tenant = Tenant(
        tenant_id="acme-corp", name="ACME", slug="acme-corp", config=None, metadata=None
    )
    tenant.request_activate(initiated_by="system")
    return tenant


@pytest.fixture()
def suspended_tenant() -> Tenant:
    """Create a Tenant in SUSPENDED state."""
    tenant = Tenant(
        tenant_id="acme-corp", name="ACME", slug="acme-corp", config=None, metadata=None
    )
    tenant.request_activate(initiated_by="system")
    tenant.request_suspend(initiated_by="admin", reason="maintenance")
    return tenant


@pytest.fixture()
def decommissioned_tenant() -> Tenant:
    """Create a Tenant in DECOMMISSIONED state."""
    tenant = Tenant(
        tenant_id="acme-corp", name="ACME", slug="acme-corp", config=None, metadata=None
    )
    tenant.request_activate(initiated_by="system")
    tenant.request_decommission(initiated_by="admin", reason="customer churn")
    return tenant
