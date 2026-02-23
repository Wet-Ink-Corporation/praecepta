"""Request ID middleware for correlation and tracing.

This module provides pure ASGI middleware for extracting, generating, and
propagating request IDs (correlation IDs) through the request lifecycle.
Request IDs are stored in context variables for access anywhere in the
request handling chain.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import MiddlewareContribution

if TYPE_CHECKING:
    from collections.abc import Callable

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


def _extract_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str:
    """Extract a header value from raw ASGI headers."""
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return ""


class RequestIdMiddleware:
    """Pure ASGI middleware for X-Request-ID header extraction and propagation.

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

        # Extract or generate request ID
        headers = scope.get("headers", [])
        request_id = _extract_header(headers, b"x-request-id")

        if not _is_valid_uuid(request_id):
            request_id = str(uuid.uuid4())

        # Store in context variable
        token = request_id_ctx.set(request_id)

        # Bind to structlog if available
        _bind_to_structlog(request_id)

        # Wrap send to inject response header
        async def send_with_request_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)
            _unbind_from_structlog()


def _bind_to_structlog(request_id: str) -> None:
    """Bind request ID to structlog context if available."""
    try:
        import structlog

        structlog.contextvars.bind_contextvars(request_id=request_id)
    except ImportError:
        pass


def _unbind_from_structlog() -> None:
    """Unbind request ID from structlog context if available."""
    try:
        import structlog

        structlog.contextvars.unbind_contextvars("request_id")
    except ImportError:
        pass


# Module-level contribution for auto-discovery via entry points.
contribution = MiddlewareContribution(
    middleware_class=RequestIdMiddleware,
    priority=10,  # Outermost band (0-99)
)
