# Build a Projection

Projections transform event streams into read-optimized views (read models). They subscribe to events and maintain materialized state.

## The Pattern

Projections extend `BaseProjection` and define handler methods for each event type:

```python
from praecepta.infra.eventsourcing import BaseProjection
from my_app.events import OrderPlaced, OrderShipped

class OrderSummaryProjection(BaseProjection):
    def handle_order_placed(self, event: OrderPlaced) -> None:
        # Insert or update a read model table
        self.execute(
            "INSERT INTO order_summaries (order_id, tenant_id, total, status) "
            "VALUES (:order_id, :tenant_id, :total, 'placed')",
            order_id=event.order_id,
            tenant_id=str(event.tenant_id),
            total=event.total,
        )

    def handle_order_shipped(self, event: OrderShipped) -> None:
        self.execute(
            "UPDATE order_summaries SET status = 'shipped', "
            "tracking_number = :tracking WHERE order_id = :order_id",
            tracking=event.tracking_number,
            order_id=event.order_id,
        )
```

## Handler Naming

Handler methods follow the convention `handle_{snake_case_event_name}`:

| Event Class | Handler Method |
|-------------|---------------|
| `OrderPlaced` | `handle_order_placed` |
| `TenantCreated` | `handle_tenant_created` |
| `UserDeactivated` | `handle_user_deactivated` |

## Multi-Tenancy Requirement

Every projection table **must** include a `tenant_id` column for Row-Level Security (RLS). This is a framework invariant:

```sql
CREATE TABLE order_summaries (
    order_id TEXT PRIMARY KEY,
    tenant_id UUID NOT NULL,    -- Required for RLS
    total NUMERIC NOT NULL,
    status TEXT NOT NULL
);
```

## The `clear_read_model` Contract

Every projection must implement `clear_read_model()`. This method drops and recreates the projection's read model tables. It is called by `ProjectionRebuilder` when a projection needs to be rebuilt from scratch (e.g. after a schema change or logic fix):

```python
class OrderSummaryProjection(BaseProjection):
    def clear_read_model(self) -> None:
        self.execute("DELETE FROM order_summaries")

    # ... handlers
```

## Registering Projections

Register projections via entry points in `pyproject.toml`:

```toml
[project.entry-points."praecepta.projections"]
order_summary = "my_app.projections:OrderSummaryProjection"
```

You also need to register the upstream application(s) that produce events:

```toml
[project.entry-points."praecepta.applications"]
orders = "my_app.application:OrderApplication"
```

The framework discovers both projections and applications at startup and wires them together automatically.

## How Projections Run

At startup, the `projection_runner_lifespan` hook (priority 200) discovers all registered projections and applications, then creates a `ProjectionPoller` for each application. Each poller:

1. Creates an internal eventsourcing `System` that wires projections to the upstream application
2. Starts a **background polling thread** that periodically calls `pull_and_process()` on each projection
3. `pull_and_process()` reads new events from the shared **PostgreSQL notification log** and processes them through the projection's handler methods
4. Each projection tracks its own position in the notification log, so it resumes where it left off after a restart

This polling-based approach works correctly in production where the API process writes events and the projection runner reads them from the shared database — they do not need to be in the same process or share application instances.

### Configuring the Poller

The polling behaviour is controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECTION_POLL_INTERVAL` | `1.0` | Seconds between poll cycles (0.1–60) |
| `PROJECTION_POLL_TIMEOUT` | `10.0` | Max seconds for graceful shutdown (1–120) |
| `PROJECTION_POLL_ENABLED` | `true` | Set to `false` to disable projection processing |

For most deployments the defaults are fine. Lower the poll interval if you need faster eventual consistency; raise it to reduce database polling overhead.

## Projection Execution Model

Projections run synchronously (`def`, not `async def`). This follows the sync-first event sourcing strategy (PADR-109) — events are processed in order, and projections must not introduce concurrency that could cause out-of-order updates.

## Testing Projections

Test projections by feeding them events directly:

```python
def test_order_summary_projection(db_session):
    projection = OrderSummaryProjection(session=db_session)

    projection.handle_order_placed(OrderPlaced(
        order_id="ORD-1",
        tenant_id=TenantId("..."),
        total=Decimal("99.99"),
    ))

    result = db_session.execute(
        "SELECT status FROM order_summaries WHERE order_id = 'ORD-1'"
    ).fetchone()
    assert result.status == "placed"
```
