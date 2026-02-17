# Define Events

Events are immutable records of things that happened in your domain. They are the source of truth in an event-sourced system.

## Event Basics

Events extend `BaseEvent` and use **past-tense naming**:

```python
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

## Naming Convention

Events describe facts that already happened. Always use past tense:

| Good | Bad |
|------|-----|
| `OrderPlaced` | `PlaceOrder` |
| `UserRegistered` | `RegisterUser` |
| `TenantSuspended` | `SuspendTenant` |
| `PaymentRefunded` | `RefundPayment` |

## Multi-Tenancy

Every event should include a `tenant_id` field. This is required for tenant-scoped event stores and projections:

```python
class OrderPlaced(BaseEvent):
    order_id: str
    tenant_id: TenantId    # Required for multi-tenant isolation
    total: Decimal
```

## Event Fields

Events carry the data needed to reconstruct state. Include enough information for consumers (projections, sagas) to act on the event without needing to query back:

```python
# Good — self-contained
class OrderPlaced(BaseEvent):
    order_id: str
    tenant_id: TenantId
    customer_name: str      # Included so projections don't need a lookup
    total: Decimal
    currency: str

# Avoid — forces consumers to look up missing data
class OrderPlaced(BaseEvent):
    order_id: str
    tenant_id: TenantId
    # Missing: customer info, total, currency
```

## Organizing Events

Place events in a `_shared/events.py` module within your bounded context, or in a top-level `events.py` for simpler packages:

```
my_context/
├── _shared/
│   └── events.py       # All events for this context
├── order.py            # Order aggregate
└── __init__.py
```

## Events Are Immutable

Events represent historical facts. They should never be modified after creation. The `BaseEvent` class enforces this via Pydantic's frozen model configuration.
