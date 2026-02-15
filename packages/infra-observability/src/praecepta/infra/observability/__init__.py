"""Praecepta Infra Observability — structlog + OpenTelemetry logging and tracing."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application.contributions import LifespanContribution
from praecepta.infra.observability.logging import (
    LoggingSettings,
    configure_logging,
    get_logger,
)
from praecepta.infra.observability.middleware import TraceContextMiddleware
from praecepta.infra.observability.tracing import (
    TracingSettings,
    configure_tracing,
    shutdown_tracing,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def _observability_lifespan(app: Any) -> AsyncIterator[None]:
    """Lifespan hook that configures logging and tracing on startup.

    Args:
        app: The FastAPI application instance.
    """
    configure_logging()
    configure_tracing(app)
    yield
    shutdown_tracing()


lifespan_contribution = LifespanContribution(
    hook=_observability_lifespan,
    priority=50,  # Start early, shut down late
)

__all__ = [
    "LoggingSettings",
    "TraceContextMiddleware",
    "TracingSettings",
    "configure_logging",
    "configure_tracing",
    "get_logger",
    "lifespan_contribution",
    "shutdown_tracing",
]
