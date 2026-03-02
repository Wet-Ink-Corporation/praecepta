"""Integration tests for TenantRepository against real PostgreSQL.

Verifies UPSERT, queries, and status updates using actual SQL execution.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.domain.tenancy.infrastructure.tenant_repository import TenantRepository


@pytest.mark.integration
class TestTenantRepositoryPostgres:
    """TenantRepository tests against real PostgreSQL."""

    def _make_repo(self, sync_session_factory) -> TenantRepository:
        return TenantRepository(session_factory=sync_session_factory)

    def test_upsert_inserts_new_tenant(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        tid = str(uuid4())

        repo.upsert(
            tenant_id=tid,
            slug="new-tenant",
            name="New Tenant",
            status="PROVISIONING",
            timestamp="2026-01-01T00:00:00+00:00",
        )

        result = repo.get("new-tenant")
        assert result is not None
        assert result["slug"] == "new-tenant"
        assert result["name"] == "New Tenant"
        assert result["status"] == "PROVISIONING"

    def test_upsert_updates_existing_tenant(self, sync_session_factory):
        """ON CONFLICT DO UPDATE should update name and status."""
        repo = self._make_repo(sync_session_factory)
        tid = str(uuid4())

        repo.upsert(tid, "update-me", "Original", "PROVISIONING", "2026-01-01T00:00:00+00:00")
        repo.upsert(tid, "update-me", "Updated Name", "ACTIVE", "2026-01-01T00:00:00+00:00")

        result = repo.get("update-me")
        assert result is not None
        assert result["name"] == "Updated Name"
        assert result["status"] == "ACTIVE"

    def test_get_returns_none_for_missing_slug(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        assert repo.get("nonexistent") is None

    def test_list_all_returns_all_tenants(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        for i in range(3):
            repo.upsert(
                str(uuid4()), f"tenant-{i}", f"Tenant {i}", "ACTIVE", "2026-01-01T00:00:00+00:00"
            )

        results = repo.list_all()
        assert len(results) == 3

    def test_list_all_with_status_filter(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        repo.upsert(str(uuid4()), "active-one", "Active", "ACTIVE", "2026-01-01T00:00:00+00:00")
        repo.upsert(
            str(uuid4()), "suspended-one", "Suspended", "SUSPENDED", "2026-01-01T00:00:00+00:00"
        )

        active = repo.list_all(status="ACTIVE")
        assert len(active) == 1
        assert active[0]["slug"] == "active-one"

    def test_update_status_sets_timestamp_column(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        tid = str(uuid4())

        repo.upsert(tid, "status-test", "Status Test", "PROVISIONING", "2026-01-01T00:00:00+00:00")
        repo.update_status(tid, "ACTIVE", "activated_at", "2026-01-02T00:00:00+00:00")

        result = repo.get("status-test")
        assert result is not None
        assert result["status"] == "ACTIVE"
        assert result["activated_at"] is not None
