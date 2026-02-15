# Event Flow

> Command → Events → Projections

---

## Overview

{Project} uses Event Sourcing with CQRS. All state changes are captured as immutable events. Commands validate and produce events; projections consume events to build read models.

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ COMMAND │──►│VALIDATE │──►│ STORE   │──►│ PROJECT │──►│ NOTIFY  │
│         │   │         │   │ EVENTS  │   │         │   │         │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
                  │              │              │              │
                  ▼              ▼              ▼              ▼
             Business       PostgreSQL     Read Models   Downstream
             rules          Event Store    (indexes)     Contexts
```

---

## Command Processing

### Command Structure

```python
@dataclass(frozen=True)
class CreateBlock(Command):
    """Create a new memory block."""
    title: str
    scope_type: ScopeType
    scope_id: UUID
    owner_id: UUID
    tenant_id: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    block_id: UUID = field(default_factory=uuid4)

    def handle(self, events: DomainEvents) -> DomainEvents:
        """Pure function: past events → new events."""
        # Validate business rules
        if len(events) > 0:
            raise BlockAlreadyExistsError(self.block_id)

        # Produce new events
        return (BlockCreated(
            originator_id=self.block_id,
            originator_version=1,
            title=self.title,
            scope_type=self.scope_type.value,
            scope_id=self.scope_id,
            owner_id=self.owner_id,
            tags=self.tags,
            tenant_id=self.tenant_id,
            correlation_id=get_correlation_id(),
            causation_id=get_causation_id(),
        ),)
```

### Key Properties

| Property | Description |
|----------|-------------|
| **Immutable** | Commands are frozen dataclasses |
| **Pure** | `handle()` has no side effects |
| **Testable** | Test without mocks: `cmd.handle(past_events) → new_events` |
| **ID Generation** | IDs generated in command (deterministic testing) |

---

## Event Structure

### Base Event

```python
@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    originator_id: UUID           # Aggregate ID
    originator_version: int       # Version number
    correlation_id: str | None    # Request/workflow ID
    causation_id: str | None      # Parent event ID
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tenant_id: str = ""           # Multi-tenant isolation

@dataclass(frozen=True)
class MemoryEvent(DomainEvent):
    """Base for Memory context events."""
    pass

@dataclass(frozen=True)
class BlockCreated(MemoryEvent):
    """Emitted when a block is created."""
    title: str
    scope_type: str
    scope_id: UUID
    owner_id: UUID
    tags: tuple[str, ...]
```

### Event Properties

| Property | Purpose |
|----------|---------|
| `originator_id` | Links event to aggregate |
| `originator_version` | Optimistic concurrency control |
| `correlation_id` | Traces entire workflow/request |
| `causation_id` | Links to triggering event |
| `timestamp` | When event occurred |
| `tenant_id` | Multi-tenant isolation |

---

## Event Store

### PostgreSQL Schema

```sql
CREATE TABLE stored_events (
    id                BIGSERIAL PRIMARY KEY,
    originator_id     UUID NOT NULL,
    originator_version INT NOT NULL,
    topic             TEXT NOT NULL,
    state             BYTEA NOT NULL,
    timestamp         TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (originator_id, originator_version)
);

CREATE INDEX idx_events_originator ON stored_events(originator_id);
CREATE INDEX idx_events_topic ON stored_events(topic);
CREATE INDEX idx_events_timestamp ON stored_events(timestamp);
```

### Notification Log

For cross-context event distribution:

```sql
CREATE TABLE notification_log (
    id              BIGSERIAL PRIMARY KEY,
    notification_id UUID NOT NULL,
    topic           TEXT NOT NULL,
    state           BYTEA NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_topic ON notification_log(topic);
```

---

## Event Flow Sequence

### Command Execution

```
┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  API   │  │  Handler │  │ Aggregate│  │  Event   │  │Notification│
│        │  │          │  │          │  │  Store   │  │   Log    │
└───┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
    │            │             │             │             │
    │ POST /blocks             │             │             │
    │───────────►│             │             │             │
    │            │             │             │             │
    │            │ validate    │             │             │
    │            │────────────►│             │             │
    │            │             │             │             │
    │            │ load events │             │             │
    │            │─────────────────────────►│             │
    │            │             │             │             │
    │            │ past events │             │             │
    │            │◄─────────────────────────│             │
    │            │             │             │             │
    │            │ cmd.handle(events)        │             │
    │            │────────────►│             │             │
    │            │             │             │             │
    │            │ new_events  │             │             │
    │            │◄────────────│             │             │
    │            │             │             │             │
    │            │ store events│             │             │
    │            │─────────────────────────►│             │
    │            │             │             │             │
    │            │             │ append to log             │
    │            │             │─────────────────────────►│
    │            │             │             │             │
    │ 201 Created│             │             │             │
    │◄───────────│             │             │             │
    │            │             │             │             │
```

### Aggregate Reconstruction

```python
class MemoryBlockRepository:
    """Event-sourced aggregate repository."""

    async def get(self, block_id: UUID) -> MemoryBlock | None:
        # 1. Load all events for this aggregate
        events = await self.event_store.get_events(
            originator_id=block_id
        )

        if not events:
            return None

        # 2. Reconstruct aggregate state
        return MemoryBlock.from_events(events)

    async def save(
        self,
        block: MemoryBlock,
        new_events: tuple[DomainEvent, ...],
    ) -> None:
        # 1. Store new events
        await self.event_store.append(
            originator_id=block.id,
            expected_version=block.version,
            events=new_events,
        )

        # 2. Append to notification log
        for event in new_events:
            await self.notification_log.append(event)
```

---

## Projection Processing

### Projection Pattern

```python
class BlockSummaryProjection(Projection[BlockSummaryView]):
    """Projects block events to summary read model."""

    name = "block_summary"
    topics = (
        get_topic(BlockCreated),
        get_topic(BlockArchived),
        get_topic(EntryAdded),
        get_topic(EntryRemoved),
    )

    @singledispatchmethod
    def process_event(self, event, tracking) -> None:
        """Dispatch by event type."""
        pass

    @process_event.register
    def _(self, event: BlockCreated, tracking) -> None:
        self.view.create(
            block_id=event.originator_id,
            title=event.title,
            scope_type=event.scope_type,
            owner_id=event.owner_id,
            tags=list(event.tags),
            entry_count=0,
            created_at=event.timestamp,
            tracking=tracking,
        )

    @process_event.register
    def _(self, event: EntryAdded, tracking) -> None:
        self.view.increment_entry_count(
            block_id=event.originator_id,
            tracking=tracking,
        )

    @process_event.register
    def _(self, event: BlockArchived, tracking) -> None:
        self.view.mark_archived(
            block_id=event.originator_id,
            archived_at=event.timestamp,
            tracking=tracking,
        )
```

### Projection Runner

```python
from eventsourcing.projection import ProjectionRunner

# Run as separate process for scalability
with ProjectionRunner(
    application_class=MemoryApplication,
    projection_class=BlockSummaryProjection,
    view_class=PostgresBlockSummaryView,
) as runner:
    runner.run_forever()
```

### Tracking Records

Ensure exactly-once processing:

```python
class TrackingView:
    """Base for views with exactly-once processing."""

    async def upsert_with_tracking(
        self,
        tracking: TrackingRecord,
        **data,
    ) -> None:
        # Tracking insert fails on duplicate → idempotent
        async with self.db.transaction():
            await self._insert_tracking(tracking)
            await self._upsert_data(**data)
```

---

## Cross-Context Events

### Event Distribution

```
┌─────────────────────────────────────────────────────────────────────┐
│                      INGESTION CONTEXT                               │
│                                                                      │
│  DocumentIngested event stored                                       │
│          │                                                           │
│          ▼                                                           │
│  Notification Log appended                                           │
│                                                                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           │  (Async polling)
           │
    ┌──────┴──────┬──────────────┬──────────────┐
    │             │              │              │
    ▼             ▼              ▼              ▼
┌────────┐  ┌────────┐    ┌────────┐    ┌────────┐
│ Query  │  │ Graph  │    │Memory  │    │Curation│
│Context │  │Context │    │Context │    │Context │
│        │  │        │    │        │    │        │
│Update  │  │Create  │    │(React  │    │(Match  │
│indexes │  │entities│    │if rule)│    │rules)  │
└────────┘  └────────┘    └────────┘    └────────┘
```

### Process Application

```python
class EntityExtractionProcessor(ProcessApplication):
    """Processes Ingestion events for Graph context."""

    @singledispatchmethod
    def policy(self, domain_event, processing_event):
        """Route events to handlers."""
        pass

    @policy.register
    def _(self, event: EntityExtracted, processing_event):
        # Find or create entity
        existing = self._find_entity(event.name, event.entity_type)

        if existing:
            # Add mention to existing entity
            processing_event.collect_events(
                EntityMentioned(
                    originator_id=existing.id,
                    document_id=event.document_id,
                    confidence=event.confidence,
                )
            )
        else:
            # Create new entity
            processing_event.collect_events(
                EntityCreated(
                    originator_id=uuid4(),
                    name=event.name,
                    entity_type=event.entity_type,
                    tenant_id=event.tenant_id,
                )
            )

    @policy.register
    def _(self, event: RelationshipExtracted, processing_event):
        # Create relationship in graph
        processing_event.collect_events(
            RelationshipCreated(
                originator_id=uuid4(),
                source_id=event.source_entity_id,
                target_id=event.target_entity_id,
                relationship_type=event.relationship_type,
            )
        )
```

---

## System Topology

### Pipe Configuration

```python
from eventsourcing.system import System

system = System(pipes=[
    # Ingestion publishes to multiple consumers
    [IngestionApplication, QueryIndexProcessor],
    [IngestionApplication, GraphProcessor],
    [IngestionApplication, CurationProcessor],

    # Memory events for curation
    [MemoryApplication, CurationProcessor],

    # Graph events for query
    [GraphApplication, QueryGraphProcessor],
])
```

### Running Modes

| Mode | Class | Use Case |
|------|-------|----------|
| **Development** | `SingleThreadedRunner` | Synchronous, immediate |
| **Production** | `MultiThreadedRunner` | Concurrent, eventual |

```python
from eventsourcing.system import SingleThreadedRunner, MultiThreadedRunner

# Development
with SingleThreadedRunner(system) as runner:
    runner.get(IngestionApplication).sync_document(...)

# Production
with MultiThreadedRunner(system) as runner:
    runner.start()
    # Events processed asynchronously
```

---

## Consistency Model

### Eventual Consistency

| Aspect | Behavior |
|--------|----------|
| **Command side** | Strongly consistent within aggregate |
| **Read side** | Eventually consistent projections |
| **Cross-context** | Eventually consistent via notification log |

### Lag Tolerance

| Projection | Typical Lag | Max Acceptable |
|------------|-------------|----------------|
| Search indexes | < 5s | 30s |
| Block summaries | < 1s | 10s |
| Graph updates | < 10s | 60s |

### Handling Lag

```python
class QueryHandler:
    """Handles potential projection lag."""

    async def search(self, query: SearchQuery) -> SearchResults:
        results = await self.projection.search(query)

        if query.require_fresh:
            # For critical queries, verify against event store
            results = await self._verify_freshness(results)

        return results
```

---

## Error Handling

### Command Failures

| Error Type | HTTP Status | Recovery |
|------------|-------------|----------|
| `AggregateNotFoundError` | 404 | N/A |
| `BusinessRuleViolationError` | 422 | Fix input |
| `ConcurrencyError` | 409 | Retry with fresh version |
| `ValidationError` | 422 | Fix input |

### Projection Failures

| Error Type | Behavior |
|------------|----------|
| Transient (DB timeout) | Retry with backoff |
| Permanent (bad event) | Dead-letter, alert |
| Schema mismatch | Upcast event |

---

## Observability

### Metrics

| Metric | Type | Purpose |
|--------|------|---------|
| `events_stored_total` | Counter | Events written |
| `events_processed_total` | Counter | Projection events processed |
| `projection_lag_seconds` | Gauge | Time behind event store |
| `command_duration_seconds` | Histogram | Command processing time |

### Traces

```
command.create_block
├── repository.load_events
├── aggregate.handle
├── event_store.append
└── notification_log.append

projection.block_summary
├── poll_notification_log
├── process_event
│   └── view.upsert
└── tracking.record
```

---

## See Also

- [Architecture Patterns](../04-solution-strategy/con-architecture-patterns.md) - Event Sourcing, CQRS
- [Memory Context](../05-building-blocks/bounded-contexts/con-memory-context.md)
- [Glossary: Event Sourcing](../12-glossary/ref-glossary.md#event-sourcing)
