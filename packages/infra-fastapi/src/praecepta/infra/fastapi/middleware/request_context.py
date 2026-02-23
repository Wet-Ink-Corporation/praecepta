"""Middleware for populating request context from HTTP headers.

Extracts tenant ID, user ID, and correlation ID from request headers
and populates the request context ContextVar for use throughout the
request lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from praecepta.foundation.application import MiddlewareContribution
from praecepta.foundation.application.context import (
    clear_request_context,
    set_request_context,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# Header names
TENANT_ID_HEADER = "X-Tenant-ID"
USER_ID_HEADER = "X-User-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str:
    """Extract a header value from raw ASGI headers."""
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return ""


class RequestContextMiddleware:
    """Pure ASGI middleware that populates request context from HTTP headers.

    Extracts the following headers and makes them available via the
    request context module:
    - X-Tenant-ID: Required tenant identifier
    - X-User-ID: Required authenticated user ID
    - X-Correlation-ID: Optional, generated if not provided

    The context is automatically cleared after the request completes.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract headers
        headers = scope.get("headers", [])
        tenant_id = _extract_header(headers, b"x-tenant-id")
        user_id_str = _extract_header(headers, b"x-user-id")
        correlation_id = _extract_header(headers, b"x-correlation-id") or str(uuid4())

        # Parse user ID, default to nil UUID if not provided
        try:
            user_id = UUID(user_id_str) if user_id_str else UUID(int=0)
        except ValueError:
            user_id = UUID(int=0)

        # Set context for this request
        token = set_request_context(
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )

        # Wrap send to inject correlation ID response header
        async def send_with_correlation_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))
                message = {**message, "headers": resp_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        finally:
            clear_request_context(token)


# Module-level contribution for auto-discovery via entry points.
contribution = MiddlewareContribution(
    middleware_class=RequestContextMiddleware,
    priority=200,  # Context band (200-299)
)
