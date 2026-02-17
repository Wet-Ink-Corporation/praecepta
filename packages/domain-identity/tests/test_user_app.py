"""Unit tests for UserApplication."""

from __future__ import annotations

import pytest

from praecepta.domain.identity.user import User
from praecepta.domain.identity.user_app import UserApplication


@pytest.mark.unit
class TestUserApplication:
    """UserApplication configuration and instantiation."""

    def test_snapshotting_interval_configured(self) -> None:
        assert UserApplication.snapshotting_intervals == {User: 50}

    def test_can_instantiate(self) -> None:
        app = UserApplication()
        assert app is not None

    def test_save_and_retrieve(self) -> None:
        app = UserApplication()
        user = User(
            oidc_sub="test-sub-123",
            tenant_id="acme-corp",
            email="test@example.com",
            name="Test User",
        )
        app.save(user)
        retrieved = app.repository.get(user.id)
        assert retrieved.oidc_sub == "test-sub-123"
        assert retrieved.tenant_id == "acme-corp"
        assert retrieved.version == 1
