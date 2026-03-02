"""End-to-end tests for UserProfileProjection against real PostgreSQL.

Saves user aggregates via UserApplication, processes events through
the projection, and verifies the user_profile table.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.domain.identity.infrastructure.projections.user_profile import (
    UserProfileProjection,
)
from praecepta.domain.identity.infrastructure.user_profile_repository import (
    UserProfileRepository,
)


@pytest.mark.integration
class TestUserProfileProjectionE2E:
    """UserProfileProjection end-to-end tests with real PostgreSQL."""

    def _make_projection(self, sync_session_factory):
        repo = UserProfileRepository(session_factory=sync_session_factory)
        view = MagicMock()
        return UserProfileProjection(view=view, repository=repo), repo

    def _get_events(self, user_app, aggregate_id):
        events = []
        start = 1
        while True:
            notifications = user_app.notification_log.select(start=start, limit=10)
            if not notifications:
                break
            for notification in notifications:
                event = user_app.mapper.to_domain_event(notification)
                if event.originator_id == aggregate_id:
                    events.append(event)
            if len(notifications) < 10:
                break
            start += 10
        return events

    def test_provisioned_materializes_user_profile(self, user_app, sync_session_factory):
        """Provisioned event should UPSERT into user_profile table."""
        from praecepta.domain.identity.user import User

        user = User(
            oidc_sub="auth0|proj-user",
            tenant_id="acme",
            email="proj@acme.com",
            name="Proj User",
        )
        user_app.save(user)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(user_app, user.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        row = repo._get_by_user_id_sync(user.id, "acme")
        assert row is not None
        assert row.oidc_sub == "auth0|proj-user"
        assert row.display_name == "Proj User"
        assert row.email == "proj@acme.com"

    def test_profile_updated_changes_display_name(self, user_app, sync_session_factory):
        """ProfileUpdated event should update display_name in projection."""
        from praecepta.domain.identity.user import User

        user = User(
            oidc_sub="auth0|update-name",
            tenant_id="acme",
            email="update@acme.com",
            name="Original",
        )
        user_app.save(user)

        user = user_app.repository.get(user.id)
        user.request_update_display_name("New Name")
        user_app.save(user)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(user_app, user.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        row = repo._get_by_user_id_sync(user.id, "acme")
        assert row is not None
        assert row.display_name == "New Name"

    def test_clear_read_model_truncates(self, user_app, sync_session_factory):
        """clear_read_model() should TRUNCATE the user_profile table."""
        from praecepta.domain.identity.user import User

        user = User(
            oidc_sub="auth0|clear-user",
            tenant_id="acme",
            email="clear@acme.com",
            name=None,
        )
        user_app.save(user)

        projection, repo = self._make_projection(sync_session_factory)
        events = self._get_events(user_app, user.id)
        tracking = MagicMock()

        for event in events:
            projection.process_event(event, tracking)

        # Verify row exists
        assert repo._get_by_user_id_sync(user.id, "acme") is not None

        projection.clear_read_model()

        # After clear, row should be gone
        assert repo._get_by_user_id_sync(user.id, "acme") is None
