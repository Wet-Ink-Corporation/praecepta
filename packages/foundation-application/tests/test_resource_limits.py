"""Unit tests for praecepta.foundation.application.resource_limits."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.foundation.application.resource_limits import (
    ResourceLimitResult,
    ResourceLimitService,
)
from praecepta.foundation.domain.config_value_objects import ConfigKey
from praecepta.foundation.domain.exceptions import ResourceLimitExceededError


class _TestConfigKey(ConfigKey):
    """Test-only config keys for unit tests."""

    MAX_WIDGETS = "limits.max_widgets"


def _make_config_service(limit_value: int = 100) -> MagicMock:
    """Create a mock TenantConfigService that returns a fixed limit."""
    svc = MagicMock()
    svc.resolve_limit = MagicMock(return_value=limit_value)
    return svc


class TestResourceLimitResult:
    @pytest.mark.unit
    def test_construction(self) -> None:
        r = ResourceLimitResult(limit=100, remaining=50)
        assert r.limit == 100
        assert r.remaining == 50

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        r = ResourceLimitResult(limit=100, remaining=50)
        with pytest.raises(AttributeError):
            r.limit = 200  # type: ignore[misc]


class TestResourceLimitService:
    @pytest.mark.unit
    def test_check_limit_passes_under_limit(self) -> None:
        config = _make_config_service(limit_value=100)
        resource_map = {"widgets": _TestConfigKey.MAX_WIDGETS}
        svc = ResourceLimitService(config, resource_key_map=resource_map)

        result = svc.check_limit("acme", "widgets", current_count=50)
        assert result.limit == 100
        assert result.remaining == 49  # 100 - 50 - 1

    @pytest.mark.unit
    def test_check_limit_raises_when_exceeded(self) -> None:
        config = _make_config_service(limit_value=10)
        resource_map = {"widgets": _TestConfigKey.MAX_WIDGETS}
        svc = ResourceLimitService(config, resource_key_map=resource_map)

        with pytest.raises(ResourceLimitExceededError) as exc_info:
            svc.check_limit("acme", "widgets", current_count=10)
        assert exc_info.value.resource == "widgets"
        assert exc_info.value.limit == 10

    @pytest.mark.unit
    def test_check_limit_unknown_resource_returns_unlimited(self) -> None:
        config = _make_config_service()
        svc = ResourceLimitService(config, resource_key_map={})

        result = svc.check_limit("acme", "unknown_resource", current_count=5)
        assert result.limit == 2**31 - 1

    @pytest.mark.unit
    def test_check_limit_with_custom_increment(self) -> None:
        config = _make_config_service(limit_value=100)
        resource_map = {"widgets": _TestConfigKey.MAX_WIDGETS}
        svc = ResourceLimitService(config, resource_key_map=resource_map)

        result = svc.check_limit("acme", "widgets", current_count=90, increment=5)
        assert result.remaining == 5  # 100 - 90 - 5

    @pytest.mark.unit
    def test_check_limit_increment_exceeds(self) -> None:
        config = _make_config_service(limit_value=100)
        resource_map = {"widgets": _TestConfigKey.MAX_WIDGETS}
        svc = ResourceLimitService(config, resource_key_map=resource_map)

        with pytest.raises(ResourceLimitExceededError):
            svc.check_limit("acme", "widgets", current_count=96, increment=5)

    @pytest.mark.unit
    def test_injectable_resource_map(self) -> None:
        """Resource map is injectable via constructor, not hard-coded."""
        config = _make_config_service(limit_value=50)
        custom_map = {"gadgets": _TestConfigKey.MAX_WIDGETS}
        svc = ResourceLimitService(config, resource_key_map=custom_map)

        result = svc.check_limit("acme", "gadgets", current_count=10)
        assert result.limit == 50
        config.resolve_limit.assert_called_once_with("acme", _TestConfigKey.MAX_WIDGETS)

    @pytest.mark.unit
    def test_empty_resource_map_default(self) -> None:
        """Default resource map is empty, so all resources are unlimited."""
        config = _make_config_service()
        svc = ResourceLimitService(config)

        result = svc.check_limit("acme", "anything", current_count=0)
        assert result.limit == 2**31 - 1
