"""Lifespan hook for event store initialization and cleanup.

Provides a LifespanContribution that initializes the event store
singleton at application startup and closes it at shutdown.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from praecepta.foundation.application import LifespanContribution


@asynccontextmanager
async def event_store_lifespan(app: Any) -> AsyncIterator[None]:
    """Initialize event store at startup, close at shutdown.

    Args:
        app: The application instance (unused but required by protocol).

    Yields:
        None — the event store is available via get_event_store() during yield.
    """
    from praecepta.infra.eventsourcing.event_store import get_event_store

    store = get_event_store()
    yield
    store.close()


lifespan_contribution = LifespanContribution(
    hook=event_store_lifespan,
    priority=100,
)
