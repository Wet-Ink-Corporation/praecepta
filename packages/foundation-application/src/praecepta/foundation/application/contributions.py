"""Contribution types for the auto-discovery system.

These dataclasses define the shape of contributions that packages declare
via entry points. They are framework-agnostic (no FastAPI, no SQLAlchemy, etc.)
and live in the foundation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MiddlewareContribution:
    """Describes a middleware to be auto-discovered and registered.

    Attributes:
        middleware_class: The ASGI middleware class.
        priority: Ordering priority. Lower numbers execute first (outermost).
            Bands: 0-99 outermost, 100-199 security, 200-299 context, 300-399 policy.
        kwargs: Additional keyword arguments to pass to ``add_middleware()``.
    """

    middleware_class: type[Any]
    priority: int = 500
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ErrorHandlerContribution:
    """Describes an exception handler to be auto-discovered and registered.

    Attributes:
        exception_class: The exception type to handle.
        handler: The async handler callable ``(Request, Exception) -> Response``.
    """

    exception_class: type[BaseException]
    handler: Any  # Callable[[Request, Exception], Awaitable[Response]]


@dataclass(frozen=True, slots=True)
class LifespanContribution:
    """Describes a lifespan hook to be auto-discovered and registered.

    Attributes:
        hook: An async context manager factory ``(app) -> AsyncContextManager[None]``.
        priority: Ordering priority. Lower priorities start first (and shut down last).
    """

    hook: Any  # Callable[[Any], AsyncContextManager[None]]
    priority: int = 500
