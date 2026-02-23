"""Polling-based projection runner for cross-process event consumption.

Replaces reliance on in-process ``SingleThreadedRunner`` prompts with a
background thread that periodically calls ``pull_and_process()`` on each
projection, reading new events from the shared PostgreSQL notification log.

The ``SingleThreadedRunner`` is still used internally to construct the
``System`` and wire up ``follow()`` relationships (readers, mappers,
tracking tables).  The polling thread then drives consumption explicitly,
which works correctly when the event-writing application lives in a
different process (or is a different instance) from the runner's internal
copy.

Example::

    from praecepta.infra.eventsourcing.projections import (
        BaseProjection,
        ProjectionPoller,
    )

    class SummaryProjection(BaseProjection):
        ...

    poller = ProjectionPoller(
        projections=[SummaryProjection],
        upstream_application=MyApplication,
    )

    poller.start()
    # ... application runs ...
    poller.stop()

See Also:
    - :mod:`praecepta.infra.eventsourcing.projections.base` — ``BaseProjection``
    - :mod:`praecepta.infra.eventsourcing.projections.runner` — legacy in-process runner
    - :mod:`praecepta.infra.eventsourcing.settings` — ``ProjectionPollingSettings``
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from praecepta.infra.eventsourcing.settings import ProjectionPollingSettings

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.system import Runner
    from praecepta.infra.eventsourcing.projections.base import BaseProjection

    RunnerType = Runner[UUID]

logger = logging.getLogger(__name__)


class ProjectionPoller:
    """Runs projections via periodic database polling.

    Uses ``SingleThreadedRunner`` to construct the ``System`` and wire up
    ``follow()`` relationships, then runs a background thread that
    periodically calls ``pull_and_process()`` on each projection.

    This approach correctly handles cross-process event consumption:
    the API writes events to PostgreSQL, and the poller reads them
    from the shared notification log table.

    Attributes:
        _projections: Projection classes to run.
        _upstream_application: Application class that produces events.
        _settings: Polling configuration (interval, timeout, etc.).
        _env: Optional environment variables for eventsourcing config.
        _runner: Internal ``SingleThreadedRunner`` for System wiring.
        _poll_thread: Background thread running the poll loop.
        _stop_event: Threading event for graceful shutdown signaling.
        _started: Whether the poller is currently active.
    """

    def __init__(
        self,
        projections: list[type[BaseProjection]],
        upstream_application: type[Any],
        settings: ProjectionPollingSettings | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Initialise the projection poller.

        .. deprecated::
            ``ProjectionPoller`` uses ``SingleThreadedRunner`` which creates
            N+1 application instances with separate connection pools and uses
            polling instead of LISTEN/NOTIFY subscriptions.
            Use :class:`~praecepta.infra.eventsourcing.projections.subscription_runner.SubscriptionProjectionRunner`
            instead.

        Args:
            projections: List of ``BaseProjection`` subclasses to run.
                Each projection will consume events from the upstream
                application's notification log.
            upstream_application: Application class that produces events.
            settings: Polling configuration. If ``None``, defaults are
                loaded from environment variables (``PROJECTION_*``).
            env: Optional environment variables for eventsourcing
                infrastructure configuration.
        """
        import warnings

        warnings.warn(
            "ProjectionPoller uses SingleThreadedRunner which creates N+1 application "
            "instances with separate connection pools. Use SubscriptionProjectionRunner "
            "instead, which uses the library's EventSourcedProjectionRunner with "
            "LISTEN/NOTIFY subscriptions.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._projections = projections
        self._upstream_application = upstream_application
        self._env = env or {}
        self._runner: RunnerType | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started = False
        self._settings: ProjectionPollingSettings = settings or ProjectionPollingSettings()

    def start(self) -> None:
        """Start the poller: create System, wire follow(), start poll thread.

        Raises:
            RuntimeError: If the poller is already started.
        """
        if self._started:
            msg = "ProjectionPoller already started"
            raise RuntimeError(msg)

        logger.info(
            "Starting projection poller with %d projections (poll_interval=%.1fs)",
            len(self._projections),
            self._settings.poll_interval,
        )
        for proj_cls in self._projections:
            logger.info("  - %s", proj_cls.__name__)

        from eventsourcing.system import SingleThreadedRunner, System

        pipes = [[self._upstream_application, proj_cls] for proj_cls in self._projections]
        system = System(pipes=pipes)

        # SingleThreadedRunner constructs app instances and wires follow()
        self._runner = SingleThreadedRunner(system, env=self._env)
        self._runner.start()

        # Start background polling thread
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="projection-poller",
            daemon=True,
        )
        self._poll_thread.start()
        self._started = True

        logger.info("Projection poller started")

    def _poll_loop(self) -> None:
        """Background thread: periodically ``pull_and_process`` on each follower."""
        leader_name = self._upstream_application.name
        while not self._stop_event.is_set():
            try:
                for proj_cls in self._projections:
                    if self._stop_event.is_set():
                        break
                    follower = self._runner.get(proj_cls)  # type: ignore[union-attr]
                    follower.pull_and_process(leader_name)
            except Exception:
                logger.exception("Error in projection poll cycle")
            self._stop_event.wait(timeout=self._settings.poll_interval)

    def stop(self) -> None:
        """Stop polling and clean up resources.

        Safe to call even if not started (logs a warning).
        """
        if not self._started or self._runner is None:
            logger.warning("ProjectionPoller not started, nothing to stop")
            return

        logger.info("Stopping projection poller...")
        self._stop_event.set()

        if self._poll_thread is not None:
            self._poll_thread.join(timeout=self._settings.poll_timeout)
            if self._poll_thread.is_alive():
                logger.warning(
                    "Projection poll thread did not stop within %.1fs timeout",
                    self._settings.poll_timeout,
                )

        self._runner.stop()
        self._runner = None
        self._poll_thread = None
        self._started = False

        logger.info("Projection poller stopped")

    @property
    def is_running(self) -> bool:
        """Check if the poller is currently active.

        Returns:
            ``True`` if started and not stopped, ``False`` otherwise.
        """
        return self._started

    def get(self, application_class: type[Any]) -> Any:
        """Get an application instance from the internal runner.

        Args:
            application_class: Application class to retrieve.

        Returns:
            Application instance managed by the internal runner.

        Raises:
            RuntimeError: If the poller is not started.
        """
        if self._runner is None:
            msg = "ProjectionPoller not started"
            raise RuntimeError(msg)
        return self._runner.get(application_class)

    def __enter__(self) -> ProjectionPoller:
        """Context manager entry: start the poller."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit: stop the poller."""
        self.stop()
