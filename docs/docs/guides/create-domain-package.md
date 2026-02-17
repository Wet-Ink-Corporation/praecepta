# Create a Domain Package

This guide walks you through creating a new domain package — a reusable bounded context that plugs into any praecepta application via entry-point auto-discovery.

## 1. Create the Directory Structure

```bash
mkdir -p packages/domain-orders/src/praecepta/domain/orders
mkdir -p packages/domain-orders/tests
```

```
packages/domain-orders/
├── pyproject.toml
├── src/
│   └── praecepta/                    # NO __init__.py (namespace)
│       └── domain/                   # NO __init__.py (namespace)
│           └── orders/               # Leaf package
│               ├── __init__.py       # Public API
│               └── py.typed          # PEP 561 marker
└── tests/
    └── test_orders.py
```

!!! warning "Namespace Package Rule"
    Do **not** add `__init__.py` to `src/praecepta/` or `src/praecepta/domain/`. Only the leaf directory (`orders/`) gets one. See [Namespace Packages](../architecture/namespace-packages.md).

## 2. Write `pyproject.toml`

```toml
[project]
name = "praecepta-domain-orders"
version = "0.1.0"
description = "Order management bounded context for praecepta"
requires-python = ">=3.12"
dependencies = [
    "praecepta-foundation-domain",
    "praecepta-foundation-application",
    "praecepta-infra-eventsourcing",
]

[tool.uv.sources]
praecepta-foundation-domain = { workspace = true }
praecepta-foundation-application = { workspace = true }
praecepta-infra-eventsourcing = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/praecepta"]

# Entry-point registrations
[project.entry-points."praecepta.applications"]
orders = "praecepta.domain.orders:OrderApplication"

[project.entry-points."praecepta.routers"]
orders = "praecepta.domain.orders.api:router"
```

## 3. Define Events

Events are immutable facts. Use past-tense naming and define them in a shared module:

```python
# src/praecepta/domain/orders/events.py
from decimal import Decimal
from praecepta.foundation.domain import BaseEvent, TenantId

class OrderPlaced(BaseEvent):
    order_id: str
    tenant_id: TenantId
    total: Decimal

class OrderCancelled(BaseEvent):
    order_id: str
    tenant_id: TenantId
    reason: str
```

## 4. Define the Aggregate

```python
# src/praecepta/domain/orders/order.py
from decimal import Decimal
from praecepta.foundation.domain import (
    BaseAggregate,
    InvalidStateTransitionError,
)
from praecepta.domain.orders.events import OrderPlaced, OrderCancelled

class Order(BaseAggregate):
    order_id: str = ""
    total: Decimal = Decimal("0")
    cancelled: bool = False

    def place(self, order_id: str, total: Decimal) -> None:
        self.trigger_event(OrderPlaced, order_id=order_id, total=total)

    def cancel(self, reason: str) -> None:
        if self.cancelled:
            raise InvalidStateTransitionError("Order already cancelled")
        self.trigger_event(OrderCancelled, reason=reason)

    def apply_order_placed(self, event: OrderPlaced) -> None:
        self.order_id = event.order_id
        self.total = event.total

    def apply_order_cancelled(self, event: OrderCancelled) -> None:
        self.cancelled = True
```

## 5. Write `__init__.py`

Export the public API:

```python
# src/praecepta/domain/orders/__init__.py
"""Order management bounded context."""

from praecepta.domain.orders.order import Order

__all__ = ["Order"]
```

Create the empty `py.typed` marker:

```bash
touch packages/domain-orders/src/praecepta/domain/orders/py.typed
```

## 6. Register in Root `pyproject.toml`

Update three sections in the root `pyproject.toml`:

```toml
# 1. Add to dependencies
[project]
dependencies = [
    # ... existing packages ...
    "praecepta-domain-orders",
]

# 2. Add workspace source
[tool.uv.sources]
praecepta-domain-orders = { workspace = true }

# 3. Add mypy path
[tool.mypy]
mypy_path = "...:packages/domain-orders/src"
```

## 7. Sync and Verify

```bash
make install    # uv sync --dev
make verify     # lint + typecheck + boundaries + test
```

## What You Get

After `make install`, your new package is automatically discovered by `create_app()`. Any application that has `praecepta-domain-orders` installed will activate its routers, middleware, and application services without any manual wiring.
