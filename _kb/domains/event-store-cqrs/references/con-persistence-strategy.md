# Persistence Strategy

> Event store, projections, and data management

---

## Overview

{Project} uses Event Sourcing as its primary persistence pattern. State is stored as immutable events rather than current state, with projections materializing optimized read models.

---

## Event Store

### PostgreSQL as Event Store

The `eventsourcing` library uses PostgreSQL for reliable event storage.

> **Library-Managed Schema:** The schema below is automatically created by the eventsourcing library when initialized with `CREATE_TABLE=true`. Do not manually create these tables—let the library handle schema creation and optimistic concurrency constraints.

```sql
-- This schema is created automatically by eventsourcing.postgres.PostgresDatastore
CREATE TABLE stored_events (
    id UUID PRIMARY KEY,
    originator_id UUID NOT NULL,          -- Aggregate ID
    originator_version INTEGER NOT NULL,  -- Version for OCC
    topic VARCHAR(255) NOT NULL,          -- Event type
    state BYTEA NOT NULL,                 -- Serialized event
    recorded_at TIMESTAMPTZ DEFAULT NOW(),

    -- Optimistic concurrency control
    UNIQUE (originator_id, originator_version)
);

CREATE INDEX idx_events_originator ON stored_events (originator_id, originator_version);
CREATE INDEX idx_events_topic ON stored_events (topic);
CREATE INDEX idx_events_recorded ON stored_events (recorded_at);
```

### Event Structure

```python
from eventsourcing.domain import Aggregate, DomainEvent
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class StoredEventMetadata:
    """Metadata for all stored events."""
    correlation_id: str | None = None    # Request/workflow ID
    causation_id: str | None = None      # Parent event ID
    user_id: str | None = None           # Acting user
    tenant_id: str = ""                  # Tenant isolation
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

### Event Store Configuration

{Project} uses the `eventsourcing` library with PostgreSQL backend. Configuration is managed through Pydantic settings:

```python
from {project}.shared.infrastructure.config.eventsourcing import EventSourcingSettings
from {project}.shared.infrastructure.persistence import get_event_store

# Load configuration from environment variables
settings = EventSourcingSettings(
    postgres_dbname="{Project}_dev",
    postgres_user="{Project}_user",
    postgres_password="secure_password",
    postgres_host="localhost",
    postgres_port=5432,
    postgres_pool_size=5,
    postgres_max_overflow=10,
    create_table=True  # Auto-create tables in development
)

# Get event store factory (singleton)
factory = get_event_store()
recorder = factory.recorder  # PostgresApplicationRecorder instance
```

**Key Configuration Options:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `POSTGRES_DBNAME` | Database name | Required |
| `POSTGRES_USER` | Database user | Required |
| `POSTGRES_PASSWORD` | Database password | Required |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_POOL_SIZE` | Base connection pool size | `5` |
| `POSTGRES_MAX_OVERFLOW` | Additional burst connections | `10` |
| `CREATE_TABLE` | Auto-create tables | `true` (dev), `false` (prod) |

**DATABASE_URL Support:**

The eventsourcing library requires individual `POSTGRES_*` variables. For compatibility with tools like Alembic, `DATABASE_URL` is parsed automatically:

```python
# Alternative: Parse DATABASE_URL
factory = EventStoreFactory.from_database_url(
    "postgresql://user:pass@localhost:5432/{Project}_dev"
)
```

### Optimistic Concurrency

The eventsourcing library handles optimistic concurrency control automatically via the `UNIQUE (originator_id, originator_version)` constraint. When appending events:

```python
from eventsourcing.domain import Aggregate

class MemoryBlock(Aggregate):
    """Memory block aggregate with OCC built-in."""

    def add_entry(self, content_id: str):
        """Add content entry to block."""
        # Trigger event - version incremented automatically
        self.trigger_event(
            self.EntryAdded,
            content_id=content_id
        )

# When saving, concurrent modifications raise IntegrityError
# which the repository wraps as ConcurrencyError
```

The recorder enforces version consistency at the database level - no application-level locking required.

---

## Snapshots

### Purpose

Snapshots optimize aggregate loading for streams with many events:

| Scenario | Without Snapshots | With Snapshots |
|----------|-------------------|----------------|
| Load 100-event aggregate | Replay 100 events | Load snapshot + replay ~10 |
| Load 1000-event aggregate | Replay 1000 events | Load snapshot + replay ~50 |

### Configuration

```python
from eventsourcing.application import Application

class MemoryApplication(Application):
    # Automatic snapshots every 50 events
    snapshotting_intervals = {
        MemoryBlock: 50,
        SourceDocument: 100,
        CurationRule: 25
    }
```

### Snapshot Storage

```sql
CREATE TABLE snapshots (
    originator_id UUID PRIMARY KEY,
    originator_version INTEGER NOT NULL,
    topic VARCHAR(255) NOT NULL,
    state BYTEA NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Loading with Snapshots

```python
class SnapshotRepository:
    async def get(self, aggregate_id: UUID) -> Aggregate:
        """Load aggregate using snapshot if available."""
        # Try to load snapshot
        snapshot = await self._load_snapshot(aggregate_id)

        if snapshot:
            # Reconstruct from snapshot
            aggregate = self._deserialize(snapshot.state)
            start_version = snapshot.originator_version + 1
        else:
            # No snapshot, start from scratch
            aggregate = None
            start_version = 1

        # Load subsequent events
        events = await self._load_events(
            aggregate_id,
            from_version=start_version
        )

        # Apply events
        for event in events:
            aggregate = self._apply(aggregate, event)

        return aggregate
```

---

## Projections

### Projection Types

| Type | Consistency | Use Case |
|------|-------------|----------|
| **Synchronous** | Strong | Critical read paths |
| **Asynchronous** | Eventual | High-throughput, analytics |
| **Catch-up** | Rebuild | New projections, recovery |

### Projection Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EVENT STORE                                       │
│                        (Source of Truth)                                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Notification Log
                                   ▼
         ┌─────────────────────────────────────────────────────────┐
         │                   PROJECTION WORKERS                      │
         │                                                           │
         │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
         │  │   Summary   │  │   Vector    │  │   Graph     │      │
         │  │  Projector  │  │  Projector  │  │  Projector  │      │
         │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
         └─────────┼────────────────┼────────────────┼─────────────┘
                   │                │                │
                   ▼                ▼                ▼
            ┌──────────┐    ┌──────────┐     ┌──────────┐
            │PostgreSQL│    │ pgvector │     │  Neo4j   │
            │  Views   │    │  Index   │     │  Graph   │
            └──────────┘    └──────────┘     └──────────┘
```

<!-- Mermaid equivalent of ASCII diagram above -->

```mermaid
graph TB
    EventStore[(EVENT STORE<br/>Source of Truth)]

    EventStore -->|Notification Log| ProjectionWorkers

    subgraph ProjectionWorkers[" PROJECTION WORKERS "]
        SummaryProj[Summary<br/>Projector]
        VectorProj[Vector<br/>Projector]
        GraphProj[Graph<br/>Projector]
    end

    SummaryProj --> PostgresViews[(PostgreSQL<br/>Views)]
    VectorProj --> PgVector[(pgvector<br/>Index)]
    GraphProj --> Neo4jGraph[(Neo4j<br/>Graph)]

    classDef sourceStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:3px
    classDef workerStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef storageStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px

    class EventStore sourceStyle
    class ProjectionWorkers,SummaryProj,VectorProj,GraphProj workerStyle
    class PostgresViews,PgVector,Neo4jGraph storageStyle
```

### Synchronous Projection

Updated in same transaction as event store:

```python
class BlockSummaryProjection(SyncProjection):
    """Synchronous projection for block summaries."""

    def handle(self, event: DomainEvent, session: AsyncSession) -> None:
        match event:
            case BlockCreated():
                session.add(BlockSummaryRecord(
                    id=event.originator_id,
                    title=event.title,
                    scope_type=event.scope_type,
                    owner_id=event.owner_id,
                    entry_count=0,
                    created_at=event.timestamp
                ))

            case EntryAdded():
                session.execute(
                    update(BlockSummaryRecord)
                    .where(BlockSummaryRecord.id == event.originator_id)
                    .values(entry_count=BlockSummaryRecord.entry_count + 1)
                )

            case BlockArchived():
                session.execute(
                    delete(BlockSummaryRecord)
                    .where(BlockSummaryRecord.id == event.originator_id)
                )
```

### Asynchronous Projection

Processes events from notification log:

```python
from eventsourcing.system import ProcessApplication

class VectorProjection(ProcessApplication):
    """Async projection to vector database."""

    def __init__(self, embedder: Embedder, vector_db: VectorDB):
        super().__init__()
        self._embedder = embedder
        self._vector_db = vector_db

    @singledispatchmethod
    def policy(self, domain_event, processing_event):
        """Default: ignore unknown events."""
        pass

    @policy.register(ChunkCreated)
    async def _(self, event: ChunkCreated, processing_event):
        """Project chunk to vector index."""
        embedding = await self._embedder.embed(event.content)
        await self._vector_db.upsert(
            id=str(event.originator_id),
            vector=embedding,
            metadata={
                'document_id': str(event.document_id),
                'tenant_id': event.tenant_id,
                'acl_hash': event.acl_hash
            }
        )

    @policy.register(ChunkDeleted)
    async def _(self, event: ChunkDeleted, processing_event):
        """Remove chunk from vector index."""
        await self._vector_db.delete(str(event.originator_id))
```

### Projection Tracking

Track progress for each projection:

```sql
CREATE TABLE projection_tracking (
    projection_name VARCHAR(255) PRIMARY KEY,
    last_notification_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

```python
class ProjectionWorker:
    async def process_batch(self) -> int:
        """Process batch of notifications."""
        # Get current position
        position = await self._get_position()

        # Fetch notifications
        notifications = await self._app.notification_log.select(
            start=position + 1,
            limit=100
        )

        if not notifications:
            return 0

        # Process each event
        for notification in notifications:
            event = self._deserialize(notification)
            await self._projection.handle(event)

        # Update position
        await self._update_position(notifications[-1].id)

        return len(notifications)
```

---

## Projection Rebuild

### Rebuild Process

Projections can be rebuilt from the event stream:

```python
class ProjectionManager:
    async def rebuild(self, projection_name: str) -> None:
        """Rebuild projection from scratch."""
        projection = self._projections[projection_name]

        # 1. Clear existing data
        await projection.clear()

        # 2. Reset tracking position
        await self._db.execute(
            """
            UPDATE projection_tracking
            SET last_notification_id = 0
            WHERE projection_name = $1
            """,
            projection_name
        )

        # 3. Replay all events
        position = 0
        while True:
            notifications = await self._app.notification_log.select(
                start=position + 1,
                limit=1000
            )

            if not notifications:
                break

            for notification in notifications:
                event = self._deserialize(notification)
                await projection.handle(event)

            position = notifications[-1].id

        # 4. Update tracking
        await self._update_position(projection_name, position)
```

### Blue-Green Rebuild

For zero-downtime rebuilds:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BLUE-GREEN REBUILD                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1: Build Green                                                        │
│  ┌──────────────┐                    ┌──────────────┐                       │
│  │ Blue (Active)│◄── Queries ───────│    API       │                       │
│  │   Table      │                    └──────────────┘                       │
│  └──────────────┘                                                           │
│                                                                              │
│  ┌──────────────┐                                                           │
│  │Green (Build) │◄── Projection Worker (rebuilding)                         │
│  │   Table      │                                                           │
│  └──────────────┘                                                           │
│                                                                              │
│  Phase 2: Switch                                                             │
│  ┌──────────────┐                    ┌──────────────┐                       │
│  │Green (Active)│◄── Queries ───────│    API       │                       │
│  │   Table      │                    └──────────────┘                       │
│  └──────────────┘                                                           │
│                                                                              │
│  ┌──────────────┐                                                           │
│  │ Blue (Drop)  │    (Cleanup)                                              │
│  └──────────────┘                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

<!-- Mermaid equivalent of ASCII diagram above -->

```mermaid
graph TB
    subgraph phase1["Phase 1: Build Green"]
        API1[API]
        Blue1[Blue Table<br/>Active]
        Green1[Green Table<br/>Building]
        Worker1[Projection Worker<br/>rebuilding]

        API1 -->|Queries| Blue1
        Worker1 -->|Building| Green1
    end

    subgraph phase2["Phase 2: Switch"]
        API2[API]
        Green2[Green Table<br/>Active]
        Blue2[Blue Table<br/>Drop]

        API2 -->|Queries| Green2
    end

    phase1 -.switch.-> phase2

    classDef activeStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef buildStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef dropStyle fill:#ffebee,stroke:#c62828,stroke-width:2px,stroke-dasharray: 5 5

    class Blue1,Green2 activeStyle
    class Green1 buildStyle
    class Blue2 dropStyle
```

---

## Multi-Store Strategy

### Store Allocation

| Store | Data | Purpose |
|-------|------|---------|
| **PostgreSQL** | Events, snapshots, summaries | Source of truth, ACID |
| **pgvector** | Chunk embeddings | Semantic search |
| **ParadeDB** | Chunk text | BM25 keyword search |
| **Neo4j** | Entities, relationships | Graph traversal |
| **Redis** | Sessions, rate limits | Caching, ephemeral |

### Consistency Model

| Read Model | Consistency | Acceptable Lag |
|------------|-------------|----------------|
| Block summaries | Strong (sync) | 0ms |
| Vector index | Eventual | 1-2 seconds |
| BM25 index | Eventual | 1-2 seconds |
| Knowledge graph | Eventual | 5-10 seconds |

---

## Event Versioning

### Upcasting Strategy

Transform old events to current schema at read time:

```python
class EventUpcaster:
    """Transform old event versions to current schema."""

    def upcast(self, topic: str, state: dict) -> dict:
        """Apply upcasting transformations."""
        match topic:
            case "BlockCreatedV1":
                # V1 didn't have tenant_id
                return {
                    **state,
                    'tenant_id': self._lookup_tenant(state['owner_id'])
                }

            case "EntryAddedV1":
                # V1 used 'content_ref' instead of separate fields
                content_ref = state.pop('content_ref')
                return {
                    **state,
                    'content_type': content_ref['type'],
                    'content_id': content_ref['id']
                }

            case _:
                return state
```

### Schema Evolution Rules

| Change Type | Strategy | Example |
|-------------|----------|---------|
| Add optional field | Default value | `tags: list = []` |
| Add required field | Upcast with lookup | `tenant_id` from owner |
| Rename field | Upcast transformation | `content_ref` → `content_type` + `content_id` |
| Remove field | Ignore in deserializer | Old fields ignored |
| Change type | Upcast conversion | String → Enum |

---

## Backup and Recovery

### Event Store Backup

```bash
# Daily backup of event store
pg_dump -h $DB_HOST -U $DB_USER -d {Project} \
  --table=stored_events \
  --table=snapshots \
  --table=projection_tracking \
  -F c -f backup_$(date +%Y%m%d).dump
```

### Point-in-Time Recovery

Events enable temporal recovery:

```python
class TemporalRepository:
    async def get_as_of(
        self,
        aggregate_id: UUID,
        as_of: datetime
    ) -> Aggregate:
        """Load aggregate state as of specific time."""
        events = await self._db.fetch(
            """
            SELECT * FROM stored_events
            WHERE originator_id = $1 AND recorded_at <= $2
            ORDER BY originator_version
            """,
            aggregate_id, as_of
        )

        aggregate = None
        for event_record in events:
            event = self._deserialize(event_record['state'])
            aggregate = self._apply(aggregate, event)

        return aggregate
```

### Projection Recovery

```bash
# Recover specific projection
python -m {Project}.projections rebuild --projection=vector_index

# Recover all projections
python -m {Project}.projections rebuild --all
```

---

## Performance Considerations

### Event Store Indexes

```sql
-- For aggregate loading
CREATE INDEX idx_events_originator ON stored_events
    (originator_id, originator_version);

-- For notification log
CREATE INDEX idx_events_id ON stored_events (id);

-- For time-based queries
CREATE INDEX idx_events_recorded ON stored_events (recorded_at);

-- For projection filtering
CREATE INDEX idx_events_topic ON stored_events (topic);
```

### Batch Operations

```python
class BatchEventStore:
    async def append_batch(
        self,
        aggregates: list[tuple[UUID, list[DomainEvent], int]]
    ) -> None:
        """Batch append for high throughput."""
        async with self._db.transaction():
            for aggregate_id, events, expected_version in aggregates:
                await self._append_single(
                    aggregate_id, events, expected_version
                )
```

---

## Redis Configuration

Redis is used for caching, task queue broker (TaskIQ), and session storage.

### Configuration Settings

```python
from {project}.shared.infrastructure.config.redis import RedisSettings

# Load from environment variables
settings = RedisSettings()
url = settings.get_url()  # redis://localhost:6379/0

# Or parse from URL
settings = RedisSettings.from_url("redis://myhost:6380/1")
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `REDIS_URL` | Full connection URL (takes precedence) | None |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_DB` | Database number (0-15) | `0` |
| `REDIS_PASSWORD` | Optional password (hidden in logs) | None |
| `REDIS_POOL_SIZE` | Maximum connections in pool | `10` |
| `REDIS_SOCKET_TIMEOUT` | Socket timeout in seconds | `5.0` |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | Connection timeout in seconds | `5.0` |

### URL Format

```
redis://[password@]host:port/db
redis://:mypassword@localhost:6379/0
redis://localhost:6379/0
```

### Usage with TaskIQ

Redis Stream is used as the TaskIQ broker for reliable message delivery:

```python
from {project}.shared.infrastructure.taskiq import broker

@broker.task
async def my_background_task(arg: str) -> str:
    return f"processed {arg}"

# Enqueue
await my_background_task.kiq("value")
```

See [PADR-005: TaskIQ](../../decisions/strategic/PADR-005-task-queue.md) for architecture decision.

### Health Checks

```python
from {project}.shared.infrastructure.persistence.redis import get_redis_client

async def check_redis_health() -> bool:
    client = await get_redis_client()
    return await client.ping()
```

---

## See Also

- [Domain Model](con-domain-model.md) - Aggregate and event design
- [PADR-001: Event Sourcing](../../decisions/strategic/PADR-001-event-sourcing.md)
- [PADR-005: TaskIQ](../../decisions/strategic/PADR-005-task-queue.md) - Task queue decision
- [Event Flow](proc-event-flow.md)
