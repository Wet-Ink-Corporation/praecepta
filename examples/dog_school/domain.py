"""Dog School domain model — aggregate and exceptions.

Demonstrates BaseAggregate usage with the two-method command pattern:
public methods validate, private @event-decorated methods mutate state.
"""

from __future__ import annotations

from eventsourcing.domain import event

from praecepta.foundation.domain import BaseAggregate, NotFoundError, ValidationError


class Dog(BaseAggregate):
    """A dog that can learn tricks.

    Example:
        >>> dog = Dog(name="Fido", tenant_id="acme-corp")
        >>> dog.add_trick("sit")
        >>> dog.tricks
        ['sit']
    """

    @event("Registered")
    def __init__(self, *, name: str, tenant_id: str) -> None:
        self.name = name
        self.tenant_id = tenant_id
        self.tricks: list[str] = []

    def add_trick(self, trick: str) -> None:
        """Teach the dog a new trick.

        Raises:
            ValidationError: If the dog already knows this trick.
        """
        if trick in self.tricks:
            raise ValidationError("trick", f"Dog already knows '{trick}'")
        self._add_trick(trick)

    @event("TrickAdded")
    def _add_trick(self, trick: str) -> None:
        self.tricks.append(trick)


class DogNotFoundError(NotFoundError):
    """Raised when a dog cannot be found by ID."""

    def __init__(self, dog_id: str) -> None:
        super().__init__("Dog", dog_id)
