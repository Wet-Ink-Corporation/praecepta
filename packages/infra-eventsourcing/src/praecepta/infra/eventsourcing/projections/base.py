"""Base projection class for CQRS read models.

This module provides the foundational projection infrastructure that all
read model projections across bounded contexts will inherit from. BaseProjection
extends the eventsourcing library's lightweight ``Projection`` class (not
``ProcessApplication``) — suited for projections that write to external read
models without emitting downstream events.

Architecture Note:
    The library provides two projection paths:

    1. **Projection** (this base class): lightweight, no event store, no extra
       connection pool.  The ``process_event()`` method receives a domain event
       and a ``Tracking`` object; the handler writes to the read model and then
       calls ``self.view.insert_tracking(tracking)`` to record position.
       Used with ``ProjectionRunner``.

    2. **EventSourcedProjection / ProcessApplication**: heavyweight, gets its
       own event store and ``ProcessRecorder`` with a separate connection pool.
       Needed only when a projection must emit downstream events via
       ``processing_event.collect_events()``.
       Used with ``EventSourcedProjectionRunner``.

    All current praecepta projections only write to SQL read models — they
    never emit events.  Using ``Projection`` eliminates unnecessary connection
    pools and event store tables.

Example:
    Define a projection by subclassing BaseProjection::

        from functools import singledispatchmethod
        from praecepta.infra.eventsourcing.projections import BaseProjection

        class SummaryProjection(BaseProjection):
            '''Maintains a summary read model.'''

            upstream_application = MyApplication

            @singledispatchmethod
            def process_event(self, domain_event, tracking):
                '''Default: ignore unknown events, track position.'''
                self.view.insert_tracking(tracking)

            @process_event.register(ItemCreated)
            def _(self, event: ItemCreated, tracking):
                '''Handle ItemCreated events.'''
                self._data[str(event.originator_id)] = {
                    "title": event.title,
                    "created_at": event.timestamp,
                }
                self.view.insert_tracking(tracking)

            def clear_read_model(self) -> None:
                '''Clear all projection data for rebuild.'''
                self._data.clear()

Idempotency Requirement:
    All process_event handlers MUST be idempotent. Use UPSERT patterns or
    deduplication tables to ensure reprocessing produces the same result.

See Also:
    - praecepta.infra.eventsourcing.projections.subscription_runner: Lifecycle management
    - praecepta.infra.eventsourcing.projections.rebuilder: Rebuild utilities
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.projection import Projection

if TYPE_CHECKING:
    from eventsourcing.application import Application
    from eventsourcing.persistence import Tracking


class BaseProjection(Projection["TrackingRecorder"]):
    """Base class for all CQRS read model projections.

    Extends eventsourcing's lightweight ``Projection`` class with:
    - Abstract ``clear_read_model()`` for rebuild support
    - Upstream application declaration for correct wiring
    - Topics filtering for selective event subscription
    - Default ``process_event()`` that tracks position for unknown events

    All read model projections MUST inherit from this class and declare
    their ``upstream_application`` class attribute.

    Attributes:
        upstream_application: The Application class that produces events
            this projection consumes. Subclasses MUST set this to enable
            correct projection-to-application wiring. When ``None``, the
            projection will be skipped during auto-discovery with a warning.
        topics: Optional tuple of event topics to filter subscription.
            If empty (default), all events are delivered. Topics use format
            "module.path:ClassName" (from BaseEvent.get_topic()).

    See Also:
        - eventsourcing.projection.Projection: Library base class
        - praecepta.infra.eventsourcing.projections.subscription_runner: Lifecycle
        - praecepta.infra.eventsourcing.projections.rebuilder: Rebuild utilities
    """

    upstream_application: ClassVar[type[Application[Any]] | None] = None
    """The upstream application class that produces events this projection consumes."""

    @singledispatchmethod
    def process_event(self, domain_event: Any, tracking: Tracking) -> None:
        """Process domain event and update read model.

        Default implementation ignores unknown event types but still tracks
        position so the projection doesn't re-process the same events.
        Subclasses register handlers for specific event types using
        the ``@process_event.register`` decorator.

        After writing to the read model, each handler MUST call
        ``self.view.insert_tracking(tracking)`` to record the processed
        position.

        Args:
            domain_event: The domain event to process. Contains originator_id,
                originator_version, timestamp, and event-specific payload.
            tracking: Position tracking object. Must be passed to
                ``self.view.insert_tracking()`` after processing.

        Note:
            This method is called by the eventsourcing library's
            ``ProjectionRunner`` infrastructure. Do not call directly.
        """
        self.view.insert_tracking(tracking)

    @abstractmethod
    def clear_read_model(self) -> None:
        """Clear all data in the read model for rebuild.

        Called before replaying all events during a rebuild operation.
        Implementation should TRUNCATE or DELETE all projection data.

        This method MUST:
        - Remove all data from the projection's read model
        - Be idempotent (safe to call multiple times)
        - NOT modify the tracking table (handled by ProjectionRebuilder)

        Raises:
            NotImplementedError: If subclass does not implement this method.

        Warning:
            This method will be called during rebuild operations.
            Ensure it completely clears the read model so replayed
            events produce a consistent result.
        """
        ...
