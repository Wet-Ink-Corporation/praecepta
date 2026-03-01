"""Subscription-based projection runner using LISTEN/NOTIFY.

Uses the eventsourcing library's ``ProjectionRunner`` (for lightweight
``Projection`` subclasses) rather than ``EventSourcedProjectionRunner``
(which targets ``ProcessApplication`` subclasses with their own event
stores and connection pools).

Each ``ProjectionRunner``:

- Creates ONE upstream application instance per projection
- Constructs a ``TrackingRecorder`` view for position tracking
- Uses PostgreSQL LISTEN/NOTIFY for near-instant event delivery
- Processes events in a dedicated background thread

The ``SubscriptionProjectionRunner`` groups projections by upstream
application and manages their lifecycle as a unit.

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
    - :class:`eventsourcing.projection.ProjectionRunner`
    - :class:`praecepta.infra.eventsourcing.projections.base.BaseProjection`
"""

from __future__ import annotations

import logging
from threading import Event, Thread
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eventsourcing.projection import ProjectionRunner
    from praecepta.infra.eventsourcing.projections.base import BaseProjection

logger = logging.getLogger(__name__)

_HEALTH_CHECK_INTERVAL_SECONDS = 2.0


class SubscriptionProjectionRunner:
    """Manages one ``ProjectionRunner`` per projection.

    Groups projections that follow the same upstream application and
    manages their lifecycle as a unit.  Each projection gets its own
    runner with its own upstream application instance, a
    ``TrackingRecorder`` view, and a dedicated LISTEN/NOTIFY
    subscription thread.

    Attributes:
        _projections: Projection classes to run.
        _upstream_application: Application class that produces events.
        _env: Optional environment variables for eventsourcing config.
        _runners: Active ``ProjectionRunner`` instances.
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
        self._runners: list[ProjectionRunner[Any, Any]] = []
        self._started = False
        self._stop_monitor = Event()
        self._monitor_thread: Thread | None = None

    def start(self) -> None:
        """Start a projection runner for each projection.

        Each runner creates one upstream application instance and
        subscribes to its recorder via LISTEN/NOTIFY (PostgreSQL).
        Uses the lightweight ``ProjectionRunner`` with a
        ``PostgresTrackingRecorder`` view — no per-projection event
        store or ``ProcessRecorder`` is created.

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

        from eventsourcing.postgres import PostgresTrackingRecorder
        from eventsourcing.projection import ProjectionRunner as _ProjectionRunner

        for proj_cls in self._projections:
            logger.info("  - %s (topics: %s)", proj_cls.__name__, proj_cls.topics or "all")
            runner: _ProjectionRunner[Any, Any] = _ProjectionRunner(
                application_class=self._upstream_application,
                projection_class=proj_cls,
                view_class=PostgresTrackingRecorder,
                env=self._env,
            )
            # __enter__ activates the subscription and starts processing
            runner.__enter__()
            self._runners.append(runner)

        # Start health monitor to detect processing thread failures
        if self._runners:
            self._stop_monitor.clear()
            self._monitor_thread = Thread(
                target=self._monitor_health,
                daemon=True,
                name=f"projection-monitor-{self._upstream_application.__name__}",
            )
            self._monitor_thread.start()

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

        # Stop health monitor before runners to avoid false positives
        self._stop_monitor.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None

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

    def _monitor_health(self) -> None:
        """Watch for processing thread failures and log immediately.

        The eventsourcing library's ``ProjectionRunner`` stores errors in
        ``_thread_error`` but never logs them — they only surface at
        shutdown via ``__exit__()``.  This monitor polls runner health so
        operators can detect stalled projections without waiting for
        application shutdown.
        """
        reported: set[int] = set()
        while not self._stop_monitor.is_set():
            for i, runner in enumerate(self._runners):
                if i in reported:
                    continue
                if not runner.is_interrupted.is_set():
                    continue
                reported.add(i)
                proj_name = type(runner.projection).__name__
                error = runner._thread_error
                if error is not None:
                    logger.error(
                        "Projection %s processing thread failed: %s",
                        proj_name,
                        error,
                        exc_info=error,
                    )
                else:
                    logger.warning(
                        "Projection %s processing thread stopped unexpectedly (no error captured)",
                        proj_name,
                    )
            if len(reported) == len(self._runners):
                break
            self._stop_monitor.wait(timeout=_HEALTH_CHECK_INTERVAL_SECONDS)

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
