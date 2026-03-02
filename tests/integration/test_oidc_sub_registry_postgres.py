"""Integration tests for OidcSubRegistry against real PostgreSQL.

Verifies OIDC sub reservation, confirmation, release, and lookup
using the event store's psycopg datastore connection.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.oidc_sub_registry import OidcSubRegistry
from praecepta.foundation.domain.exceptions import ConflictError


@pytest.mark.integration
class TestOidcSubRegistryPostgres:
    """OidcSubRegistry tests against real PostgreSQL via event store datastore."""

    def test_ensure_table_exists_creates_table(self, user_app):
        """ensure_table_exists should not raise (idempotent)."""
        OidcSubRegistry.ensure_table_exists(user_app)

    def test_reserve_oidc_sub_succeeds(self, user_app):
        registry = OidcSubRegistry(user_app)
        registry.reserve("auth0|new-user", "acme")

    def test_reserve_duplicate_raises_conflict(self, user_app):
        registry = OidcSubRegistry(user_app)
        registry.reserve("auth0|taken", "acme")

        with pytest.raises(ConflictError):
            registry.reserve("auth0|taken", "acme")

    def test_confirm_sets_user_id(self, user_app):
        registry = OidcSubRegistry(user_app)
        uid = uuid4()

        registry.reserve("auth0|confirm", "acme")
        registry.confirm("auth0|confirm", uid)

        # Should still be taken after confirmation
        with pytest.raises(ConflictError):
            registry.reserve("auth0|confirm", "acme")

    def test_release_unconfirmed_succeeds(self, user_app):
        registry = OidcSubRegistry(user_app)

        registry.reserve("auth0|release", "acme")
        registry.release("auth0|release")

        # Can reserve again
        registry.reserve("auth0|release", "acme")

    def test_lookup_returns_user_id_for_confirmed(self, user_app):
        registry = OidcSubRegistry(user_app)
        uid = uuid4()

        registry.reserve("auth0|lookup", "acme")
        registry.confirm("auth0|lookup", uid)

        result = registry.lookup("auth0|lookup")
        assert result == uid

    def test_lookup_returns_none_for_nonexistent(self, user_app):
        registry = OidcSubRegistry(user_app)
        assert registry.lookup("auth0|does-not-exist") is None
