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

import json
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import MiddlewareContribution
from praecepta.foundation.domain import TenantStatus

if TYPE_CHECKING:
    from collections.abc import Callable

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


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str:
    """Extract a header value from raw ASGI headers."""
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return ""


class TenantStateMiddleware:
    """Enforces tenant suspension by blocking API requests.

    Request flow:
    1. Extract tenant slug from X-Tenant-ID header
    2. Skip check if path is excluded (admin, health, docs)
    3. Skip check if no tenant slug (unauthenticated or internal requests)
    4. Look up tenant state via the provided checker callable
    5. If checker returns None (cache miss): fail-open (allow request through)
    6. If SUSPENDED or DECOMMISSIONED: return 403 Forbidden
    7. Otherwise: proceed to next handler

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
        self.app = app
        self._excluded_prefixes = (
            excluded_prefixes if excluded_prefixes is not None else DEFAULT_EXCLUDED_PREFIXES
        )
        self._check_status = tenant_status_checker

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # 1. Skip excluded paths
        if any(path.startswith(prefix) for prefix in self._excluded_prefixes):
            await self.app(scope, receive, send)
            return

        # 2. Get tenant slug from header
        headers = scope.get("headers", [])
        tenant_slug = _extract_header(headers, b"x-tenant-id")
        if not tenant_slug:
            await self.app(scope, receive, send)
            return

        # 3. If no checker configured, fail-open
        if self._check_status is None:
            await self.app(scope, receive, send)
            return

        # 4. Check tenant state
        status = self._check_status(tenant_slug)

        # 5. Fail-open on cache miss
        if status is None:
            await self.app(scope, receive, send)
            return

        # 6. Block suspended or decommissioned tenants
        if status in (TenantStatus.SUSPENDED.value, TenantStatus.DECOMMISSIONED.value):
            body_content = {
                "type": "/errors/tenant-suspended",
                "title": "Tenant Suspended",
                "status": 403,
                "detail": (
                    f"Tenant '{tenant_slug}' is {status.lower()}. "
                    "Contact your platform administrator."
                ),
                "error_code": "TENANT_SUSPENDED",
            }
            body_bytes = json.dumps(body_content).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", _PROBLEM_MEDIA_TYPE.encode("latin-1")),
                        (b"content-length", str(len(body_bytes)).encode("latin-1")),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body_bytes,
                }
            )
            return

        # 7. Allow request through
        await self.app(scope, receive, send)


# Module-level contribution for auto-discovery via entry points.
contribution = MiddlewareContribution(
    middleware_class=TenantStateMiddleware,
    priority=250,  # Context band (200-299)
)
