"""Unit tests for User aggregate."""

from __future__ import annotations

from typing import Any

import pytest

from praecepta.domain.identity.user import User


def _new_user(
    *,
    oidc_sub: str = "test-oidc-sub-123",
    tenant_id: str = "acme-corp",
    email: str | None = "user@example.com",
    name: str | None = "Test User",
) -> User:
    """Helper to create a User with sensible defaults."""
    return User(oidc_sub=oidc_sub, tenant_id=tenant_id, email=email, name=name)


@pytest.mark.unit
class TestUserCreation:
    """User aggregate creation from OIDC claims."""

    def test_creates_from_valid_oidc_claims(self) -> None:
        user = User(
            oidc_sub="550e8400-e29b-41d4-a716-446655440000",
            tenant_id="acme-corp",
            email="alice@example.com",
            name="Alice Smith",
        )
        assert user.oidc_sub == "550e8400-e29b-41d4-a716-446655440000"
        assert user.tenant_id == "acme-corp"
        assert user.email == "alice@example.com"
        assert user.display_name == "Alice Smith"
        assert user.preferences == {}

    def test_records_provisioned_event(self) -> None:
        user = _new_user()
        events = user.collect_events()
        assert len(events) >= 1
        event = events[0]
        assert event.__class__.__name__ == "Provisioned"
        assert event.oidc_sub == "test-oidc-sub-123"
        assert event.email == "user@example.com"
        assert event.name == "Test User"
        assert event.tenant_id == "acme-corp"

    def test_stores_oidc_sub_and_tenant_id(self) -> None:
        user = _new_user(
            oidc_sub="auth0|507f1f77bcf86cd799439011",
            tenant_id="test-tenant",
        )
        assert user.oidc_sub == "auth0|507f1f77bcf86cd799439011"
        assert user.tenant_id == "test-tenant"

    def test_derives_display_name_from_name_claim(self) -> None:
        user = _new_user(name="Bob Smith", email="bob@example.com")
        assert user.display_name == "Bob Smith"

    def test_derives_display_name_from_email(self) -> None:
        user = _new_user(email="bob@example.com", name=None)
        assert user.display_name == "bob"

    def test_derives_display_name_fallback(self) -> None:
        user = _new_user(email=None, name=None)
        assert user.display_name == "User"

    def test_initializes_empty_preferences(self) -> None:
        user = _new_user()
        assert user.preferences == {}
        assert isinstance(user.preferences, dict)

    def test_rejects_empty_oidc_sub(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            User(oidc_sub="", tenant_id="acme-corp", email=None, name=None)

    def test_rejects_oversized_oidc_sub(self) -> None:
        oversized = "a" * 256
        with pytest.raises(ValueError, match="too long"):
            User(oidc_sub=oversized, tenant_id="acme-corp", email=None, name=None)

    def test_rejects_missing_tenant_id(self) -> None:
        with pytest.raises(TypeError):
            User(oidc_sub="test-sub", email=None, name=None)  # type: ignore[call-arg]

    def test_allows_empty_email(self) -> None:
        user = _new_user(email="")
        assert user.email == ""

    def test_allows_missing_name(self) -> None:
        user = _new_user(name=None, email="test@example.com")
        assert user.display_name == "test"


@pytest.mark.unit
class TestUserProfileUpdate:
    """User aggregate profile update methods."""

    def test_updates_display_name(self) -> None:
        user = _new_user()
        initial_version = user.version
        user.request_update_display_name("New Display Name")
        events = user.collect_events()
        assert len(events) >= 2
        profile_event = events[-1]
        assert profile_event.__class__.__name__ == "ProfileUpdated"
        assert profile_event.display_name == "New Display Name"
        assert user.version == initial_version + 1

    def test_display_name_update_changes_property(self) -> None:
        user = _new_user(name="Original Name")
        assert user.display_name == "Original Name"
        user.request_update_display_name("Updated Name")
        assert user.display_name == "Updated Name"

    def test_rejects_empty_display_name(self) -> None:
        user = _new_user()
        with pytest.raises(ValueError, match="cannot be empty"):
            user.request_update_display_name("")

    def test_rejects_whitespace_only_display_name(self) -> None:
        user = _new_user()
        with pytest.raises(ValueError, match="cannot be empty"):
            user.request_update_display_name("   ")

    def test_strips_display_name_whitespace(self) -> None:
        user = _new_user()
        user.request_update_display_name("  Padded Name  ")
        assert user.display_name == "Padded Name"

    def test_updates_preferences(self) -> None:
        user = _new_user()
        initial_version = user.version
        test_prefs: dict[str, Any] = {"theme": "dark", "notifications": True}
        user.request_update_preferences(test_prefs)
        events = user.collect_events()
        assert len(events) >= 2
        prefs_event = events[-1]
        assert prefs_event.__class__.__name__ == "PreferencesUpdated"
        assert user.version == initial_version + 1
        assert user.preferences == test_prefs
