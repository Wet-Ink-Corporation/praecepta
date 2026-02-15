"""Unit tests for praecepta.foundation.application.policy_binding."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from praecepta.foundation.application.policy_binding import (
    PolicyBindingService,
    PolicyResolution,
)
from praecepta.foundation.domain.config_defaults import SYSTEM_DEFAULTS
from praecepta.foundation.domain.config_value_objects import (
    ConfigKey,
    EnumConfigValue,
)
from praecepta.foundation.domain.exceptions import ValidationError
from praecepta.foundation.domain.policy_types import PolicyType


class _TestPolicyType(PolicyType):
    """Test-only policy types."""

    DECAY = "decay_strategy"
    RETENTION = "retention_period"


class _TestConfigKey(ConfigKey):
    """Test-only config keys."""

    DEFAULT_DECAY = "policy.default_decay_strategy"
    DEFAULT_RETENTION = "policy.default_retention_days"


_TEST_POLICY_MAP: dict[PolicyType, ConfigKey] = {
    _TestPolicyType.DECAY: _TestConfigKey.DEFAULT_DECAY,
    _TestPolicyType.RETENTION: _TestConfigKey.DEFAULT_RETENTION,
}


def _make_config_service(
    tenant_configs: dict[str, dict[str, Any]] | None = None,
) -> MagicMock:
    """Create mock TenantConfigService."""
    svc = MagicMock()
    _configs = tenant_configs or {}

    def get_config(tenant_id: str, key: str) -> dict[str, Any] | None:
        return _configs.get(key)

    svc.get_config = get_config
    return svc


class TestPolicyResolution:
    @pytest.mark.unit
    def test_construction(self) -> None:
        r = PolicyResolution(
            value="ExponentialDecay",
            source="tenant_default",
            policy_type="decay_strategy",
        )
        assert r.value == "ExponentialDecay"
        assert r.source == "tenant_default"
        assert r.policy_type == "decay_strategy"

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        r = PolicyResolution(value="v", source="explicit", policy_type="t")
        with pytest.raises(AttributeError):
            r.value = "other"  # type: ignore[misc]


class TestPolicyBindingServiceResolution:
    @pytest.mark.unit
    def test_tenant_default_beats_system_default(self) -> None:
        """Level 2 (tenant default) takes priority over Level 3 (system)."""
        SYSTEM_DEFAULTS[_TestConfigKey.DEFAULT_DECAY.value] = EnumConfigValue(
            value="LinearDecay",
            allowed_values=["LinearDecay", "ExponentialDecay"],
        )
        try:
            tenant_config = {
                _TestConfigKey.DEFAULT_DECAY.value: {
                    "key": _TestConfigKey.DEFAULT_DECAY.value,
                    "value": {
                        "type": "enum",
                        "value": "ExponentialDecay",
                        "allowed_values": [
                            "LinearDecay",
                            "ExponentialDecay",
                        ],
                    },
                    "source": "tenant",
                }
            }
            config = _make_config_service(tenant_configs=tenant_config)
            svc = PolicyBindingService(config, policy_type_to_config_key=_TEST_POLICY_MAP)

            result = svc.resolve_policy("acme", "decay_strategy")
            assert result.value == "ExponentialDecay"
            assert result.source == "tenant_default"
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.DEFAULT_DECAY.value, None)

    @pytest.mark.unit
    def test_falls_back_to_system_default(self) -> None:
        """Level 3 (system default) when no tenant override."""
        SYSTEM_DEFAULTS[_TestConfigKey.DEFAULT_DECAY.value] = EnumConfigValue(
            value="LinearDecay",
            allowed_values=["LinearDecay", "ExponentialDecay"],
        )
        try:
            config = _make_config_service()
            svc = PolicyBindingService(config, policy_type_to_config_key=_TEST_POLICY_MAP)

            result = svc.resolve_policy("acme", "decay_strategy")
            assert result.value == "LinearDecay"
            assert result.source == "system_default"
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.DEFAULT_DECAY.value, None)

    @pytest.mark.unit
    def test_system_default_returns_empty_when_missing(self) -> None:
        """No system default configured yields empty string."""
        config = _make_config_service()
        svc = PolicyBindingService(config, policy_type_to_config_key=_TEST_POLICY_MAP)

        result = svc.resolve_policy("acme", "decay_strategy")
        assert result.value == ""
        assert result.source == "system_default"

    @pytest.mark.unit
    def test_unsupported_policy_type_raises(self) -> None:
        config = _make_config_service()
        svc = PolicyBindingService(config, policy_type_to_config_key=_TEST_POLICY_MAP)

        with pytest.raises(ValidationError):
            svc.resolve_policy("acme", "nonexistent_policy_type")

    @pytest.mark.unit
    def test_injectable_policy_type_registry(self) -> None:
        """Policy type registry is injectable, not hard-coded."""
        SYSTEM_DEFAULTS[_TestConfigKey.DEFAULT_RETENTION.value] = EnumConfigValue(
            value="90",
            allowed_values=["30", "60", "90"],
        )
        try:
            custom_map: dict[PolicyType, ConfigKey] = {
                _TestPolicyType.RETENTION: _TestConfigKey.DEFAULT_RETENTION,
            }
            config = _make_config_service()
            svc = PolicyBindingService(config, policy_type_to_config_key=custom_map)

            result = svc.resolve_policy("acme", "retention_period")
            assert result.value == "90"
            assert result.source == "system_default"
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.DEFAULT_RETENTION.value, None)

    @pytest.mark.unit
    def test_no_config_key_mapping_raises(self) -> None:
        """Policy type with no registered mapping raises ValidationError."""
        config = _make_config_service()
        svc = PolicyBindingService(config, policy_type_to_config_key={})

        with pytest.raises(ValidationError, match="Unsupported policy type"):
            svc.resolve_policy("acme", "decay_strategy")


class TestPolicyBindingServiceGetAllBindings:
    @pytest.mark.unit
    def test_get_all_bindings(self) -> None:
        """Returns resolutions for all registered policy types."""
        config = _make_config_service()
        svc = PolicyBindingService(config, policy_type_to_config_key=_TEST_POLICY_MAP)

        results = svc.get_all_bindings("acme")
        policy_types_returned = {r.policy_type for r in results}
        assert "decay_strategy" in policy_types_returned
        assert "retention_period" in policy_types_returned
        assert len(results) == 2
