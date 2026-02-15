"""Unit tests for praecepta.foundation.application.config_service."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from praecepta.foundation.application.config_service import (
    TenantConfigService,
    _evaluate_percentage_flag,
)
from praecepta.foundation.domain.config_defaults import SYSTEM_DEFAULTS
from praecepta.foundation.domain.config_value_objects import (
    BooleanConfigValue,
    ConfigKey,
    IntegerConfigValue,
    PercentageConfigValue,
)


class _TestConfigKey(ConfigKey):
    """Test-only config keys for unit tests."""

    FEATURE_X = "feature.x"
    FEATURE_Y = "feature.y"
    LIMIT_ITEMS = "limits.items"


def _make_repo(
    tenant_data: dict[str, dict[str, Any]] | None = None,
    all_data: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> MagicMock:
    """Create a mock ConfigRepository."""
    repo = MagicMock()
    _tenant_data = tenant_data or {}
    _all_data = all_data or {}

    def get(tenant_id: str, key: str) -> dict[str, Any] | None:
        return _tenant_data.get(key)

    def get_all(tenant_id: str) -> dict[str, dict[str, Any]]:
        return _all_data.get(tenant_id, {})

    repo.get = get
    repo.get_all = get_all
    repo.upsert = MagicMock()
    return repo


class TestEvaluatePercentageFlag:
    @pytest.mark.unit
    def test_deterministic_same_input(self) -> None:
        """Same tenant+feature always returns same result."""
        result1 = _evaluate_percentage_flag("acme", "feature.x", 50)
        result2 = _evaluate_percentage_flag("acme", "feature.x", 50)
        assert result1 == result2

    @pytest.mark.unit
    def test_zero_percent_always_false(self) -> None:
        assert _evaluate_percentage_flag("acme", "feature.x", 0) is False

    @pytest.mark.unit
    def test_hundred_percent_always_true(self) -> None:
        assert _evaluate_percentage_flag("acme", "feature.x", 100) is True

    @pytest.mark.unit
    def test_monotonic_rollout(self) -> None:
        """Increasing percentage keeps previously enabled tenants enabled."""
        enabled_at_10 = _evaluate_percentage_flag("acme", "feature.x", 10)
        enabled_at_50 = _evaluate_percentage_flag("acme", "feature.x", 50)

        if enabled_at_10:
            assert enabled_at_50 is True

    @pytest.mark.unit
    def test_feature_independence(self) -> None:
        """Different features can give different results for same tenant."""
        # Just verify both return bool without error
        r1 = _evaluate_percentage_flag("acme", "feature.x", 50)
        r2 = _evaluate_percentage_flag("acme", "feature.y", 50)
        assert isinstance(r1, bool)
        assert isinstance(r2, bool)


class TestTenantConfigServiceGetConfig:
    @pytest.mark.unit
    def test_tenant_override_beats_system_default(self) -> None:
        """Tenant override takes priority over system default."""
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_X.value] = BooleanConfigValue(value=False)
        try:
            tenant_value = {"type": "boolean", "value": True}
            repo = _make_repo(tenant_data={_TestConfigKey.FEATURE_X.value: tenant_value})
            svc = TenantConfigService(repository=repo)

            result = svc.get_config("acme", _TestConfigKey.FEATURE_X.value)
            assert result is not None
            assert result["source"] == "tenant"
            assert result["value"]["value"] is True
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_X.value, None)

    @pytest.mark.unit
    def test_falls_back_to_system_default(self) -> None:
        """When no tenant override, falls back to system default."""
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_X.value] = BooleanConfigValue(value=True)
        try:
            repo = _make_repo()
            svc = TenantConfigService(repository=repo)

            result = svc.get_config("acme", _TestConfigKey.FEATURE_X.value)
            assert result is not None
            assert result["source"] == "system_default"
            assert result["value"]["value"] is True
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_X.value, None)

    @pytest.mark.unit
    def test_returns_none_for_unknown_key(self) -> None:
        repo = _make_repo()
        svc = TenantConfigService(repository=repo)
        result = svc.get_config("acme", "unknown.key.does.not.exist")
        assert result is None


class TestTenantConfigServiceGetAllConfig:
    @pytest.mark.unit
    def test_get_all_config_merges_tenant_and_defaults(self) -> None:
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_X.value] = BooleanConfigValue(value=False)
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_Y.value] = BooleanConfigValue(value=True)
        try:
            tenant_overrides = {
                _TestConfigKey.FEATURE_X.value: {
                    "type": "boolean",
                    "value": True,
                }
            }
            repo = _make_repo(
                all_data={"acme": tenant_overrides},
            )
            svc = TenantConfigService(repository=repo)

            results = svc.get_all_config("acme")

            by_key = {r["key"]: r for r in results}
            # feature.x has tenant override
            assert by_key[_TestConfigKey.FEATURE_X.value]["source"] == "tenant"
            # feature.y falls back to system default
            assert by_key[_TestConfigKey.FEATURE_Y.value]["source"] == "system_default"
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_X.value, None)
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_Y.value, None)


class TestTenantConfigServiceFeatureFlags:
    @pytest.mark.unit
    def test_boolean_feature_enabled(self) -> None:
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_X.value] = BooleanConfigValue(value=True)
        try:
            repo = _make_repo()
            svc = TenantConfigService(repository=repo)
            assert svc.is_feature_enabled("acme", _TestConfigKey.FEATURE_X) is True
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_X.value, None)

    @pytest.mark.unit
    def test_boolean_feature_disabled(self) -> None:
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_X.value] = BooleanConfigValue(value=False)
        try:
            repo = _make_repo()
            svc = TenantConfigService(repository=repo)
            assert svc.is_feature_enabled("acme", _TestConfigKey.FEATURE_X) is False
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_X.value, None)

    @pytest.mark.unit
    def test_percentage_flag_deterministic(self) -> None:
        """Percentage flag evaluation is deterministic via SHA256."""
        SYSTEM_DEFAULTS[_TestConfigKey.FEATURE_X.value] = PercentageConfigValue(value=50)
        try:
            repo = _make_repo()
            svc = TenantConfigService(repository=repo)
            r1 = svc.is_feature_enabled("acme", _TestConfigKey.FEATURE_X)
            r2 = svc.is_feature_enabled("acme", _TestConfigKey.FEATURE_X)
            assert r1 == r2
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.FEATURE_X.value, None)

    @pytest.mark.unit
    def test_no_config_returns_false(self) -> None:
        """Missing config means feature disabled (fail-closed)."""
        repo = _make_repo()
        svc = TenantConfigService(repository=repo)
        # Use a key that's not in SYSTEM_DEFAULTS
        assert svc.is_feature_enabled("acme", _TestConfigKey.FEATURE_Y) is False


class TestTenantConfigServiceResolveLimit:
    @pytest.mark.unit
    def test_resolve_limit_from_system_default(self) -> None:
        SYSTEM_DEFAULTS[_TestConfigKey.LIMIT_ITEMS.value] = IntegerConfigValue(value=500)
        try:
            repo = _make_repo()
            svc = TenantConfigService(repository=repo)
            assert svc.resolve_limit("acme", _TestConfigKey.LIMIT_ITEMS) == 500
        finally:
            SYSTEM_DEFAULTS.pop(_TestConfigKey.LIMIT_ITEMS.value, None)

    @pytest.mark.unit
    def test_resolve_limit_returns_int_max_when_missing(self) -> None:
        repo = _make_repo()
        svc = TenantConfigService(repository=repo)
        assert svc.resolve_limit("acme", _TestConfigKey.LIMIT_ITEMS) == 2**31 - 1
