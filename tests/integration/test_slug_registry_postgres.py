"""Integration tests for SlugRegistry against real PostgreSQL.

Verifies slug reservation, confirmation, release, and decommission
using the event store's psycopg datastore connection.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.domain.tenancy.infrastructure.slug_registry import SlugRegistry
from praecepta.foundation.domain.exceptions import ConflictError


@pytest.mark.integration
class TestSlugRegistryPostgres:
    """SlugRegistry tests against real PostgreSQL via the event store datastore."""

    def test_ensure_table_exists_creates_table(self, tenant_app):
        """ensure_table_exists should not raise when table already exists (idempotent)."""
        SlugRegistry.ensure_table_exists(tenant_app)

    def test_reserve_slug_succeeds(self, tenant_app):
        registry = SlugRegistry(tenant_app)
        registry.reserve("unique-slug")

    def test_reserve_duplicate_slug_raises_conflict(self, tenant_app):
        registry = SlugRegistry(tenant_app)
        registry.reserve("taken-slug")

        with pytest.raises(ConflictError):
            registry.reserve("taken-slug")

    def test_confirm_sets_tenant_id_and_confirmed(self, tenant_app):
        registry = SlugRegistry(tenant_app)
        tid = uuid4()

        registry.reserve("confirm-me")
        registry.confirm("confirm-me", tid)

        # Verify by trying to reserve again — should still conflict
        with pytest.raises(ConflictError):
            registry.reserve("confirm-me")

    def test_release_removes_unconfirmed_reservation(self, tenant_app):
        registry = SlugRegistry(tenant_app)

        registry.reserve("release-me")
        registry.release("release-me")

        # Should be reservable again after release
        registry.reserve("release-me")

    def test_release_does_not_remove_confirmed(self, tenant_app):
        registry = SlugRegistry(tenant_app)
        tid = uuid4()

        registry.reserve("confirmed-slug")
        registry.confirm("confirmed-slug", tid)
        registry.release("confirmed-slug")  # Should not delete (confirmed=TRUE)

        # Still taken
        with pytest.raises(ConflictError):
            registry.reserve("confirmed-slug")

    def test_decommission_removes_any_reservation(self, tenant_app):
        registry = SlugRegistry(tenant_app)
        tid = uuid4()

        registry.reserve("decom-slug")
        registry.confirm("decom-slug", tid)
        registry.decommission("decom-slug")

        # Should be reservable again after decommission
        registry.reserve("decom-slug")
