"""Unit tests for UserProvisioningService with mock app and registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.user_provisioning import (
    UserProvisioningService,
)
from praecepta.foundation.domain.exceptions import ConflictError


def _make_mock_app_and_registry() -> tuple[MagicMock, MagicMock]:
    """Create mock app and registry for provisioning tests."""
    app = MagicMock()
    registry = MagicMock()
    return app, registry


@pytest.mark.unit
class TestUserProvisioningFastPath:
    """Fast-path: user already exists."""

    def test_returns_existing_user_id(self) -> None:
        app, registry = _make_mock_app_and_registry()
        existing_id = uuid4()
        registry.lookup.return_value = existing_id
        existing_user = MagicMock()
        existing_user.tenant_id = "acme-corp"
        app.repository.get.return_value = existing_user

        service = UserProvisioningService(app=app, registry=registry)
        result = service.ensure_user_exists(oidc_sub="test-sub", tenant_id="acme-corp")

        assert result == existing_id
        registry.reserve.assert_not_called()
        app.save.assert_not_called()

    def test_raises_conflict_on_cross_tenant(self) -> None:
        app, registry = _make_mock_app_and_registry()
        existing_id = uuid4()
        registry.lookup.return_value = existing_id
        existing_user = MagicMock()
        existing_user.tenant_id = "other-tenant"
        app.repository.get.return_value = existing_user

        service = UserProvisioningService(app=app, registry=registry)
        with pytest.raises(ConflictError, match="different tenant"):
            service.ensure_user_exists(oidc_sub="test-sub", tenant_id="acme-corp")


@pytest.mark.unit
class TestUserProvisioningSlowPath:
    """Slow-path: new user provisioning."""

    def test_creates_and_saves_new_user(self) -> None:
        app, registry = _make_mock_app_and_registry()
        registry.lookup.return_value = None

        service = UserProvisioningService(app=app, registry=registry)
        result = service.ensure_user_exists(
            oidc_sub="new-sub",
            tenant_id="acme-corp",
            email="new@example.com",
            name="New User",
        )

        assert result is not None
        registry.reserve.assert_called_once_with("new-sub", "acme-corp")
        app.save.assert_called_once()
        registry.confirm.assert_called_once()

    def test_releases_reservation_on_save_failure(self) -> None:
        app, registry = _make_mock_app_and_registry()
        registry.lookup.return_value = None
        app.save.side_effect = RuntimeError("event store down")

        service = UserProvisioningService(app=app, registry=registry)
        with pytest.raises(RuntimeError, match="event store down"):
            service.ensure_user_exists(oidc_sub="new-sub", tenant_id="acme-corp")

        registry.release.assert_called_once_with("new-sub")


@pytest.mark.unit
class TestUserProvisioningRaceCondition:
    """Race condition handling on reserve conflict."""

    @patch("praecepta.domain.identity.infrastructure.user_provisioning.time")
    def test_retries_lookup_on_conflict(self, mock_time: MagicMock) -> None:
        app, registry = _make_mock_app_and_registry()
        registry.lookup.return_value = None
        registry.reserve.side_effect = ConflictError("already provisioned")

        # After conflict, retry lookup succeeds on 2nd attempt
        retry_id = uuid4()
        registry.lookup.side_effect = [None, None, retry_id]

        service = UserProvisioningService(app=app, registry=registry)
        result = service.ensure_user_exists(oidc_sub="race-sub", tenant_id="acme-corp")

        assert result == retry_id
        app.save.assert_not_called()
