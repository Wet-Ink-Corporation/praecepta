"""Tenant configuration resolution service.

Implements the resolution chain: explicit tenant value -> system default.
Read-side service for query endpoints. Write-side handled by aggregate.
Feature flag evaluation via deterministic SHA256 hashing.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any, Protocol

from praecepta.foundation.domain.config_defaults import SYSTEM_DEFAULTS

if TYPE_CHECKING:
    from praecepta.foundation.domain.config_value_objects import ConfigKey

logger = logging.getLogger(__name__)


class ConfigRepository(Protocol):
    """Protocol for configuration storage access.

    Implementations live in infrastructure packages. This protocol defines
    the read-side contract that TenantConfigService depends on.
    """

    def get(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        """Get a single tenant config value."""
        ...

    def get_all(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        """Get all tenant config overrides as {key: value_dict}."""
        ...

    def upsert(
        self,
        tenant_id: str,
        key: str,
        value: dict[str, Any],
        updated_by: str,
    ) -> None:
        """Upsert a config value for a tenant."""
        ...


class ConfigCache(Protocol):
    """Protocol for configuration caching.

    Implementations live in infrastructure packages. This protocol defines
    the caching contract used by TenantConfigService.
    """

    def cache_key(self, tenant_id: str, key: str) -> str:
        """Build a cache key from tenant and config key."""
        ...

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Get a cached value by cache key."""
        ...

    def set(self, cache_key: str, value: dict[str, Any]) -> None:
        """Set a cached value."""
        ...

    def delete(self, cache_key: str) -> None:
        """Delete a cached value."""
        ...


def _evaluate_percentage_flag(
    tenant_id: str,
    feature_key: str,
    rollout_percentage: int,
) -> bool:
    """Deterministic percentage flag evaluation using SHA256 consistent hashing.

    Properties:
    - Same tenant + feature always returns same result (deterministic)
    - Monotonic: increasing percentage from 10% to 20% keeps original 10% enabled
    - Feature independence: different features get independent bucket assignments
      because feature_key is part of the hash input

    Algorithm:
    1. Concatenate "{feature_key}:{tenant_id}" as hash input
    2. SHA256 hash the input (UTF-8 encoded)
    3. Take first 4 bytes as big-endian unsigned integer
    4. Compute bucket = hash_int % 100 (range 0-99)
    5. Return bucket < rollout_percentage

    Args:
        tenant_id: Tenant slug identifier (e.g., "acme-corp").
        feature_key: ConfigKey string value (e.g., "feature.graph_view").
        rollout_percentage: Target rollout percentage (0-100 inclusive).

    Returns:
        True if tenant falls within the rollout percentage bucket.
    """
    hash_input = f"{feature_key}:{tenant_id}"
    hash_bytes = hashlib.sha256(hash_input.encode("utf-8")).digest()
    hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
    bucket = hash_int % 100
    return bucket < rollout_percentage


class TenantConfigService:
    """Configuration resolution with tenant override + system defaults.

    Supports feature flag evaluation via ``is_feature_enabled()`` with
    deterministic percentage-based rollouts.

    Args:
        repository: ConfigRepository for reading projection data.
        cache: Optional ConfigCache for in-memory lookups.
    """

    def __init__(
        self,
        repository: ConfigRepository,
        cache: ConfigCache | None = None,
    ) -> None:
        self._repo = repository
        self._cache = cache

    def set_config(
        self,
        tenant_id: str,
        key: str,
        value: dict[str, Any],
        updated_by: str,
    ) -> None:
        """Write-through: upsert into projection table and invalidate cache.

        Called by the update config endpoint to synchronously materialize
        the config change into the projection table.

        Args:
            tenant_id: Tenant slug identifier.
            key: Configuration key string.
            value: Config value dict (JSONB content).
            updated_by: Operator user ID for audit.
        """
        self._repo.upsert(tenant_id, key, value, updated_by)
        if self._cache is not None:
            ck = self._cache.cache_key(tenant_id, key)
            self._cache.delete(ck)

    def get_config(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        """Resolve a single configuration value.

        Resolution chain: cache -> projection -> system default.

        Args:
            tenant_id: Tenant slug identifier.
            key: Configuration key string (must correspond to a registered
                ConfigKey value or a key in SYSTEM_DEFAULTS).

        Returns:
            Dict with ``key``, ``value``, ``source`` fields.
            Returns None if key has no tenant override and no system default.
        """
        # Check cache first (sync, in-memory)
        if self._cache is not None:
            ck = self._cache.cache_key(tenant_id, key)
            cached = self._cache.get(ck)
            if cached is not None:
                return {
                    "key": key,
                    "value": cached,
                    "source": "tenant",
                }

        # Check tenant override from projection
        tenant_value = self._repo.get(tenant_id, key)
        if tenant_value is not None:
            # Populate cache on read
            if self._cache is not None:
                ck = self._cache.cache_key(tenant_id, key)
                self._cache.set(ck, tenant_value)
            return {
                "key": key,
                "value": tenant_value,
                "source": "tenant",
            }

        # Fall back to system default
        default = SYSTEM_DEFAULTS.get(key)
        if default is not None:
            return {
                "key": key,
                "value": default.model_dump(),
                "source": "system_default",
            }

        return None

    def get_all_config(self, tenant_id: str) -> list[dict[str, Any]]:
        """Resolve all configuration values for a tenant.

        Returns entries for all keys found in system defaults and tenant
        overrides, with tenant overrides taking priority.

        Args:
            tenant_id: Tenant slug identifier.

        Returns:
            List of dicts with ``key``, ``value``, ``source`` fields.
        """
        # Load all tenant overrides
        tenant_overrides = self._repo.get_all(tenant_id)

        # Collect all known keys from system defaults and tenant overrides
        all_keys = sorted(set(SYSTEM_DEFAULTS.keys()) | set(tenant_overrides.keys()))

        result: list[dict[str, Any]] = []
        for key_str in all_keys:
            tenant_value = tenant_overrides.get(key_str)

            if tenant_value is not None:
                result.append(
                    {
                        "key": key_str,
                        "value": tenant_value,
                        "source": "tenant",
                    }
                )
            else:
                default = SYSTEM_DEFAULTS.get(key_str)
                if default is not None:
                    result.append(
                        {
                            "key": key_str,
                            "value": default.model_dump(),
                            "source": "system_default",
                        }
                    )

        return result

    def is_feature_enabled(
        self,
        tenant_id: str,
        feature_key: ConfigKey,
    ) -> bool:
        """Evaluate feature flag for a tenant.

        Resolution:
        1. Call get_config for tenant+key (cache -> projection -> default)
        2. Check the value type discriminator:
           - "boolean": return value directly
           - "percentage": delegate to _evaluate_percentage_flag()
        3. If no config or unexpected type: return False (fail-closed)

        Args:
            tenant_id: Tenant slug identifier.
            feature_key: Feature flag ConfigKey (must be feature.* namespace).

        Returns:
            True if feature is enabled for this tenant, False otherwise.
        """
        config_entry = self.get_config(tenant_id, feature_key.value)

        if config_entry is None:
            return False  # fail-closed: no config means disabled

        config_value = config_entry["value"]
        value_type = config_value.get("type")

        if value_type == "boolean":
            result = bool(config_value.get("value", False))
        elif value_type == "percentage":
            rollout_percentage = config_value.get("value", 0)
            result = _evaluate_percentage_flag(
                tenant_id=tenant_id,
                feature_key=feature_key.value,
                rollout_percentage=rollout_percentage,
            )
        else:
            # Unexpected type for feature flag
            logger.warning(
                "feature_flag_unexpected_type",
                extra={
                    "tenant_id": tenant_id,
                    "feature_key": feature_key.value,
                    "config_type": value_type,
                },
            )
            return False  # fail-closed

        logger.debug(
            "feature_flag_evaluated",
            extra={
                "tenant_id": tenant_id,
                "feature_key": feature_key.value,
                "enabled": result,
                "source": config_entry["source"],
                "config_type": value_type,
            },
        )

        return result

    def resolve_limit(self, tenant_id: str, resource_key: ConfigKey) -> int:
        """Resolve resource limit for a tenant.

        Resolution chain: explicit tenant config -> system default -> INT_MAX.

        Uses the existing get_config() method which checks cache first,
        then projection, then system defaults. This method extracts the
        integer value from the config entry.

        Args:
            tenant_id: Tenant slug identifier.
            resource_key: ConfigKey for the resource limit
                (e.g., a "limits.*" key).

        Returns:
            Integer limit value. Returns 2**31 - 1 if no limit is configured
            anywhere in the resolution chain.
        """
        config_entry = self.get_config(tenant_id, resource_key.value)

        if config_entry is not None:
            config_value = config_entry["value"]
            if config_value.get("type") == "integer":
                return int(config_value.get("value", 2**31 - 1))

        # No config found at all (get_config already checked system defaults)
        return 2**31 - 1

    def resolve_policy(
        self,
        tenant_id: str,
        policy_type: str,
        block_id: str | None = None,
    ) -> str:
        """Resolve policy via three-level chain.

        Convenience method delegating to PolicyBindingService.
        Chain: explicit block -> tenant default -> system default.

        Args:
            tenant_id: Tenant slug identifier.
            policy_type: Policy type string (e.g., "decay_strategy").
            block_id: Optional block ID for explicit policy lookup.

        Returns:
            Resolved policy value as string.
        """
        from praecepta.foundation.application.policy_binding import (
            PolicyBindingService,
        )

        resolver = PolicyBindingService(self)
        resolution = resolver.resolve_policy(tenant_id, policy_type, block_id)
        return resolution.value
