# Build a Projection

Projections transform event streams into read-optimized views (read models). They subscribe to events from an upstream application and maintain materialized state in SQL tables.

## The Pattern

Projections extend `BaseProjection` and implement `process_event()` to handle domain events:

```python
from typing import Any, ClassVar

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.persistence import Tracking, TrackingRecorder

from praecepta.infra.eventsourcing import BaseProjection
from my_app.application import OrderApplication


class OrderSummaryProjection(BaseProjection):
    """Materializes order events into an order_summaries read model."""

    upstream_application: ClassVar[type[Any]] = OrderApplication

    topics: ClassVar[tuple[str, ...]] = (
        "my_app.order:Order.Placed",
        "my_app.order:Order.Shipped",
    )

    def __init__(
        self,
        view: TrackingRecorder,
        repository: OrderSummaryRepository | None = None,
    ) -> None:
        super().__init__(view=view)
        if repository is None:
            repository = OrderSummaryRepository(...)
        self._repo = repository

    @singledispatchmethod
    def process_event(self, domain_event: Any, tracking: Tracking) -> None:
        """Default: ignore unknown events, track position."""
        event_name = domain_event.__class__.__name__
        if event_name == "Placed":
            self._handle_placed(domain_event)
        elif event_name == "Shipped":
            self._handle_shipped(domain_event)
        self.view.insert_tracking(tracking)

    def _handle_placed(self, event: Any) -> None:
        self._repo.upsert(
            order_id=str(event.originator_id),
            tenant_id=str(event.tenant_id),
            total=event.total,
            status="placed",
        )

    def _handle_shipped(self, event: Any) -> None:
        self._repo.update_status(
            order_id=str(event.originator_id),
            status="shipped",
            tracking_number=event.tracking_number,
        )

    def clear_read_model(self) -> None:
        self._repo.truncate()
```

### Key Requirements

1. **`upstream_application`** — declares which `Application` class produces events this projection consumes. Required for auto-discovery wiring.

2. **`topics`** — optional tuple of event topic strings to filter which events are delivered. Format: `"module.path:ClassName.EventName"`. If omitted, all events from the upstream application are delivered.

3. **`process_event(self, domain_event, tracking)`** — called by the framework for each event. After writing to the read model, you **must** call `self.view.insert_tracking(tracking)` to record the processed position.

4. **`clear_read_model()`** — abstract method called during rebuilds. Must delete all projection data (TRUNCATE or DELETE).

5. **Constructor** — receives a `view: TrackingRecorder` parameter (the framework's position tracker). Pass it to `super().__init__(view=view)`.

### Event Routing

The eventsourcing library creates event classes dynamically via the `@event` decorator, so standard `singledispatch` registration by type doesn't work. Instead, route events by class name:

```python
@singledispatchmethod
def process_event(self, domain_event: Any, tracking: Tracking) -> None:
    event_name = domain_event.__class__.__name__
    if event_name == "Placed":
        self._handle_placed(domain_event)
    elif event_name == "Shipped":
        self._handle_shipped(domain_event)
    self.view.insert_tracking(tracking)
```

### Idempotency Requirement

All handlers **must** be idempotent. Use UPSERT patterns (INSERT ON CONFLICT UPDATE) so that replaying events during rebuilds produces the same result. The tracking position and read model writes are in separate transactions — if the process crashes between them, the event will be reprocessed on restart.

## The `clear_read_model` Contract

Every projection must implement `clear_read_model()`. This method is called by `ProjectionRebuilder` when a projection needs to be rebuilt from scratch (e.g. after a schema change or logic fix):

```python
def clear_read_model(self) -> None:
    with self._session_factory() as session:
        session.execute(text("TRUNCATE TABLE order_summaries"))
        session.commit()
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

At startup, the `projection_runner_lifespan` hook (priority 200) discovers all registered projections, groups them by `upstream_application`, and creates a `SubscriptionProjectionRunner` for each application group. Each runner:

1. Creates a `ProjectionRunner` per projection, which instantiates one upstream `Application` and one `PostgresTrackingRecorder` (view)
2. Uses PostgreSQL **LISTEN/NOTIFY** for push-based event delivery — no polling
3. Each projection tracks its own position via the tracking recorder, resuming where it left off after a restart

### Connection Pool Budget

Each `ProjectionRunner` creates two connection pools: one for the upstream application (reads events) and one for the tracking recorder (writes position). The projection lifespan uses smaller pool sizes for these (default: pool_size=2, max_overflow=3) since they handle minimal traffic.

At startup, the framework logs an estimated connection budget and warns if the total exceeds `POSTGRES_MAX_CONNECTIONS`:

```text
Connection pool budget: 3 API app(s) (24 max conn) + 4 projection(s) x 2 pools (40 max conn) = 64 estimated total
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PROJECTION_POOL_SIZE` | `2` | Pool size for projection upstream apps and tracking recorders |
| `POSTGRES_PROJECTION_MAX_OVERFLOW` | `3` | Max overflow for projection pools |
| `MAX_PROJECTION_RUNNERS` | `8` | Maximum number of projection runners (caps discovered projections) |

## Projection Execution Model

Projections run synchronously (`def`, not `async def`). This follows the sync-first event sourcing strategy — events are processed in order, and projections must not introduce concurrency that could cause out-of-order updates.

## Testing Projections

Test projections by constructing them with a mock view and repository:

```python
from unittest.mock import MagicMock

def test_order_summary_upserts_on_placed() -> None:
    mock_repo = MagicMock()
    mock_view = MagicMock()
    projection = OrderSummaryProjection(view=mock_view, repository=mock_repo)

    event = MagicMock()
    event.__class__ = type("Placed", (), {})
    event.__class__.__name__ = "Placed"
    event.originator_id = uuid4()
    event.tenant_id = "acme-corp"
    event.total = Decimal("99.99")

    projection.process_event(event, MagicMock())

    mock_repo.upsert.assert_called_once()
    call_kwargs = mock_repo.upsert.call_args.kwargs
    assert call_kwargs["status"] == "placed"
```
