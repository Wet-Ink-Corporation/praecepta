"""Unit tests for UserProfileProjection with mock repository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.projections.user_profile import (
    UserProfileProjection,
)


def _make_provisioned_event(
    *,
    oidc_sub: str = "test-sub",
    email: str = "test@example.com",
    name: str | None = "Test User",
    tenant_id: str = "acme-corp",
) -> MagicMock:
    event = MagicMock()
    event.__class__ = type("Provisioned", (), {})
    event.__class__.__name__ = "Provisioned"
    event.originator_id = uuid4()
    event.oidc_sub = oidc_sub
    event.email = email
    event.name = name
    event.tenant_id = tenant_id
    return event


def _make_profile_updated_event(*, display_name: str = "New Name") -> MagicMock:
    event = MagicMock()
    event.__class__ = type("ProfileUpdated", (), {})
    event.__class__.__name__ = "ProfileUpdated"
    event.originator_id = uuid4()
    event.display_name = display_name
    return event


def _make_preferences_updated_event(
    *,
    preferences: dict | None = None,  # type: ignore[type-arg]
) -> MagicMock:
    event = MagicMock()
    event.__class__ = type("PreferencesUpdated", (), {})
    event.__class__.__name__ = "PreferencesUpdated"
    event.originator_id = uuid4()
    event.preferences = preferences or {"theme": "dark"}
    return event


@pytest.mark.unit
class TestUserProfileProjectionTopics:
    def test_subscribes_to_user_events(self) -> None:
        assert len(UserProfileProjection.topics) == 3
        assert any("User.Provisioned" in t for t in UserProfileProjection.topics)
        assert any("User.ProfileUpdated" in t for t in UserProfileProjection.topics)
        assert any("User.PreferencesUpdated" in t for t in UserProfileProjection.topics)


@pytest.mark.unit
class TestUserProfileProjectionPolicy:
    def test_upserts_on_provisioned(self) -> None:
        mock_repo = MagicMock()
        projection = UserProfileProjection(repository=mock_repo)
        event = _make_provisioned_event()
        projection.policy(event, MagicMock())
        mock_repo.upsert_full.assert_called_once()
        call_kwargs = mock_repo.upsert_full.call_args
        assert call_kwargs.kwargs["oidc_sub"] == "test-sub"
        assert call_kwargs.kwargs["display_name"] == "Test User"

    def test_provisioned_fallback_to_email_prefix(self) -> None:
        mock_repo = MagicMock()
        projection = UserProfileProjection(repository=mock_repo)
        event = _make_provisioned_event(name=None, email="bob@example.com")
        projection.policy(event, MagicMock())
        call_kwargs = mock_repo.upsert_full.call_args
        assert call_kwargs.kwargs["display_name"] == "bob"

    def test_provisioned_fallback_to_user(self) -> None:
        mock_repo = MagicMock()
        projection = UserProfileProjection(repository=mock_repo)
        event = _make_provisioned_event(name=None, email="")
        projection.policy(event, MagicMock())
        call_kwargs = mock_repo.upsert_full.call_args
        assert call_kwargs.kwargs["display_name"] == "User"

    def test_updates_display_name_on_profile_updated(self) -> None:
        mock_repo = MagicMock()
        projection = UserProfileProjection(repository=mock_repo)
        event = _make_profile_updated_event(display_name="Updated Name")
        projection.policy(event, MagicMock())
        mock_repo.update_display_name.assert_called_once()

    def test_updates_preferences_on_preferences_updated(self) -> None:
        mock_repo = MagicMock()
        projection = UserProfileProjection(repository=mock_repo)
        event = _make_preferences_updated_event(preferences={"lang": "en"})
        projection.policy(event, MagicMock())
        mock_repo.update_preferences.assert_called_once()

    def test_ignores_unknown_events(self) -> None:
        mock_repo = MagicMock()
        projection = UserProfileProjection(repository=mock_repo)
        event = MagicMock()
        event.__class__.__name__ = "SomeOtherEvent"
        projection.policy(event, MagicMock())
        mock_repo.upsert_full.assert_not_called()
        mock_repo.update_display_name.assert_not_called()
        mock_repo.update_preferences.assert_not_called()
