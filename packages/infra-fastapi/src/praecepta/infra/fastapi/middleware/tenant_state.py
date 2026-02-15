"""Middleware to enforce tenant suspension across all tenant-scoped endpoints.

Checks tenant lifecycle state before processing requests. Suspended and
decommissioned tenants receive 403 Forbidden with RFC 7807 problem detail.

Design decisions:
- Fail-open on cache miss: on first request for a tenant (cache empty),
  the middleware allows the request through.
- Admin endpoint exclusion: configurable path prefixes are excluded from
  enforcement so admin operations work on suspended tenants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from praecepta.foundation.application import MiddlewareContribution
from praecepta.foundation.domain import TenantStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

# Default paths excluded from tenant state enforcement.
DEFAULT_EXCLUDED_PREFIXES: tuple[str, ...] = (
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/scalar",
    "/favicon",
)

# HTTP status codes and error body for blocked tenants
_PROBLEM_MEDIA_TYPE = "application/problem+json"


class TenantStateMiddleware(BaseHTTPMiddleware):
    """Enforces tenant suspension by blocking API requests.

    Request flow:
    1. Extract tenant slug from X-Tenant-ID header
    2. Skip check if path is excluded (admin, health, docs)
    3. Skip check if no tenant slug (unauthenticated or internal requests)
    4. Look up tenant state via the provided checker callable
    5. If checker returns None (cache miss): fail-open (allow request through)
    6. If SUSPENDED or DECOMMISSIONED: return 403 Forbidden
    7. Otherwise: proceed to next handler

    Fail-open rationale:
    On first request for a tenant (cache empty), the middleware allows the
    request through. The cache is populated when suspend/reactivate/decommission
    handlers call set_status(). A TTL ensures eventual eviction of stale entries.

    Args:
        app: The ASGI application.
        excluded_prefixes: Tuple of URL path prefixes to skip. Defaults to
            common infra paths (health, docs, etc.).
        tenant_status_checker: A callable that accepts a tenant slug string
            and returns the tenant status string (e.g. "ACTIVE", "SUSPENDED")
            or None on cache miss. If not provided, the middleware will
            always fail-open (no enforcement).
    """

    def __init__(
        self,
        app: Any,
        excluded_prefixes: tuple[str, ...] | None = None,
        tenant_status_checker: Callable[[str], str | None] | None = None,
    ) -> None:
        super().__init__(app)
        self._excluded_prefixes = (
            excluded_prefixes if excluded_prefixes is not None else DEFAULT_EXCLUDED_PREFIXES
        )
        self._check_status = tenant_status_checker

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Check tenant state and block if suspended/decommissioned.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/handler in the chain.

        Returns:
            403 JSONResponse if tenant is blocked, otherwise the response
            from the downstream handler.
        """
        # 1. Skip excluded paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._excluded_prefixes):
            return await call_next(request)

        # 2. Get tenant slug from header
        tenant_slug = request.headers.get("X-Tenant-ID", "")
        if not tenant_slug:
            return await call_next(request)

        # 3. If no checker configured, fail-open
        if self._check_status is None:
            return await call_next(request)

        # 4. Check tenant state
        status = self._check_status(tenant_slug)

        # 5. Fail-open on cache miss (None means no cached state)
        if status is None:
            return await call_next(request)

        # 6. Block suspended or decommissioned tenants
        if status in (TenantStatus.SUSPENDED.value, TenantStatus.DECOMMISSIONED.value):
            return JSONResponse(
                status_code=403,
                content={
                    "type": "/errors/tenant-suspended",
                    "title": "Tenant Suspended",
                    "status": 403,
                    "detail": (
                        f"Tenant '{tenant_slug}' is {status.lower()}. "
                        "Contact your platform administrator."
                    ),
                    "error_code": "TENANT_SUSPENDED",
                },
                media_type=_PROBLEM_MEDIA_TYPE,
            )

        # 7. Allow request through
        return await call_next(request)


# Module-level contribution for auto-discovery via entry points.
contribution = MiddlewareContribution(
    middleware_class=TenantStateMiddleware,
    priority=250,  # Context band (200-299)
)
