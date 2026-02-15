"""Middleware for populating request context from HTTP headers.

Extracts tenant ID, user ID, and correlation ID from request headers
and populates the request context ContextVar for use throughout the
request lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware

from praecepta.foundation.application import MiddlewareContribution
from praecepta.foundation.application.context import (
    clear_request_context,
    set_request_context,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


# Header names
TENANT_ID_HEADER = "X-Tenant-ID"
USER_ID_HEADER = "X-User-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that populates request context from HTTP headers.

    Extracts the following headers and makes them available via the
    request context module:
    - X-Tenant-ID: Required tenant identifier
    - X-User-ID: Required authenticated user ID
    - X-Correlation-ID: Optional, generated if not provided

    The context is automatically cleared after the request completes.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request and populate context.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The HTTP response.
        """
        # Extract headers (endpoints validate required headers separately)
        tenant_id = request.headers.get(TENANT_ID_HEADER, "")
        user_id_str = request.headers.get(USER_ID_HEADER, "")
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())

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

        try:
            # Add correlation ID to response headers for tracing
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            # Always clear context after request
            clear_request_context(token)


# Module-level contribution for auto-discovery via entry points.
contribution = MiddlewareContribution(
    middleware_class=RequestContextMiddleware,
    priority=200,  # Context band (200-299)
)
