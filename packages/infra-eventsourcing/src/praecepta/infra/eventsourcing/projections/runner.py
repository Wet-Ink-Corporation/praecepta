"""Projection runner for managing projection lifecycle.

This module provides the ProjectionRunner class that wraps the eventsourcing
library's System and Runner classes with additional features: graceful
start/stop lifecycle, logging, and observability.

Example:
    Running projections as background workers::

        from praecepta.infra.eventsourcing.projections import (
            BaseProjection,
            ProjectionRunner,
        )

        class SummaryProjection(BaseProjection):
            # ... implementation
            pass

        runner = ProjectionRunner(
            projections=[SummaryProjection],
            upstream_application=MyApplication,
        )

        # Start processing events
        runner.start()

        # ... application runs ...

        # Graceful shutdown
        runner.stop()

See Also:
    - praecepta.infra.eventsourcing.projections.base: BaseProjection class
    - praecepta.infra.eventsourcing.projections.rebuilder: Rebuild utilities
    - eventsourcing.system: Library System and Runner classes
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.system import Runner
    from praecepta.infra.eventsourcing.projections.base import BaseProjection

    # Type alias for Runner with UUID aggregate ID
    RunnerType = Runner[UUID]

logger = logging.getLogger(__name__)


class ProjectionRunner:
    """Runs projections as background workers with lifecycle management.

    Wraps eventsourcing's System and Runner classes with additional features:
    - Graceful start/stop lifecycle
    - Logging and observability hooks
    - Status tracking via is_running property
    - Access to managed application instances

    The runner creates a System with pipes connecting the upstream
    application (event source) to each projection (event consumer).
    Each projection independently processes events from the notification
    log and tracks its own position.

    Attributes:
        _projections: List of projection classes to run.
        _upstream_application: Application class that produces events.
        _runner_class: Optional custom Runner class (default: SingleThreadedRunner).
        _env: Optional environment variables for configuration.
        _runner: Internal eventsourcing Runner instance.
        _started: Whether the runner is currently active.
    """

    def __init__(
        self,
        projections: list[type[BaseProjection]],
        upstream_application: type[Any],
        runner_class: type[RunnerType] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Initialize projection runner.

        Args:
            projections: List of BaseProjection subclasses to run.
                Each projection will receive events from the upstream
                application's notification log.
            upstream_application: Application class that produces events
                for the projections to consume.
            runner_class: Optional runner class. Defaults to SingleThreadedRunner
                for development. Use MultiThreadedRunner for production when
                concurrent projection processing is needed.
            env: Optional environment variables for configuration.
                Passed to the eventsourcing library for infrastructure config.
        """
        self._projections = projections
        self._upstream_application = upstream_application
        self._runner_class = runner_class
        self._env = env or {}
        self._runner: RunnerType | None = None
        self._started = False

    def start(self) -> None:
        """Start projection processing.

        Creates the eventsourcing System and Runner, then starts
        processing events from the notification log. Each projection
        resumes from its last tracked position.

        Raises:
            RuntimeError: If runner is already started. Call stop() first
                before starting again.
        """
        if self._started:
            msg = "ProjectionRunner already started"
            raise RuntimeError(msg)

        logger.info(
            "Starting projection runner with %d projections",
            len(self._projections),
        )

        for projection_cls in self._projections:
            logger.info("  - %s", projection_cls.__name__)

        # Build system pipes: upstream -> each projection
        from eventsourcing.system import SingleThreadedRunner, System

        pipes = [
            [self._upstream_application, projection_cls] for projection_cls in self._projections
        ]

        system = System(pipes=pipes)

        runner_class = self._runner_class or SingleThreadedRunner
        self._runner = runner_class(system, env=self._env)
        self._runner.start()
        self._started = True

        logger.info("Projection runner started")

    def stop(self) -> None:
        """Stop projection processing gracefully.

        Waits for in-progress event processing to complete before
        shutting down. Safe to call even if not started (logs warning).
        """
        if not self._started or self._runner is None:
            logger.warning("ProjectionRunner not started, nothing to stop")
            return

        logger.info("Stopping projection runner...")
        self._runner.stop()
        self._runner = None
        self._started = False
        logger.info("Projection runner stopped")

    @property
    def is_running(self) -> bool:
        """Check if runner is currently active.

        Returns:
            True if started and not stopped, False otherwise.
        """
        return self._started

    def get(self, application_class: type[Any]) -> Any:
        """Get application instance from runner.

        Useful for accessing upstream application to trigger commands
        during testing, or for inspecting projection state.

        Args:
            application_class: Application class to retrieve. Must be one
                of the applications in the system (upstream or projection).

        Returns:
            Application instance managed by the runner.

        Raises:
            RuntimeError: If runner not started.
        """
        if self._runner is None:
            msg = "ProjectionRunner not started"
            raise RuntimeError(msg)
        return self._runner.get(application_class)

    def __enter__(self) -> ProjectionRunner:
        """Context manager entry: start the runner.

        Returns:
            Self for use in with statement.
        """
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit: stop the runner.

        Args:
            exc_type: Exception type if exception raised in context.
            exc_val: Exception value if exception raised in context.
            exc_tb: Exception traceback if exception raised in context.

        Note:
            Always stops the runner, even if an exception was raised.
        """
        self.stop()
