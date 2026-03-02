"""Integration tests for UserProfileRepository against real PostgreSQL.

Verifies UPSERT, update, truncate operations with real JSONB and indexes.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.user_profile_repository import (
    UserProfileRepository,
)


@pytest.mark.integration
class TestUserProfileRepositoryPostgres:
    """UserProfileRepository tests against real PostgreSQL."""

    def _make_repo(self, sync_session_factory) -> UserProfileRepository:
        return UserProfileRepository(session_factory=sync_session_factory)

    def test_upsert_full_inserts_new_profile(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        uid = uuid4()

        repo.upsert_full(
            user_id=uid,
            oidc_sub="auth0|test1",
            email="test@acme.com",
            display_name="Test User",
            tenant_id="acme",
            preferences={"theme": "light"},
        )

        # Verify via sync read
        row = repo._get_by_user_id_sync(uid, "acme")
        assert row is not None
        assert row.oidc_sub == "auth0|test1"
        assert row.email == "test@acme.com"
        assert row.display_name == "Test User"
        assert row.preferences == {"theme": "light"}

    def test_upsert_full_idempotent_replay(self, sync_session_factory):
        """Same user_id twice should not raise an error (ON CONFLICT)."""
        repo = self._make_repo(sync_session_factory)
        uid = uuid4()

        repo.upsert_full(uid, "auth0|replay", "a@b.com", "First", "acme", {})
        repo.upsert_full(uid, "auth0|replay", "a@b.com", "Second", "acme", {"updated": True})

        row = repo._get_by_user_id_sync(uid, "acme")
        assert row is not None
        assert row.display_name == "Second"
        assert row.preferences == {"updated": True}

    def test_update_display_name(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        uid = uuid4()

        repo.upsert_full(uid, "auth0|name", "n@b.com", "Original", "acme", {})
        repo.update_display_name(uid, "Updated Name")

        row = repo._get_by_user_id_sync(uid, "acme")
        assert row is not None
        assert row.display_name == "Updated Name"

    def test_update_preferences_jsonb(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        uid = uuid4()

        repo.upsert_full(uid, "auth0|prefs", "p@b.com", "User", "acme", {})
        repo.update_preferences(uid, {"locale": "fr-FR", "timezone": "Europe/Paris"})

        row = repo._get_by_user_id_sync(uid, "acme")
        assert row is not None
        assert row.preferences == {"locale": "fr-FR", "timezone": "Europe/Paris"}

    def test_truncate_removes_all(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        for i in range(3):
            repo.upsert_full(uuid4(), f"auth0|trunc{i}", f"t{i}@b.com", "User", "acme", {})

        repo.truncate()

        # After truncate, reading should return None
        row = repo._get_by_user_id_sync(uuid4(), "acme")
        assert row is None
