"""Resource limit enforcement service.

Resolves configured limits for tenants and validates that operations
would not exceed capacity. Used by endpoint-level dependencies to
enforce limits at request boundaries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from praecepta.foundation.domain.exceptions import ResourceLimitExceededError

if TYPE_CHECKING:
    from praecepta.foundation.application.config_service import TenantConfigService
    from praecepta.foundation.domain.config_value_objects import ConfigKey

logger = logging.getLogger(__name__)

_INT_MAX = 2**31 - 1


@dataclass(frozen=True)
class ResourceLimitResult:
    """Result of a successful resource limit check.

    Attributes:
        limit: The resolved limit value.
        remaining: Capacity remaining after the operation
            (limit - current - increment).
    """

    limit: int
    remaining: int


class ResourceLimitService:
    """Validates resource limits before command execution.

    Resolution chain for a limit value:
    1. Explicit tenant configuration (via TenantConfigService.resolve_limit)
    2. System default from SYSTEM_DEFAULTS
    3. INT_MAX if no default exists (treated as unlimited)

    The resource-type-to-config-key mapping is injectable, allowing each
    application to define its own resource types and corresponding config
    keys.

    Args:
        config_service: TenantConfigService for resolving limit values.
        resource_key_map: Mapping from resource type strings
            (e.g., "memory_blocks") to ConfigKey instances
            (e.g., ConfigKey.MAX_MEMORY_BLOCKS).
    """

    def __init__(
        self,
        config_service: TenantConfigService,
        resource_key_map: dict[str, ConfigKey] | None = None,
    ) -> None:
        self._config = config_service
        self._resource_key_map: dict[str, ConfigKey] = (
            resource_key_map if resource_key_map is not None else {}
        )

    def check_limit(
        self,
        tenant_id: str,
        resource: str,
        current_count: int,
        increment: int = 1,
    ) -> ResourceLimitResult:
        """Check if operation would exceed resource limit.

        Args:
            tenant_id: Tenant slug identifier.
            resource: Resource type key (e.g., "memory_blocks").
            current_count: Current usage count from projection query.
            increment: Number of resources the operation would add.

        Returns:
            ResourceLimitResult with resolved limit and remaining capacity.

        Raises:
            ResourceLimitExceededError: If current_count + increment > limit.
        """
        config_key = self._resource_key_map.get(resource)
        if config_key is None:
            # Unknown resource type: no limit enforced
            return ResourceLimitResult(
                limit=_INT_MAX,
                remaining=_INT_MAX - current_count,
            )

        limit = self._config.resolve_limit(tenant_id, config_key)

        if current_count + increment > limit:
            logger.warning(
                "resource_limit_exceeded",
                extra={
                    "tenant_id": tenant_id,
                    "resource": resource,
                    "limit": limit,
                    "current": current_count,
                    "attempted_increment": increment,
                },
            )
            raise ResourceLimitExceededError(
                resource=resource,
                limit=limit,
                current=current_count,
            )

        remaining = limit - current_count - increment

        logger.debug(
            "resource_limit_checked",
            extra={
                "tenant_id": tenant_id,
                "resource": resource,
                "limit": limit,
                "remaining": remaining,
            },
        )

        return ResourceLimitResult(limit=limit, remaining=remaining)
