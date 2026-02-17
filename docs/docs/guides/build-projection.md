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

## Registering Projections

Register projections via entry points in `pyproject.toml`:

```toml
[project.entry-points."praecepta.projections"]
order_summary = "my_app.projections:OrderSummaryProjection"
```

The framework discovers and runs projections automatically.

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
