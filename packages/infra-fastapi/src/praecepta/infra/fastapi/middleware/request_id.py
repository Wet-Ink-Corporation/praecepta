"""Request ID middleware for correlation and tracing.

This module provides ASGI middleware for extracting, generating, and propagating
request IDs (correlation IDs) through the request lifecycle. Request IDs are
stored in context variables for access anywhere in the request handling chain.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request  # noqa: TC002
from starlette.responses import Response  # noqa: TC002

from praecepta.foundation.application import MiddlewareContribution

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# Header name constant
REQUEST_ID_HEADER = "X-Request-ID"

# Context variable for request ID propagation
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context.

    Returns the request ID set by RequestIdMiddleware for the current
    async context. Returns empty string if called outside of request context.

    Returns:
        Current request ID or empty string if not in request context.

    Example:
        >>> from praecepta.infra.fastapi.middleware import get_request_id
        >>> # Inside a request handler
        >>> request_id = get_request_id()
        >>> print(f"Processing request {request_id}")
    """
    return request_id_ctx.get()


def _is_valid_uuid(value: str | None) -> bool:
    """Check if value is a valid UUID format.

    Validates that the provided string is a valid UUID (any version).
    Returns False for None, empty strings, or invalid formats.

    Args:
        value: String to validate as UUID.

    Returns:
        True if value is a valid UUID format, False otherwise.
    """
    if not value:
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class RequestIdMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for X-Request-ID header extraction and propagation.

    This middleware:
    1. Extracts X-Request-ID from incoming request headers
    2. Validates the header is a valid UUID format
    3. Generates a new UUID4 if header is missing or invalid
    4. Stores the request ID in a context variable for the request duration
    5. Optionally binds to structlog context (if structlog is configured)
    6. Adds X-Request-ID to response headers

    Design Decision:
        Invalid UUIDs from clients generate new UUIDs rather than returning 400.
        This resilient approach ensures requests aren't blocked due to client
        header misconfigurations.

    Example:
        >>> from fastapi import FastAPI
        >>> from praecepta.infra.fastapi.middleware import RequestIdMiddleware
        >>>
        >>> app = FastAPI()
        >>> app.add_middleware(RequestIdMiddleware)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with request ID handling.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            Response with X-Request-ID header added.
        """
        # Extract or generate request ID
        request_id = request.headers.get(REQUEST_ID_HEADER, "")

        if not _is_valid_uuid(request_id):
            request_id = str(uuid.uuid4())

        # Store in context variable
        token = request_id_ctx.set(request_id)

        # Bind to structlog if available (optional integration)
        self._bind_to_structlog(request_id)

        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            # Reset context to prevent leakage between requests
            request_id_ctx.reset(token)
            self._unbind_from_structlog()

    def _bind_to_structlog(self, request_id: str) -> None:
        """Bind request ID to structlog context if available.

        Args:
            request_id: Request ID to bind.
        """
        try:
            import structlog

            structlog.contextvars.bind_contextvars(request_id=request_id)
        except ImportError:
            # structlog not installed, skip binding
            pass

    def _unbind_from_structlog(self) -> None:
        """Unbind request ID from structlog context if available."""
        try:
            import structlog

            structlog.contextvars.unbind_contextvars("request_id")
        except ImportError:
            # structlog not installed, skip unbinding
            pass


# Module-level contribution for auto-discovery via entry points.
contribution = MiddlewareContribution(
    middleware_class=RequestIdMiddleware,
    priority=10,  # Outermost band (0-99)
)
