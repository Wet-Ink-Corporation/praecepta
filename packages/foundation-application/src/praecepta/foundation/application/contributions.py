"""Contribution types for the auto-discovery system.

These dataclasses define the shape of contributions that packages declare
via entry points. They are framework-agnostic (no FastAPI, no SQLAlchemy, etc.)
and live in the foundation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Priority band constants for middleware ordering
MIDDLEWARE_PRIORITY_MIN = 0
MIDDLEWARE_PRIORITY_MAX = 499

# Recommended lifespan priority constants
LIFESPAN_PRIORITY_OBSERVABILITY = 50
LIFESPAN_PRIORITY_PERSISTENCE = 75
LIFESPAN_PRIORITY_EVENTSTORE = 100
LIFESPAN_PRIORITY_TASKIQ = 150
LIFESPAN_PRIORITY_PROJECTIONS = 200


@dataclass(frozen=True, slots=True)
class MiddlewareContribution:
    """Describes a middleware to be auto-discovered and registered.

    Attributes:
        middleware_class: The ASGI middleware class.
        priority: Ordering priority. Lower numbers execute first (outermost).
            Bands: 0-99 outermost, 100-199 security, 200-299 context, 300-399 policy.
            Must be in range [0, 499].
        kwargs: Additional keyword arguments to pass to ``add_middleware()``.
    """

    middleware_class: type[Any]
    priority: int = 400
    kwargs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not MIDDLEWARE_PRIORITY_MIN <= self.priority <= MIDDLEWARE_PRIORITY_MAX:
            msg = (
                f"Middleware priority must be between {MIDDLEWARE_PRIORITY_MIN} "
                f"and {MIDDLEWARE_PRIORITY_MAX}, got {self.priority}"
            )
            raise ValueError(msg)


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
