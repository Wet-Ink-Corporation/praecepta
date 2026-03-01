# Infra Event Sourcing

Event store factory, base projection, subscription runner, and configuration cache.

```python
from praecepta.infra.eventsourcing import (
    BaseProjection,
    EventSourcingSettings,
    EventStoreFactory,
    HybridConfigCache,
    SubscriptionProjectionRunner,
    get_event_store,
)
```

## Key Exports

| Export | Purpose |
|--------|---------|
| `BaseProjection` | Abstract base class for CQRS read model projections (extends `Projection`) |
| `SubscriptionProjectionRunner` | LISTEN/NOTIFY-based projection runner for real-time event delivery |
| `EventStoreFactory` | Factory for direct event store access (rebuilds, admin queries) |
| `EventSourcingSettings` | Pydantic settings for PostgreSQL event store (`POSTGRES_*` env vars) |
| `HybridConfigCache` | Configuration cache with environment + database fallback |
| `get_event_store` | Cached singleton accessor for `EventStoreFactory` |

## Architecture Note

There are two paths to event store infrastructure:

1. **`EventStoreFactory` / `get_event_store()`** — for direct event store access outside of `Application` subclasses (projection rebuilds, admin queries, event stream inspection). Creates its own `PostgresInfrastructureFactory` lazily on first `.recorder` access.

2. **`Application[UUID]` subclasses** — each application constructs its own `InfrastructureFactory` from `os.environ` during `__init__()`. These are independent of `EventStoreFactory`.

The `event_store_lifespan` hook (priority 100) bridges `EventSourcingSettings` into `os.environ` so that `Application` subclasses receive the correct configuration (e.g. `PERSISTENCE_MODULE=eventsourcing.postgres`).

### Projection Architecture

Projections use the eventsourcing library's lightweight `Projection` class (not `ProcessApplication`). This means:

- **No per-projection event store** — projections don't create their own aggregate stores or `ProcessRecorder`
- **No per-projection connection pool** — only a small `TrackingRecorder` pool for position tracking
- **Push-based delivery** — uses PostgreSQL LISTEN/NOTIFY via `ProjectionRunner`, not polling

Each `SubscriptionProjectionRunner` creates one `ProjectionRunner` per projection class. The `ProjectionRunner` manages the upstream application instance, tracking recorder, and subscription thread.

## API Reference

::: praecepta.infra.eventsourcing
