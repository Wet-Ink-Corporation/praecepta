"""Manual instrumentation utilities for OpenTelemetry tracing.

This module provides utilities for manual span instrumentation:
- @traced_operation decorator for database operations
- start_span context manager for nested spans
- Helper functions for span management

Usage:
    # Decorator for database operations
    from praecepta.infra.observability.instrumentation import traced_operation

    @traced_operation("event_store.append", db_system="postgresql")
    async def append_events(aggregate_id: str, events: list) -> None:
        # Database operation is automatically traced
        pass

    # Context manager for nested spans
    from praecepta.infra.observability.instrumentation import start_span

    with start_span("process_batch", {"batch.size": 100}) as span:
        for item in batch:
            process_item(item)
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, cast

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


# Type variable for decorated functions
F = TypeVar("F", bound="Callable[..., Any]")


def get_tracer(name: str) -> trace.Tracer:
    """Get a named tracer instance.

    Args:
        name: Tracer name (typically __name__ from calling module).

    Returns:
        Tracer instance from the global TracerProvider.
        Returns NoOp tracer if tracing is not configured.

    Example:
        >>> tracer = get_tracer(__name__)
        >>> with tracer.start_as_current_span("my_operation"):
        ...     pass
    """
    return trace.get_tracer(name)


def get_current_span() -> trace.Span:
    """Get the currently active span.

    Returns:
        Active Span from context, or NonRecordingSpan if none active.
        Safe to call even when tracing is disabled.

    Example:
        >>> span = get_current_span()
        >>> if span.is_recording():
        ...     span.set_attribute("custom.key", "value")
    """
    return trace.get_current_span()


def set_span_error(span: trace.Span, exc: BaseException) -> None:
    """Record an exception in a span and set error status.

    Convenience function for consistent error recording across the codebase.

    Args:
        span: Span to record error in.
        exc: Exception to record.

    Example:
        >>> span = get_current_span()
        >>> try:
        ...     risky_operation()
        ... except Exception as exc:
        ...     set_span_error(span, exc)
        ...     raise
    """
    span.set_status(Status(StatusCode.ERROR, str(exc)))
    span.record_exception(exc)


def traced_operation(
    name: str,
    *,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    **span_attributes: Any,
) -> Callable[[F], F]:
    """Decorator to create a span for an operation.

    Creates a child span for the decorated function, automatically:
    - Sets span name and initial attributes
    - Sets span status to OK on success
    - Records exceptions and sets ERROR status on failure
    - Supports both sync and async functions

    Args:
        name: Span name (e.g., "event_store.append", "database.query").
        kind: Span kind (default: INTERNAL).
        **span_attributes: Initial span attributes (e.g., db_system="postgresql").

    Returns:
        Decorated function with automatic span instrumentation.

    Example:
        >>> @traced_operation(
        ...     "event_store.append",
        ...     db_system="postgresql",
        ...     db_operation="insert",
        ... )
        ... async def append_events(aggregate_id: str, events: list) -> None:
        ...     span = get_current_span()
        ...     span.set_attribute("event.count", len(events))
        ...     await event_store.insert_many(events)
    """

    def decorator(func: F) -> F:
        tracer = trace.get_tracer(func.__module__)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(name, kind=kind) as span:
                # Set initial attributes from decorator
                for key, value in span_attributes.items():
                    span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(name, kind=kind) as span:
                # Set initial attributes from decorator
                for key, value in span_attributes.items():
                    span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast("F", async_wrapper)
        return cast("F", sync_wrapper)

    return decorator


@contextmanager
def start_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Iterator[trace.Span]:
    """Context manager to create a nested span.

    Creates a child span for the code block, automatically setting status
    to OK on success or ERROR on exception.

    Args:
        name: Span name.
        attributes: Optional initial span attributes.
        kind: Span kind (default: INTERNAL).

    Yields:
        Active Span for adding attributes or events.

    Example:
        >>> with start_span("process_batch", {"batch.size": 100}) as span:
        ...     for item in batch:
        ...         process_item(item)
        ...     span.set_attribute("processed.count", len(batch))
    """
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(name, kind=kind) as span:
        # Set initial attributes if provided
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
