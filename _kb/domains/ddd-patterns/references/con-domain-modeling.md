# Domain Modeling

## Overview

Domain modeling in this architecture centers on events, commands, and queries. Events are immutable facts; commands produce events; queries project events into read models.

## Events

Events are immutable dataclasses shared within a bounded context. They include correlation and causation IDs for distributed tracing:

```python
@dataclass(frozen=True)
class DogSchoolEvent(DomainEvent):
    """Base for all dog school events."""
    originator_id: UUID
    originator_version: int

    # Distributed tracing
    correlation_id: str | None = None  # Request/workflow ID
    causation_id: str | None = None    # Which command caused this?
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass(frozen=True)
class DogRegistered(DogSchoolEvent):
    name: str
    owner_id: UUID

@dataclass(frozen=True)
class TrickAdded(DogSchoolEvent):
    trick: str
```

## Commands

Commands are pure functions that take past events and return new events to append:

```python
@dataclass(frozen=True)
class RegisterDog(Command):
    """Register a new dog in the school."""
    name: str
    owner_id: UUID
    dog_id: UUID | None = None

    def handle(self, events: DomainEvents) -> DomainEvents:
        """Pure business logic - no side effects."""
        if len(events) > 0:
            raise DogAlreadyRegisteredError(self.dog_id)

        dog_id = self.dog_id or uuid4()
        return (
            DogRegistered(
                originator_id=dog_id,
                originator_version=1,
                name=self.name,
                owner_id=self.owner_id,
            ),
        )

    def execute(self) -> int | None:
        """Execute against store with optimistic concurrency."""
        dog_id = self.dog_id or uuid4()
        return put_events(self.handle(get_events(dog_id)))
```

## Queries with Projections

Queries project events into read models:

```python
@dataclass(frozen=True)
class ListDogs(Query):
    """List all dogs with their trick counts."""

    @staticmethod
    def projection(events: DomainEvents) -> list[DogSummary]:
        """Project events into read model."""
        dogs: dict[UUID, dict] = {}

        for event in events:
            if isinstance(event, DogRegistered):
                dogs[event.originator_id] = {
                    "id": event.originator_id,
                    "name": event.name,
                    "owner_id": event.owner_id,
                    "trick_count": 0,
                }
            elif isinstance(event, TrickAdded):
                if event.originator_id in dogs:
                    dogs[event.originator_id]["trick_count"] += 1

        return [DogSummary(**d) for d in dogs.values()]
```

## Repository Port Pattern

Repository interfaces live in domain; implementations live in infrastructure:

```python
# Domain (port)
class DogRepository(ABC):
    @abstractmethod
    async def get(self, dog_id: UUID) -> DomainEvents:
        pass

# Infrastructure (adapter)
class PostgresDogRepository(DogRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, dog_id: UUID) -> DomainEvents:
        # SQLAlchemy implementation
        ...
```

## Key Points

- Events are immutable facts with tracing metadata
- Commands are pure functions: `(past_events) -> new_events`
- Queries project events into read models
- Repository ports in domain, adapters in infrastructure

## Prerequisites

- [Architecture Layers](con-layers.md) - Where domain fits

## Related

- [Event Evolution](con-event-evolution.md) - Schema versioning
- [Neo4j Projections](con-neo4j-projection.md) - Graph projections
