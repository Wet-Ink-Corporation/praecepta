# Praecepta

Build Domain-Driven Design / Event Sourcing multi-tenant applications in Python with composable, layered packages.

**[Get Started →](getting-started/installation.md)** | [View on GitHub](https://github.com/wet-ink-corporation/praecepta)

---

## Why Praecepta?

### Event Sourcing by Default

Immutable append-only event streams as the source of truth. State is derived from event replay — giving you a complete audit trail and temporal queries out of the box.

### Multi-Tenant Isolation

Row-Level Security on every table, tenant-scoped projections, and request-context propagation ensure tenant data never leaks — enforced at the infrastructure layer, not by convention.

### 4-Layer Architecture

Foundation, Infrastructure, Domain, and Integration layers with enforced dependency boundaries. Your domain logic stays pure — no framework imports allowed.

### Auto-Discovery

Register applications, projections, middleware, and routers via Python entry points. The app factory discovers and wires everything automatically — no manual registration.

---

## Quick Example

```python
# Define an aggregate with event sourcing
from praecepta.foundation.domain import BaseAggregate, BaseEvent, TenantId

class OrderPlaced(BaseEvent):
    order_id: str
    tenant_id: TenantId
    total: Decimal

class Order(BaseAggregate):
    def place(self, order_id: str, total: Decimal) -> None:
        self.trigger_event(OrderPlaced, order_id=order_id, total=total)

    def apply_order_placed(self, event: OrderPlaced) -> None:
        self.order_id = event.order_id
        self.total = event.total
```
