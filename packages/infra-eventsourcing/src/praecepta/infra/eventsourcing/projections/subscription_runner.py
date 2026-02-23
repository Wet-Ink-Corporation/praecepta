"""Subscription-based projection runner using LISTEN/NOTIFY.

Replaces the polling-based ``ProjectionPoller`` with the eventsourcing
library's ``EventSourcedProjectionRunner``, which:

- Creates ONE upstream application instance per projection (not N+1)
- Uses PostgreSQL LISTEN/NOTIFY for near-instant event delivery
- Processes events in a dedicated background thread per projection
- Tracks position via the projection's own ProcessRecorder

Example::

    from praecepta.infra.eventsourcing.projections import (
        BaseProjection,
        SubscriptionProjectionRunner,
    )

    runner = SubscriptionProjectionRunner(
        projections=[TenantListProjection, TenantConfigProjection],
        upstream_application=TenantApplication,
    )

    runner.start()
    # ... application runs ...
    runner.stop()

See Also:
    - :class:`eventsourcing.projection.EventSourcedProjectionRunner`
    - :class:`praecepta.infra.eventsourcing.projections.base.BaseProjection`
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eventsourcing.projection import EventSourcedProjectionRunner
    from praecepta.infra.eventsourcing.projections.base import BaseProjection

logger = logging.getLogger(__name__)


class SubscriptionProjectionRunner:
    """Manages one ``EventSourcedProjectionRunner`` per projection.

    Groups projections that follow the same upstream application and
    manages their lifecycle as a unit.  Each projection gets its own
    runner with a single upstream application instance and a dedicated
    LISTEN/NOTIFY subscription thread.

    Attributes:
        _projections: Projection classes to run.
        _upstream_application: Application class that produces events.
        _env: Optional environment variables for eventsourcing config.
        _runners: Active ``EventSourcedProjectionRunner`` instances.
        _started: Whether the runner group is currently active.
    """

    def __init__(
        self,
        projections: list[type[BaseProjection]],
        upstream_application: type[Any],
        env: dict[str, str] | None = None,
    ) -> None:
        """Initialise the subscription runner.

        Args:
            projections: List of ``BaseProjection`` subclasses to run.
                Each projection must declare ``upstream_application``
                matching the given ``upstream_application`` argument.
            upstream_application: Application class that produces events.
            env: Optional environment variables for eventsourcing
                infrastructure configuration.
        """
        self._projections = projections
        self._upstream_application = upstream_application
        self._env = env
        self._runners: list[EventSourcedProjectionRunner[Any, Any]] = []
        self._started = False

    def start(self) -> None:
        """Start a subscription runner for each projection.

        Each runner creates ONE upstream application instance and
        subscribes to its recorder via LISTEN/NOTIFY (PostgreSQL).

        Raises:
            RuntimeError: If the runner group is already started.
        """
        if self._started:
            msg = "SubscriptionProjectionRunner already started"
            raise RuntimeError(msg)

        logger.info(
            "Starting subscription runners for %s with %d projection(s)",
            self._upstream_application.__name__,
            len(self._projections),
        )

        from eventsourcing.projection import EventSourcedProjectionRunner

        for proj_cls in self._projections:
            logger.info("  - %s (topics: %s)", proj_cls.__name__, proj_cls.topics or "all")
            runner: EventSourcedProjectionRunner[Any, Any] = EventSourcedProjectionRunner(
                application_class=self._upstream_application,
                projection_class=proj_cls,
                env=self._env,
            )
            # __enter__ activates the subscription and starts processing
            runner.__enter__()
            self._runners.append(runner)

        self._started = True
        logger.info("Subscription runners started")

    def stop(self) -> None:
        """Stop all subscription runners and release resources.

        Safe to call even if not started (logs a warning).
        Runners are stopped in reverse order of creation.
        """
        if not self._started:
            logger.warning("SubscriptionProjectionRunner not started, nothing to stop")
            return

        logger.info("Stopping subscription runners...")
        for runner in reversed(self._runners):
            try:
                runner.__exit__(None, None, None)
            except Exception:
                logger.exception(
                    "Error stopping runner for %s",
                    type(runner.projection).__name__,
                )

        self._runners.clear()
        self._started = False
        logger.info("Subscription runners stopped")

    @property
    def is_running(self) -> bool:
        """Check if the runner group is currently active."""
        return self._started

    def __enter__(self) -> SubscriptionProjectionRunner:
        """Context manager entry: start the runner group."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit: stop the runner group."""
        self.stop()
