"""Three-level policy binding resolution service.

Resolution chain:
  Level 1: Explicit block-level policy (from block properties)
  Level 2: Tenant default policy (from tenant configuration)
  Level 3: System default policy (from SYSTEM_DEFAULTS constants)

Caching: Tenant defaults cached via TenantConfigService (L1/L2).
Block-level policies are NOT cached (deferred to future implementation).
System defaults are static in-memory constants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from praecepta.foundation.domain.config_defaults import SYSTEM_DEFAULTS
from praecepta.foundation.domain.exceptions import ValidationError

if TYPE_CHECKING:
    from praecepta.foundation.application.config_service import TenantConfigService
    from praecepta.foundation.domain.config_value_objects import ConfigKey
    from praecepta.foundation.domain.policy_types import PolicyType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyResolution:
    """Result of a policy resolution lookup.

    Attributes:
        value: Resolved policy value as string
            (e.g., "ExponentialDecay", "90").
        source: Which level of the resolution chain provided the value.
        policy_type: The PolicyType that was resolved.
    """

    value: str
    source: Literal["explicit", "tenant_default", "system_default"]
    policy_type: str


class PolicyBindingService:
    """Resolves policy bindings via three-level chain.

    Level 1: Explicit block policy (block_id required, returns None for now)
    Level 2: Tenant default policy (from TenantConfigService)
    Level 3: System default policy (from SYSTEM_DEFAULTS)

    The policy type registry is injectable: callers provide a mapping from
    PolicyType enum values to ConfigKey instances. This allows each
    application to define its own domain-specific policy types.

    Args:
        config_service: TenantConfigService for reading tenant config.
        policy_type_to_config_key: Mapping from PolicyType to ConfigKey.
            If not provided, defaults to an empty mapping. Applications
            should provide their own domain-specific mapping.
    """

    def __init__(
        self,
        config_service: TenantConfigService,
        policy_type_to_config_key: dict[PolicyType, ConfigKey] | None = None,
    ) -> None:
        self._config = config_service
        self._policy_type_to_config_key: dict[PolicyType, ConfigKey] = (
            policy_type_to_config_key if policy_type_to_config_key is not None else {}
        )

    def resolve_policy(
        self,
        tenant_id: str,
        policy_type: str,
        block_id: str | None = None,
    ) -> PolicyResolution:
        """Resolve policy via three-level chain.

        Args:
            tenant_id: Tenant slug identifier.
            policy_type: Policy type string (must match a registered
                PolicyType in the policy_type_to_config_key mapping).
            block_id: Optional block ID for explicit policy lookup.

        Returns:
            PolicyResolution with value and resolution source.

        Raises:
            ValidationError: If policy_type is not registered in the
                policy_type_to_config_key mapping.
        """
        # Look up policy_type string in the registered mapping
        pt: PolicyType | None = None
        config_key: ConfigKey | None = None
        for registered_pt, registered_ck in self._policy_type_to_config_key.items():
            if registered_pt.value == policy_type:
                pt = registered_pt
                config_key = registered_ck
                break

        if pt is None or config_key is None:
            supported = [t.value for t in self._policy_type_to_config_key]
            raise ValidationError(
                "policy_type",
                f"Unsupported policy type: {policy_type!r}. Supported: {supported}",
            )

        # Level 1: Explicit block policy
        if block_id is not None:
            block_policy = self._get_block_policy(block_id, pt)
            if block_policy is not None:
                logger.debug(
                    "policy_resolved",
                    extra={
                        "tenant_id": tenant_id,
                        "policy_type": policy_type,
                        "source": "explicit",
                        "block_id": block_id,
                    },
                )
                return PolicyResolution(
                    value=block_policy,
                    source="explicit",
                    policy_type=policy_type,
                )

        # Level 2: Tenant default
        config_entry = self._config.get_config(tenant_id, config_key.value)

        if config_entry is not None and config_entry["source"] == "tenant":
            raw_value = config_entry["value"]
            resolved_value = str(raw_value.get("value", ""))
            logger.debug(
                "policy_resolved",
                extra={
                    "tenant_id": tenant_id,
                    "policy_type": policy_type,
                    "source": "tenant_default",
                    "value": resolved_value,
                },
            )
            return PolicyResolution(
                value=resolved_value,
                source="tenant_default",
                policy_type=policy_type,
            )

        # Level 3: System default
        system_default = SYSTEM_DEFAULTS.get(config_key.value)
        default_value = ""
        if system_default is not None:
            default_value = str(system_default.value)

        logger.debug(
            "policy_resolved",
            extra={
                "tenant_id": tenant_id,
                "policy_type": policy_type,
                "source": "system_default",
                "value": default_value,
            },
        )
        return PolicyResolution(
            value=default_value,
            source="system_default",
            policy_type=policy_type,
        )

    def get_all_bindings(
        self,
        tenant_id: str,
    ) -> list[PolicyResolution]:
        """Resolve all policy bindings for a tenant.

        Iterates over all registered policy types and resolves each.

        Args:
            tenant_id: Tenant slug identifier.

        Returns:
            List of PolicyResolution for each registered policy type.
        """
        return [self.resolve_policy(tenant_id, pt.value) for pt in self._policy_type_to_config_key]

    def _get_block_policy(
        self,
        block_id: str,
        policy_type: PolicyType,
    ) -> str | None:
        """Get explicit block-level policy.

        Stub: returns None for all lookups. Block-level policy storage
        is deferred to future implementation. This method signature is
        designed for future extension when block properties include
        policy fields.

        Args:
            block_id: Block identifier.
            policy_type: Policy type being resolved.

        Returns:
            None (always). Future: policy value string if block
            has explicit policy.
        """
        return None
