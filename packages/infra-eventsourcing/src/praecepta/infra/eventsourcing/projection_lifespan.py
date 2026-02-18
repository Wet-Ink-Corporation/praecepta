"""Lifespan hook for projection poller auto-discovery and lifecycle.

Discovers projection classes and upstream application classes from
entry points, creates ``ProjectionPoller`` instances, and manages their
lifecycle (start on app startup, stop on app shutdown).

Each poller runs a background thread that periodically calls
``pull_and_process()`` on its projections, reading new events from the
shared PostgreSQL notification log.  This replaces the previous
``ProjectionRunner`` approach which relied on in-process
``SingleThreadedRunner`` prompts that do not work cross-process.

Priority 200 ensures projections start AFTER the event store (priority 100)
is initialised, since projections depend on the event store infrastructure.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import LifespanContribution, discover
from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.projections.poller import ProjectionPoller

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

GROUP_PROJECTIONS = "praecepta.projections"
GROUP_APPLICATIONS = "praecepta.applications"


def _discover_projections() -> list[type[BaseProjection]]:
    """Discover all registered projection classes.

    Returns:
        List of BaseProjection subclasses found via entry points.
        Non-BaseProjection entries are logged and skipped.
    """
    projections: list[type[BaseProjection]] = []
    for contrib in discover(GROUP_PROJECTIONS):
        value = contrib.value
        if isinstance(value, type) and issubclass(value, BaseProjection):
            projections.append(value)
            logger.debug("Discovered projection: %s (%s)", contrib.name, value.__name__)
        else:
            logger.warning(
                "Entry point %s:%s is not a BaseProjection subclass, skipping",
                GROUP_PROJECTIONS,
                contrib.name,
            )
    return projections


def _discover_applications() -> list[type[Any]]:
    """Discover all registered upstream application classes.

    Returns:
        List of Application classes found via entry points.
    """
    applications: list[type[Any]] = []
    for contrib in discover(GROUP_APPLICATIONS):
        value = contrib.value
        if isinstance(value, type):
            applications.append(value)
            logger.debug("Discovered application: %s (%s)", contrib.name, value.__name__)
        else:
            logger.warning(
                "Entry point %s:%s is not a class, skipping",
                GROUP_APPLICATIONS,
                contrib.name,
            )
    return applications


@asynccontextmanager
async def projection_runner_lifespan(app: Any) -> AsyncIterator[None]:
    """Start projection pollers at startup, stop at shutdown.

    Discovers projection and application classes from entry points.
    Creates one ``ProjectionPoller`` per upstream application, each with
    all discovered projections.  Each poller runs a background thread that
    periodically calls ``pull_and_process()`` to consume events from the
    shared PostgreSQL notification log.

    Args:
        app: The application instance (unused but required by protocol).

    Yields:
        None -- pollers are active during yield.
    """
    projections = _discover_projections()
    if not projections:
        logger.info("No projections discovered; projection runners will not start")
        yield
        return

    applications = _discover_applications()
    if not applications:
        logger.warning(
            "Projections discovered (%d) but no upstream applications found; "
            "projection runners will not start",
            len(projections),
        )
        yield
        return

    logger.info(
        "Starting projection runners: %d application(s), %d projection(s)",
        len(applications),
        len(projections),
    )

    pollers: list[ProjectionPoller] = []
    try:
        for app_cls in applications:
            poller = ProjectionPoller(
                projections=projections,
                upstream_application=app_cls,
            )
            poller.start()
            pollers.append(poller)
            logger.info(
                "Started projection poller for %s with %d projection(s)",
                app_cls.__name__,
                len(projections),
            )
    except Exception:
        logger.exception("Failed to start projection pollers; stopping already-started pollers")
        for poller in reversed(pollers):
            poller.stop()
        raise

    try:
        yield
    finally:
        for poller in reversed(pollers):
            poller.stop()


projection_lifespan_contribution = LifespanContribution(
    hook=projection_runner_lifespan,
    priority=200,
)
