"""Base projection class for CQRS read models.

This module provides the foundational projection infrastructure that all
read model projections across bounded contexts will inherit from. BaseProjection
extends the eventsourcing library's ProcessApplication class with rebuild
capabilities, topic filtering, and standardized patterns.

Example:
    Define a projection by subclassing BaseProjection::

        from functools import singledispatchmethod
        from praecepta.infra.eventsourcing.projections import BaseProjection

        class SummaryProjection(BaseProjection):
            '''Maintains a summary read model.'''

            upstream_application = MyApplication

            @singledispatchmethod
            def policy(self, domain_event, processing_event):
                '''Default: ignore unknown events.'''
                pass

            @policy.register(ItemCreated)
            def _(self, event: ItemCreated, processing_event):
                '''Handle ItemCreated events.'''
                # UPSERT into read model (idempotent pattern)
                self._data[str(event.originator_id)] = {
                    "title": event.title,
                    "created_at": event.timestamp,
                }

            def clear_read_model(self) -> None:
                '''Clear all projection data for rebuild.'''
                self._data.clear()

Idempotency Requirement:
    All policy handlers MUST be idempotent. Use UPSERT patterns or
    deduplication tables to ensure reprocessing produces the same result.

See Also:
    - praecepta.infra.eventsourcing.projections.subscription_runner: Lifecycle management
    - praecepta.infra.eventsourcing.projections.rebuilder: Rebuild utilities
"""

from __future__ import annotations

from abc import abstractmethod
from functools import singledispatchmethod
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from eventsourcing.system import ProcessApplication

if TYPE_CHECKING:
    from eventsourcing.application import Application, ProcessingEvent
    from eventsourcing.domain import DomainEvent


class BaseProjection(ProcessApplication[UUID]):
    """Base class for all projections.

    Extends eventsourcing.system.ProcessApplication with:
    - Abstract clear_read_model() for rebuild support
    - Upstream application declaration for correct wiring
    - Name property for tracking identification
    - Topics filtering for selective event subscription

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
        - eventsourcing.system.ProcessApplication: Library base class
        - praecepta.infra.eventsourcing.projections.subscription_runner: Lifecycle
        - praecepta.infra.eventsourcing.projections.rebuilder: Rebuild utilities
    """

    upstream_application: ClassVar[type[Application[Any]] | None] = None
    """The upstream application class that produces events this projection consumes."""

    def get_projection_name(self) -> str:
        """Get unique projection name for tracking table.

        The name is used as the application_name in the tracking table
        to store the last processed notification_id. This enables each
        projection to maintain its own position independently.

        This method uses the inherited 'name' attribute from ProcessApplication.
        By default, this is the class name. Override in subclass if needed.

        Returns:
            Class name by default. Override for custom naming if multiple
            instances of the same projection class are needed.
        """
        return self.name

    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEvent,
        processing_event: ProcessingEvent[UUID],
    ) -> None:
        """Process domain event and update read model.

        Default implementation ignores unknown event types (no-op).
        Subclasses register handlers for specific event types using
        the @policy.register decorator.

        Args:
            domain_event: The domain event to process. Contains originator_id,
                originator_version, timestamp, and event-specific payload.
            processing_event: Container for tracking and reaction events.
                Use processing_event.collect_events() to emit new events
                for cross-aggregate reactions.

        Note:
            This method is called by the eventsourcing library's
            ProcessApplication infrastructure. Do not call directly.
        """
        pass  # Ignore unknown events by default

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
