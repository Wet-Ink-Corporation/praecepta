"""Lifespan hook for event store initialization and cleanup.

Provides a LifespanContribution that initializes the event store
singleton at application startup and closes it at shutdown.

Also bridges ``EventSourcingSettings`` defaults into ``os.environ`` so that
eventsourcing library ``Application`` subclasses (which read configuration
directly from ``os.environ``) pick up the correct ``PERSISTENCE_MODULE``
and ``POSTGRES_*`` values.  Without this bridge, the library defaults to
``eventsourcing.popo`` (in-memory storage), causing silent data loss.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from praecepta.foundation.application import LifespanContribution

logger = logging.getLogger(__name__)

# Keys bridged from EventSourcingSettings to os.environ.
# Only set when not already present (explicit env vars always win).
_BRIDGE_KEYS = frozenset(
    {
        "PERSISTENCE_MODULE",
        "POSTGRES_DBNAME",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "CREATE_TABLE",
        "POSTGRES_SCHEMA",
    }
)


def _bridge_settings_to_environ() -> None:
    """Populate ``os.environ`` with ``EventSourcingSettings`` defaults.

    Only sets keys that are **not** already present in ``os.environ``,
    so explicit environment variables always take precedence.

    Emits a warning if ``PERSISTENCE_MODULE`` was not set, since the
    eventsourcing library defaults to in-memory storage without it.
    """
    if "PERSISTENCE_MODULE" not in os.environ:
        logger.warning(
            "PERSISTENCE_MODULE not set in environment. "
            "Bridging from EventSourcingSettings (default: eventsourcing.postgres). "
            "Set PERSISTENCE_MODULE explicitly in production.",
        )

    try:
        from praecepta.infra.eventsourcing.settings import EventSourcingSettings

        settings = EventSourcingSettings()  # type: ignore[call-arg]
    except Exception:
        logger.warning(
            "Could not load EventSourcingSettings for environment bridging. "
            "Ensure POSTGRES_* variables are set.",
        )
        return

    env_dict = settings.to_env_dict()
    for key in _BRIDGE_KEYS:
        if key not in os.environ and key in env_dict:
            os.environ[key] = env_dict[key]
            log_value = "***" if "PASSWORD" in key else env_dict[key]
            logger.debug("Bridged %s=%s to os.environ", key, log_value)


@asynccontextmanager
async def event_store_lifespan(app: Any) -> AsyncIterator[None]:
    """Initialize event store at startup, close at shutdown.

    On entry this hook:

    1. **Bridges** ``EventSourcingSettings`` defaults into ``os.environ`` so
       that ``Application[UUID]`` subclasses (which construct their own
       ``InfrastructureFactory`` from ``os.environ``) receive the correct
       ``PERSISTENCE_MODULE`` and connection parameters.
    2. **Initialises** the ``get_event_store()`` singleton for direct event
       store access (projection rebuilds, admin queries, etc.).

    On exit it closes the ``EventStoreFactory`` singleton's connection pool
    (if one was created).

    Args:
        app: The application instance (unused but required by protocol).

    Yields:
        None — the event store is available via ``get_event_store()`` during yield.
    """
    _bridge_settings_to_environ()

    from praecepta.infra.eventsourcing.event_store import get_event_store

    store = get_event_store()
    yield
    store.close()


lifespan_contribution = LifespanContribution(
    hook=event_store_lifespan,
    priority=100,
)
