"""Lifespan hook for projection runner auto-discovery and lifecycle.

Discovers projection classes from entry points, groups them by their
declared ``upstream_application``, and creates
``SubscriptionProjectionRunner`` instances that use the eventsourcing
library's ``EventSourcedProjectionRunner`` for LISTEN/NOTIFY-based
event delivery.

Each runner creates ONE upstream application instance and subscribes
to its recorder for near-instant event processing.

Priority 200 ensures projections start AFTER the event store (priority 100)
is initialised, since projections depend on the event store infrastructure.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import LifespanContribution, discover
from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.projections.subscription_runner import (
    SubscriptionProjectionRunner,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

GROUP_PROJECTIONS = "praecepta.projections"


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


def _group_projections_by_application(
    projections: list[type[BaseProjection]],
) -> dict[type[Any], list[type[BaseProjection]]]:
    """Group projections by their declared ``upstream_application``.

    Projections without ``upstream_application`` are logged and skipped.

    Returns:
        Mapping of application class to list of projection classes.
    """
    grouped: dict[type[Any], list[type[BaseProjection]]] = defaultdict(list)
    for proj_cls in projections:
        app_cls = getattr(proj_cls, "upstream_application", None)
        if app_cls is None:
            logger.warning(
                "Projection %s has no upstream_application declared; skipping",
                proj_cls.__name__,
            )
            continue
        grouped[app_cls].append(proj_cls)
        logger.debug(
            "Projection %s -> %s",
            proj_cls.__name__,
            app_cls.__name__,
        )
    return dict(grouped)


@asynccontextmanager
async def projection_runner_lifespan(app: Any) -> AsyncIterator[None]:
    """Start projection runners at startup, stop at shutdown.

    Discovers projection classes from entry points, groups them by their
    declared ``upstream_application``, and creates one
    ``SubscriptionProjectionRunner`` per upstream application.  Each
    runner uses PostgreSQL LISTEN/NOTIFY for event delivery.

    Args:
        app: The application instance (unused but required by protocol).

    Yields:
        None -- runners are active during yield.
    """
    projections = _discover_projections()
    if not projections:
        logger.info("No projections discovered; projection runners will not start")
        yield
        return

    grouped = _group_projections_by_application(projections)
    if not grouped:
        logger.warning(
            "Projections discovered (%d) but none declare upstream_application; "
            "projection runners will not start",
            len(projections),
        )
        yield
        return

    total_projections = sum(len(ps) for ps in grouped.values())

    # Enforce max_projection_runners limit (CF-14)
    max_runners = int(os.getenv("MAX_PROJECTION_RUNNERS", "8"))
    if total_projections > max_runners:
        logger.warning(
            "Discovered %d projections exceeds max_projection_runners=%d; "
            "capping to first %d projections",
            total_projections,
            max_runners,
            max_runners,
        )
        capped: dict[type[Any], list[type[BaseProjection]]] = {}
        count = 0
        for app_cls, app_projections in grouped.items():
            remaining = max_runners - count
            if remaining <= 0:
                break
            capped[app_cls] = app_projections[:remaining]
            count += len(capped[app_cls])
        grouped = capped
        total_projections = count

    logger.info(
        "Starting projection runners: %d application(s), %d projection(s)",
        len(grouped),
        total_projections,
    )

    runners: list[SubscriptionProjectionRunner] = []
    try:
        for app_cls, app_projections in grouped.items():
            runner = SubscriptionProjectionRunner(
                projections=app_projections,
                upstream_application=app_cls,
            )
            runner.start()
            runners.append(runner)
            logger.info(
                "Started subscription runner for %s with %d projection(s)",
                app_cls.__name__,
                len(app_projections),
            )
    except Exception:
        logger.exception("Failed to start projection runners; stopping already-started runners")
        for runner in reversed(runners):
            runner.stop()
        raise

    try:
        yield
    finally:
        for runner in reversed(runners):
            runner.stop()


projection_lifespan_contribution = LifespanContribution(
    hook=projection_runner_lifespan,
    priority=200,
)
