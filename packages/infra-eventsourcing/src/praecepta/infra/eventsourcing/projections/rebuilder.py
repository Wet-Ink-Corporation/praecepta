"""Projection rebuilder for orchestrating rebuild from event stream.

This module provides the ProjectionRebuilder class that orchestrates
projection rebuild workflow: clear read model, reset tracking position,
and prepare for event replay.

A rebuild is needed when:
- Projection schema changed (added/removed fields)
- Projection logic bug fixed (need to recompute)
- New projection added (process historical events)
- Data corruption detected (restore from source of truth)

Example:
    Rebuilding a projection::

        from praecepta.infra.eventsourcing.projections import (
            BaseProjection,
            ProjectionRebuilder,
        )

        class SummaryProjection(BaseProjection):
            # ... implementation
            pass

        # Get projection instance
        projection = SummaryProjection()

        # Create rebuilder with upstream application
        rebuilder = ProjectionRebuilder(upstream_app=my_app)

        # Execute rebuild (clears read model and resets position)
        rebuilder.rebuild(projection)

        # Now start projection worker to replay all events

Rebuild Workflow:
    1. Stop projection worker (if running) - caller responsibility
    2. Clear read model via projection.clear_read_model()
    3. Reset tracking position to 0
    4. Restart projection worker - caller responsibility
    5. Events replay from beginning

Warning:
    Rebuild clears the read model completely. For zero-downtime
    rebuilds (blue-green strategy), see future implementation notes.

See Also:
    - praecepta.infra.eventsourcing.projections.base: BaseProjection class
    - praecepta.infra.eventsourcing.projections.runner: Lifecycle management
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from praecepta.infra.eventsourcing.projections.base import BaseProjection

logger = logging.getLogger(__name__)


class ProjectionRebuilder:
    """Orchestrates projection rebuild from event stream.

    Manages the rebuild workflow that prepares a projection to replay
    all events from the beginning. This involves clearing the read model
    and resetting the tracking position.

    The actual event replay happens when the projection worker is restarted
    after rebuild() completes. The worker will see position=0 and process
    all events from the notification log.

    Attributes:
        _app: Upstream application that owns the event store and tracking table.

    Warning:
        Ensure the projection worker is stopped before calling rebuild().
        Running rebuild while worker is processing can cause inconsistent state.

    Note:
        The caller is responsible for:
        1. Stopping the projection worker before rebuild
        2. Starting the projection worker after rebuild completes

    See Also:
        - BaseProjection.clear_read_model: Abstract method for clearing read model
        - ProjectionRunner: For starting/stopping projection workers
    """

    def __init__(
        self,
        upstream_app: Any,
    ) -> None:
        """Initialize rebuilder with upstream application.

        Args:
            upstream_app: Application instance that owns the event store.
                Used to access the recorder for tracking table operations.
        """
        self._app = upstream_app

    def rebuild(self, projection: BaseProjection) -> None:
        """Rebuild projection from scratch.

        Clears the read model and resets tracking position so the
        projection will replay all events from the beginning when
        the worker restarts.

        Args:
            projection: Projection instance to rebuild. Must implement
                clear_read_model() method (required by BaseProjection).

        Note:
            After calling rebuild(), start the projection worker to
            begin replaying events.

        Workflow:
            1. Clear read model via projection.clear_read_model()
            2. Reset tracking position to 0 (delete tracking record)
            3. Log completion (caller must restart worker)

        Warning:
            This operation is destructive. The read model will be empty
            until the projection worker replays all events.
        """
        projection_name = projection.name
        logger.info("Starting rebuild for projection: %s", projection_name)

        # Step 1: Clear read model
        logger.info("Clearing read model for: %s", projection_name)
        projection.clear_read_model()
        logger.info("Read model cleared for: %s", projection_name)

        # Step 2: Reset tracking position to 0
        logger.info("Resetting tracking position for: %s", projection_name)
        self._reset_tracking_position(projection_name)
        logger.info("Tracking position reset for: %s", projection_name)

        logger.info(
            "Rebuild preparation complete for: %s. Start projection worker to replay events.",
            projection_name,
        )

    def _reset_tracking_position(self, projection_name: str) -> None:
        """Reset tracking position to 0 for projection.

        Deletes the tracking record for the projection, causing it to
        start processing from notification_id=0 when the worker restarts.

        Args:
            projection_name: Name of projection in tracking table.

        Note:
            The eventsourcing library's tracking table schema is:
            tracking(application_name VARCHAR PRIMARY KEY, notification_id BIGINT)

            By deleting the tracking record, the ProcessApplication will
            create a new record starting from notification_id=0 when it
            begins processing.

            If the recorder doesn't have delete_tracking_record method,
            a warning is logged (graceful degradation for testing).
        """
        recorder = self._app.recorder
        if hasattr(recorder, "delete_tracking_record"):
            recorder.delete_tracking_record(projection_name)
        else:
            # Fallback: log warning for environments without tracking table
            logger.warning(
                "Recorder does not support delete_tracking_record for: %s. "
                "Tracking position may not be reset.",
                projection_name,
            )
