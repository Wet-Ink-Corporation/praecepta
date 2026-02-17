# Define an Aggregate

Aggregates are consistency boundaries — they enforce business rules and emit events that represent state changes.

## The Pattern

Every aggregate follows the `trigger_event()` / `apply()` pattern:

1. **Command methods** validate business rules and call `trigger_event()`
2. **Apply methods** update internal state from events (no business logic here)

```python
from praecepta.foundation.domain import BaseAggregate, BaseEvent, TenantId

class ItemAdded(BaseEvent):
    item_id: str
    tenant_id: TenantId
    name: str

class Cart(BaseAggregate):
    items: list[str] = []

    # Command method — validates rules, triggers events
    def add_item(self, item_id: str, name: str) -> None:
        if item_id in self.items:
            raise ValueError("Item already in cart")
        self.trigger_event(ItemAdded, item_id=item_id, name=name)

    # Apply method — updates state from event (no validation here)
    def apply_item_added(self, event: ItemAdded) -> None:
        self.items.append(event.item_id)
```

## Apply Method Naming

Apply methods follow the convention `apply_{snake_case_event_name}`:

| Event Class | Apply Method |
|-------------|-------------|
| `OrderPlaced` | `apply_order_placed` |
| `ItemAdded` | `apply_item_added` |
| `TenantSuspended` | `apply_tenant_suspended` |

## State Transitions

Use exceptions from `praecepta.foundation.domain` to enforce valid state transitions:

```python
from praecepta.foundation.domain import (
    BaseAggregate,
    InvalidStateTransitionError,
    ValidationError,
)

class Order(BaseAggregate):
    status: str = "draft"

    def submit(self) -> None:
        if self.status != "draft":
            raise InvalidStateTransitionError(
                f"Cannot submit order in '{self.status}' status"
            )
        self.trigger_event(OrderSubmitted)

    def cancel(self, reason: str) -> None:
        if self.status == "cancelled":
            raise InvalidStateTransitionError("Already cancelled")
        if not reason:
            raise ValidationError("Cancellation reason is required")
        self.trigger_event(OrderCancelled, reason=reason)
```

## Two-Tier Validation

Validation happens in two tiers:

1. **Structural** (at the API boundary) — Pydantic validates data types, required fields, formats
2. **Semantic** (in the aggregate) — Domain rules validate business logic

```python
# Tier 1: Pydantic DTO (API layer)
class PlaceOrderRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=50)
    total: Decimal = Field(gt=0)

# Tier 2: Aggregate (domain layer)
class Order(BaseAggregate):
    def place(self, order_id: str, total: Decimal) -> None:
        # Semantic validation — requires domain knowledge
        if self.is_finalized:
            raise InvalidStateTransitionError("Order is finalized")
        self.trigger_event(OrderPlaced, order_id=order_id, total=total)
```

## Testing Aggregates

Aggregates are pure domain objects with no framework dependencies, making them straightforward to test:

```python
import pytest
from praecepta.foundation.domain import InvalidStateTransitionError

def test_order_can_be_placed():
    order = Order()
    order.place(order_id="ORD-1", total=Decimal("99.99"))
    assert order.order_id == "ORD-1"
    assert order.total == Decimal("99.99")

def test_cancelled_order_cannot_be_shipped():
    order = Order()
    order.place(order_id="ORD-1", total=Decimal("99.99"))
    order.cancel(reason="Changed mind")
    with pytest.raises(InvalidStateTransitionError):
        order.ship(tracking_number="TRACK-1")
```
