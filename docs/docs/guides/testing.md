# Testing

Praecepta uses pytest with markers to distinguish test types and `import-linter` to enforce architecture boundaries.

## Test Organization

Tests live alongside their packages:

```
packages/domain-orders/
├── src/praecepta/domain/orders/
│   └── ...
└── tests/
    ├── test_order.py           # Unit tests for the aggregate
    └── test_order_api.py       # Integration tests for endpoints
```

## Markers

Every test should be marked with its type:

```python
import pytest

@pytest.mark.unit
def test_order_can_be_placed():
    order = Order()
    order.place(order_id="ORD-1", total=Decimal("99.99"))
    assert order.order_id == "ORD-1"

@pytest.mark.integration
async def test_order_endpoint(client):
    response = await client.post("/api/v1/orders/", json={...})
    assert response.status_code == 200
```

Run filtered test suites:

```bash
make test-unit      # uv run pytest -m unit
make test-int       # uv run pytest -m integration
make test           # uv run pytest (all)
```

## Testing Aggregates

Aggregates are pure domain objects — no mocks or infrastructure needed:

```python
import pytest
from decimal import Decimal
from praecepta.foundation.domain import InvalidStateTransitionError

@pytest.mark.unit
def test_order_lifecycle():
    order = Order()

    # Place the order
    order.place(order_id="ORD-1", total=Decimal("99.99"))
    assert order.order_id == "ORD-1"
    assert not order.shipped

    # Ship it
    order.ship(tracking_number="TRACK-1")
    assert order.shipped

    # Can't ship twice
    with pytest.raises(InvalidStateTransitionError):
        order.ship(tracking_number="TRACK-2")
```

## Testing Endpoints

Use `httpx.AsyncClient` with `create_app()`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from praecepta.infra.fastapi import create_app

@pytest.fixture
def app():
    return create_app(
        # Exclude discovery to isolate tests
        exclude_groups=frozenset({
            "praecepta.middleware",
            "praecepta.lifespan",
        }),
        extra_routers=[test_router],
    )

@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.mark.integration
async def test_place_order(client):
    response = await client.post("/api/v1/orders/", json={
        "order_id": "ORD-1",
        "total": "99.99",
    })
    assert response.status_code == 200
```

## Controlling Discovery in Tests

Use `exclude_groups` and `exclude_names` to suppress auto-discovered contributions:

```python
# Suppress all middleware (for fast unit-style HTTP tests)
app = create_app(exclude_groups=frozenset({"praecepta.middleware"}))

# Suppress specific entries
app = create_app(exclude_names=frozenset({"auth", "tenant_state"}))
```

## Async Mode

Pytest async mode is set to `strict` — all async tests must be explicitly marked:

```python
@pytest.mark.integration
async def test_async_query():
    ...
```

## Architecture Boundary Tests

`import-linter` runs as part of `make verify` and ensures:

- Foundation packages don't import infrastructure frameworks
- Layer dependencies flow downward only
- Bounded contexts don't access each other's internals

```bash
make boundaries   # uv run lint-imports
```
