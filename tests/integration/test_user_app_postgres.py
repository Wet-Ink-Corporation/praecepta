"""Integration tests for UserApplication against real PostgreSQL.

Verifies user aggregate persistence including profile and preferences updates.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestUserApplicationPostgres:
    """UserApplication round-trip tests against real PostgreSQL."""

    def test_save_and_retrieve_user(self, user_app):
        """Create, save, reload, and verify user state."""
        from praecepta.domain.identity.user import User

        user = User(
            oidc_sub="auth0|user123",
            tenant_id="acme",
            email="alice@acme.com",
            name="Alice",
        )
        user_app.save(user)

        reloaded = user_app.repository.get(user.id)
        assert reloaded.oidc_sub == "auth0|user123"
        assert reloaded.email == "alice@acme.com"
        assert reloaded.display_name == "Alice"
        assert reloaded.tenant_id == "acme"

    def test_user_profile_update_persists(self, user_app):
        """Update display_name and verify persistence."""
        from praecepta.domain.identity.user import User

        user = User(
            oidc_sub="auth0|profile",
            tenant_id="acme",
            email="bob@acme.com",
            name="Bob",
        )
        user_app.save(user)

        user = user_app.repository.get(user.id)
        user.request_update_display_name("Robert")
        user_app.save(user)

        reloaded = user_app.repository.get(user.id)
        assert reloaded.display_name == "Robert"

    def test_user_preferences_update_persists(self, user_app):
        """Update preferences and verify persistence."""
        from praecepta.domain.identity.user import User

        user = User(
            oidc_sub="auth0|prefs",
            tenant_id="acme",
            email="carol@acme.com",
            name=None,
        )
        user_app.save(user)

        user = user_app.repository.get(user.id)
        user.request_update_preferences({"theme": "dark", "locale": "en-US"})
        user_app.save(user)

        reloaded = user_app.repository.get(user.id)
        assert reloaded.preferences == {"theme": "dark", "locale": "en-US"}
