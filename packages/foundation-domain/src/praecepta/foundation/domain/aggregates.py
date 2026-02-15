"""Base aggregate classes for domain event sourcing.

This module provides the foundational aggregate infrastructure that all
domain aggregates across bounded contexts will inherit from. BaseAggregate
extends the eventsourcing library's Aggregate class with multi-tenancy support.

Example:
    >>> from praecepta.foundation.domain.aggregates import BaseAggregate
    >>> from eventsourcing.domain import event
    >>> from uuid import UUID
    >>>
    >>> class MyAggregate(BaseAggregate):
    ...     @event('Created')
    ...     def __init__(self, *, title: str, owner_id: UUID, tenant_id: str):
    ...         self.title = title
    ...         self.owner_id = owner_id
    ...         self.tenant_id = tenant_id

"""

from __future__ import annotations

from eventsourcing.domain import Aggregate


class BaseAggregate(Aggregate):
    """Base class for all domain aggregates.

    Extends eventsourcing.domain.Aggregate with:
    - Multi-tenancy via required tenant_id field
    - Consistent patterns for command methods and event handlers
    - Documentation for correct aggregate implementation

    All domain aggregates MUST inherit from this class.

    Attributes:
        tenant_id: Organizational boundary identifier (required, immutable).
            Must be set by subclass __init__ method. Format: lowercase slug,
            2-63 characters (validated at event level via BaseEvent).

    Inherited from Aggregate (eventsourcing library):
        id: Aggregate identifier (UUID, auto-generated)
        version: Current version for optimistic concurrency
        created_on: Timestamp of first event
        modified_on: Timestamp of last event

    Library Features Available:
        - @event decorator for mutator methods
        - collect_events() to retrieve pending events
        - Automatic version tracking
        - Snapshot support for long-lived aggregates

    Usage Pattern:
        Subclasses must:
        1. Decorate __init__ with @event('Created')
        2. Set self.tenant_id in __init__
        3. Use @event decorator for all state-changing methods
        4. Keep state changes within decorated methods only

    Example:
        >>> class Dog(BaseAggregate):
        ...     @event('Created')
        ...     def __init__(self, *, name: str, tenant_id: str):
        ...         self.name = name
        ...         self.tenant_id = tenant_id
        ...         self.tricks: list[str] = []
        ...
        ...     @event('TrickAdded')
        ...     def add_trick(self, trick: str) -> None:
        ...         self.tricks.append(trick)
        ...
        >>> dog = Dog(name='Fido', tenant_id='acme-corp')
        >>> dog.add_trick('roll over')
        >>> events = dog.collect_events()
        >>> len(events)
        2
        >>> dog.version
        2

    Command Pattern (with validation):
        For commands with business rule validation, use a two-method pattern:

        >>> class Resource(BaseAggregate):
        ...     def add_item_if_valid(
        ...         self, item_id: UUID, score: float
        ...     ) -> None:
        ...         '''Public command with validation.'''
        ...         if item_id in self.items:
        ...             raise ValueError("Item already exists")
        ...         self._add_item(item_id, score)
        ...
        ...     @event('ItemAdded')
        ...     def _add_item(self, item_id: UUID, score: float) -> None:
        ...         '''Private mutator that triggers event.'''
        ...         self.items[item_id] = score

    See Also:
        - eventsourcing.domain.Aggregate: Library base class
        - praecepta.foundation.domain.events.BaseEvent: Event base class

    """

    # Required multi-tenancy field - must be set by subclass __init__
    tenant_id: str

    # Note: We intentionally do NOT override __init__ here.
    # The eventsourcing library's @event decorator on subclass __init__
    # methods handles initialization and event creation. Subclasses
    # MUST set self.tenant_id in their decorated __init__ method.
