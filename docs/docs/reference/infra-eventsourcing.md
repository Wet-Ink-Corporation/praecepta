# Infra Event Sourcing

Event store factory, base projection, projection poller, and configuration cache.

```python
from praecepta.infra.eventsourcing import (
    BaseProjection,
    EventSourcingSettings,
    EventStoreFactory,
    HybridConfigCache,
    ProjectionPoller,
    ProjectionPollingSettings,
    get_event_store,
)
```

## Key Exports

| Export | Purpose |
|--------|---------|
| `BaseProjection` | Abstract base class for event projections |
| `ProjectionPoller` | Polling-based projection runner for cross-process event consumption |
| `ProjectionPollingSettings` | Pydantic settings for poller configuration (`PROJECTION_*` env vars) |
| `EventStoreFactory` | Factory for direct event store access (rebuilds, admin queries) |
| `EventSourcingSettings` | Pydantic settings for PostgreSQL event store (`POSTGRES_*` env vars) |
| `HybridConfigCache` | Configuration cache with environment + database fallback |
| `get_event_store` | Cached singleton accessor for `EventStoreFactory` |

## Architecture Note

There are two paths to event store infrastructure:

1. **`EventStoreFactory` / `get_event_store()`** — for direct event store access outside of `Application` subclasses (projection rebuilds, admin queries, event stream inspection). Creates its own `PostgresInfrastructureFactory` lazily on first `.recorder` access.

2. **`Application[UUID]` subclasses** — each application constructs its own `InfrastructureFactory` from `os.environ` during `__init__()`. These are independent of `EventStoreFactory`.

The `event_store_lifespan` hook (priority 100) bridges `EventSourcingSettings` into `os.environ` so that `Application` subclasses receive the correct configuration (e.g. `PERSISTENCE_MODULE=eventsourcing.postgres`).

## API Reference

::: praecepta.infra.eventsourcing
