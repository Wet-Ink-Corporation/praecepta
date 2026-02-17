# Quick Start

This guide walks you through creating a minimal praecepta application with event sourcing and a REST API.

## 1. Create Your Project

```bash
mkdir my-app && cd my-app
uv init
uv add praecepta
```

## 2. Define Domain Events

Events are immutable facts about things that happened. They use past-tense naming.

```python
# my_app/events.py
from decimal import Decimal
from praecepta.foundation.domain import BaseEvent, TenantId

class OrderPlaced(BaseEvent):
    order_id: str
    tenant_id: TenantId
    total: Decimal

class OrderShipped(BaseEvent):
    order_id: str
    tenant_id: TenantId
    tracking_number: str
```

## 3. Define an Aggregate

Aggregates are the consistency boundaries in your domain. They use `trigger_event()` to record events and `apply_*` methods to update state.

```python
# my_app/aggregate.py
from decimal import Decimal
from praecepta.foundation.domain import BaseAggregate

from my_app.events import OrderPlaced, OrderShipped

class Order(BaseAggregate):
    order_id: str = ""
    total: Decimal = Decimal("0")
    shipped: bool = False

    def place(self, order_id: str, total: Decimal) -> None:
        self.trigger_event(OrderPlaced, order_id=order_id, total=total)

    def ship(self, tracking_number: str) -> None:
        if self.shipped:
            raise ValueError("Order already shipped")
        self.trigger_event(OrderShipped, tracking_number=tracking_number)

    # Apply methods update state from events
    def apply_order_placed(self, event: OrderPlaced) -> None:
        self.order_id = event.order_id
        self.total = event.total

    def apply_order_shipped(self, event: OrderShipped) -> None:
        self.shipped = True
```

## 4. Create the Application

The app factory auto-discovers all installed praecepta packages and wires them together.

```python
# my_app/main.py
from praecepta.infra.fastapi import create_app, AppSettings

app = create_app(settings=AppSettings(title="My Order Service"))
```

## 5. Run It

```bash
uv run uvicorn my_app.main:app --reload
```

Visit `http://localhost:8000/docs` to see the auto-generated OpenAPI documentation.

## What Just Happened?

When you called `create_app()`, the framework:

1. Discovered all installed praecepta packages via Python entry points
2. Registered their routers, middleware, error handlers, and lifespan hooks
3. Sorted middleware by priority (outermost first)
4. Created a FastAPI application with everything wired together

No manual registration required. Install a package, and it activates.

## Next Steps

- [Core Concepts](concepts.md) — understand the architecture
- [Define an Aggregate](../guides/define-aggregate.md) — deep dive into the aggregate pattern
- [Create a Domain Package](../guides/create-domain-package.md) — build a reusable bounded context
