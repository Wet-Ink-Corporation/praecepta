"""Tracing middleware for trace-log correlation.

This module provides middleware to bind OpenTelemetry trace context to
structlog for automatic trace ID and span ID inclusion in all logs.

Usage:
    # Add to FastAPI middleware stack
    from praecepta.infra.observability.middleware import TraceContextMiddleware
    app.add_middleware(TraceContextMiddleware)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

from praecepta.foundation.application.contributions import MiddlewareContribution

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


class TraceContextMiddleware(BaseHTTPMiddleware):
    """Middleware to bind trace_id and span_id to structlog context.

    Extracts trace context from the active OpenTelemetry span (created by
    FastAPIInstrumentor) and binds trace_id and span_id to structlog
    context variables. This ensures all logs within a request include
    trace correlation fields.

    Must be added to middleware stack AFTER RequestIdMiddleware to ensure
    request_id is already bound when trace context is added.

    Note:
        If tracing is disabled or no active span exists, this middleware
        is a no-op and does not bind any context.

    Example:
        >>> from fastapi import FastAPI
        >>> from praecepta.infra.observability.middleware import TraceContextMiddleware
        >>> app = FastAPI()
        >>> app.add_middleware(TraceContextMiddleware)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with trace context binding.

        Extracts trace_id and span_id from the active span and binds them
        to structlog context for correlation with logs.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            Response from downstream handlers.
        """
        # Get current span from OpenTelemetry context
        span = trace.get_current_span()

        # Only bind context if span is recording (tracing is enabled)
        if span.is_recording():
            span_context = span.get_span_context()
            # Format trace_id as 32 hex chars, span_id as 16 hex chars
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

            # Bind to structlog context variables
            structlog.contextvars.bind_contextvars(
                trace_id=trace_id,
                span_id=span_id,
            )

        try:
            response = await call_next(request)
            return response
        finally:
            # Always unbind trace context to prevent leakage between requests
            structlog.contextvars.unbind_contextvars("trace_id", "span_id")


# Module-level contribution for auto-discovery via entry points
contribution = MiddlewareContribution(
    middleware_class=TraceContextMiddleware,
    priority=20,  # Outermost band (0-99)
)
