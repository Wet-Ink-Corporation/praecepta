"""FastAPI dependency for resource limit enforcement.

Provides ``check_resource_limit()`` factory that creates endpoint
dependencies for enforcing tenant resource limits before command execution.

The resource-type-to-count mapping is injectable: callers provide a
``usage_counter`` callable that returns the current usage count for a
given tenant and resource key.

Usage in endpoint::

    from praecepta.infra.fastapi.dependencies.resource_limits import (
        check_resource_limit,
    )

    @router.post("/", status_code=201)
    def create_block(
        request: CreateBlockRequest,
        limit_result: Annotated[
            ResourceLimitResult,
            Depends(check_resource_limit("memory_blocks")),
        ],
    ) -> CreateBlockResponse:
        # limit_result.limit and limit_result.remaining available for headers
        ...
"""

# NOTE: Do NOT use ``from __future__ import annotations`` here.
# FastAPI dependency injection needs runtime-evaluable type annotations
# on the inner functions (``request: Request``) to resolve parameters.
# PEP 563 deferred evaluation breaks this under pytest --import-mode=importlib.

import logging
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request
from praecepta.foundation.application.context import get_current_tenant_id
from praecepta.foundation.domain import ResourceLimitExceededError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResourceLimitResult:
    """Result of a successful resource limit check.

    Attributes:
        limit: The resolved limit value.
        remaining: Capacity remaining after the operation.
    """

    limit: int
    remaining: int


def check_resource_limit(
    resource: str,
    *,
    usage_counter: Callable[[Request, str, str], int] | None = None,
    limit_resolver: Callable[[Request, str, str], int] | None = None,
    default_limit: int = 2**31 - 1,
) -> Callable[..., ResourceLimitResult]:
    """Create a FastAPI dependency that enforces a resource limit.

    Returns a dependency function that:
    1. Reads tenant_id from request context
    2. Queries current usage count via the provided ``usage_counter``
    3. Resolves the configured limit via ``limit_resolver``
    4. Raises ResourceLimitExceededError (-> 429) if exceeded
    5. Returns ResourceLimitResult with limit/remaining for response headers

    Args:
        resource: Resource type key (e.g., "memory_blocks").
        usage_counter: Callable ``(request, tenant_id, resource) -> int``
            that returns the current usage count. If None, usage is assumed
            to be 0 (no enforcement).
        limit_resolver: Callable ``(request, tenant_id, resource) -> int``
            that resolves the configured limit. If None, ``default_limit``
            is used (effectively unlimited).
        default_limit: Fallback limit when no resolver is provided.

    Returns:
        FastAPI-compatible sync dependency function returning ResourceLimitResult.
    """

    def _check_limit(request: Request) -> ResourceLimitResult:
        """Enforce resource limit for current tenant.

        Returns:
            ResourceLimitResult with limit and remaining capacity.

        Raises:
            ResourceLimitExceededError: If limit would be exceeded.
        """
        tenant_id = get_current_tenant_id()

        # Query current usage count
        if usage_counter is not None:
            current_count = usage_counter(request, tenant_id, resource)
        else:
            current_count = 0

        # Resolve limit
        if limit_resolver is not None:
            limit = limit_resolver(request, tenant_id, resource)
        else:
            limit = default_limit

        # Check limit
        if current_count + 1 > limit:
            logger.warning(
                "resource_limit_exceeded",
                extra={
                    "tenant_id": tenant_id,
                    "resource": resource,
                    "limit": limit,
                    "current": current_count,
                },
            )
            raise ResourceLimitExceededError(
                resource=resource,
                limit=limit,
                current=current_count,
            )

        remaining = limit - current_count - 1

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

    # Store metadata for introspection
    _check_limit.__qualname__ = f"check_resource_limit({resource!r})._check_limit"
    _check_limit._resource = resource  # type: ignore[attr-defined]

    return _check_limit
