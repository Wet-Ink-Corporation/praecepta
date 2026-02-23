"""Unit tests for TenantConfigProjection with mock repo/cache."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.domain.tenancy.infrastructure.projections.tenant_config import (
    TenantConfigProjection,
)


def _make_config_updated_event(
    *,
    tenant_id: str = "acme-corp",
    config_key: str = "feature.dark_mode",
    config_value: dict | None = None,  # type: ignore[type-arg]
    updated_by: str = "admin",
) -> MagicMock:
    """Create a mock ConfigUpdated event."""
    event = MagicMock()
    event.__class__ = type("ConfigUpdated", (), {})
    event.__class__.__name__ = "ConfigUpdated"
    event.tenant_id = tenant_id
    event.config_key = config_key
    event.config_value = config_value or {"type": "boolean", "value": True}
    event.updated_by = updated_by
    return event


@pytest.mark.unit
class TestTenantConfigProjectionUpstream:
    """Upstream application declaration."""

    def test_declares_upstream_application(self) -> None:
        from praecepta.domain.tenancy.tenant_app import TenantApplication

        assert TenantConfigProjection.upstream_application is TenantApplication


@pytest.mark.unit
class TestTenantConfigProjectionTopics:
    """Topic configuration."""

    def test_subscribes_to_config_updated(self) -> None:
        assert len(TenantConfigProjection.topics) == 1
        assert "Tenant.ConfigUpdated" in TenantConfigProjection.topics[0]


@pytest.mark.unit
class TestTenantConfigProjectionPolicy:
    """Event handling via policy method."""

    def test_upserts_on_config_updated(self) -> None:
        mock_repo = MagicMock()
        projection = TenantConfigProjection(repository=mock_repo)
        event = _make_config_updated_event()
        mock_processing = MagicMock()

        projection.policy(event, mock_processing)

        mock_repo.upsert.assert_called_once_with(
            tenant_id="acme-corp",
            key="feature.dark_mode",
            value={"type": "boolean", "value": True},
            updated_by="admin",
        )

    def test_invalidates_cache_on_config_updated(self) -> None:
        mock_repo = MagicMock()
        mock_cache = MagicMock()
        mock_cache.cache_key.return_value = "acme-corp:feature.dark_mode"
        projection = TenantConfigProjection(repository=mock_repo, cache=mock_cache)
        event = _make_config_updated_event()

        projection.policy(event, MagicMock())

        mock_cache.cache_key.assert_called_once_with("acme-corp", "feature.dark_mode")
        mock_cache.delete.assert_called_once_with("acme-corp:feature.dark_mode")

    def test_no_cache_invalidation_when_cache_is_none(self) -> None:
        mock_repo = MagicMock()
        projection = TenantConfigProjection(repository=mock_repo, cache=None)
        event = _make_config_updated_event()

        # Should not raise
        projection.policy(event, MagicMock())
        mock_repo.upsert.assert_called_once()

    def test_ignores_non_config_updated_events(self) -> None:
        mock_repo = MagicMock()
        projection = TenantConfigProjection(repository=mock_repo)
        event = MagicMock()
        event.__class__.__name__ = "Activated"

        projection.policy(event, MagicMock())
        mock_repo.upsert.assert_not_called()
