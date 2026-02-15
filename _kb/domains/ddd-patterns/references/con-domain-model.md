# Domain Model

> Core domain concepts and aggregates

---

## Overview

The domain model follows Domain-Driven Design principles with Event Sourcing. This document describes the fundamental patterns that apply across all bounded contexts.

---

## Aggregate Design

### Principles

| Principle | Implementation |
|-----------|----------------|
| **Transactional Boundary** | Each aggregate is a consistency boundary |
| **Event Sourced** | State reconstructed from events |
| **Identified by UUID** | Every aggregate has a unique identifier |
| **Version Tracked** | Optimistic concurrency via version numbers |

### Base Aggregate

```python
from eventsourcing.domain import Aggregate, DomainEvent
from dataclasses import dataclass, field
from uuid import UUID, uuid4

@dataclass
class BaseAggregate(Aggregate):
    """Base class for all project aggregates."""
    tenant_id: str = ""

    @classmethod
    def create(cls, **kwargs) -> "BaseAggregate":
        """Factory method for aggregate creation."""
        aggregate = cls(**kwargs)
        return aggregate
```

> **Library Usage Note:** This is a thin wrapper extending `eventsourcing.domain.Aggregate`. The library provides event collection, versioning, replay, and persistence—we only add project-specific fields like `tenant_id`. Do not reimplement these capabilities.

---

## Domain Events

### Structure

All events inherit from a context-specific base. The pattern below shows the extension approach—adding correlation/causation IDs and tenant isolation on top of the library's event infrastructure:

```python
@dataclass(frozen=True)
class AppEvent:
    """Application extension pattern for domain events."""
    originator_id: UUID           # Aggregate that emitted this event
    originator_version: int       # Version for ordering
    correlation_id: str | None    # Links events in a workflow
    causation_id: str | None      # Links to triggering event
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tenant_id: str = ""           # Multi-tenant isolation

@dataclass(frozen=True)
class OrderEvent(DomainEvent):
    """Base for Order context events."""
    pass

@dataclass(frozen=True)
class OrderPlaced(OrderEvent):
    """Emitted when an order is placed."""
    customer_id: UUID
    total_amount: Decimal
    currency: str
    line_items: tuple[str, ...]
```

### Event Properties

| Property | Purpose | Example |
|----------|---------|---------|
| `originator_id` | Links event to aggregate | Order UUID |
| `originator_version` | Ordering within aggregate | 1, 2, 3... |
| `correlation_id` | Traces workflow/request | Request ID |
| `causation_id` | Links to parent event | Parent event ID |
| `tenant_id` | Multi-tenant isolation | "acme" |

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| **Events** | Past tense verb | `OrderPlaced`, `ItemShipped` |
| **Commands** | Imperative verb | `PlaceOrder`, `ShipItem` |

---

## Value Objects

### Definition

Immutable objects defined by their attributes, not identity:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Money:
    """Monetary value with currency."""
    amount: Decimal
    currency: str

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount must be non-negative")

@dataclass(frozen=True)
class Address:
    """Shipping or billing address."""
    street: str
    city: str
    postal_code: str
    country: str

@dataclass(frozen=True)
class Principal:
    """Identity reference for authorization."""
    type: PrincipalType  # USER, GROUP, ROLE, TENANT
    id: str

    def __str__(self) -> str:
        return f"{self.type.value}:{self.id}"
```

### Common Value Objects

| Value Object | Context | Purpose |
|--------------|---------|--------|
| `Money` | Orders | Amount + currency pair |
| `Address` | Shipping | Validated postal address |
| `OrderStatus` | Orders | PENDING, CONFIRMED, SHIPPED, DELIVERED |
| `Priority` | Tasks | LOW, NORMAL, HIGH, URGENT |
| `Permission` | Security | VIEW, EDIT, ADMIN |

---

## Commands

### Structure

Commands are immutable with pure `handle()` methods:

```python
@dataclass(frozen=True)
class PlaceOrder(Command):
    """Place a new order."""
    customer_id: UUID
    total_amount: Decimal
    currency: str
    tenant_id: str
    line_items: tuple[str, ...] = field(default_factory=tuple)
    order_id: UUID = field(default_factory=uuid4)

    def handle(self, events: DomainEvents) -> DomainEvents:
        """Pure function: past events → new events."""
        # Business rules
        if len(events) > 0:
            raise OrderAlreadyExistsError(self.order_id)

        # Return new events
        return (OrderPlaced(
            originator_id=self.order_id,
            originator_version=1,
            customer_id=self.customer_id,
            total_amount=self.total_amount,
            # ...
        ),)
```

### Command Properties

| Property | Purpose |
|----------|---------|
| **Immutable** | `frozen=True` dataclass |
| **Self-identifying** | Contains its own ID |
| **Pure handler** | No side effects in `handle()` |
| **Testable** | Test with `cmd.handle(events)` |

---

## Entity vs Aggregate

| Concept | Characteristics | Example |
|---------|-----------------|--------|
| **Aggregate** | Consistency boundary, event-sourced, has ID | `Order`, `Customer` |
| **Entity** | Has identity, belongs to aggregate | `LineItem`, `ShipmentItem` |
| **Value Object** | No identity, immutable | `Money`, `Principal` |

---

## Ubiquitous Language

Each bounded context should define its own ubiquitous language. Common cross-cutting terms:

| Term | Definition |
|------|------------|
| **Aggregate** | Consistency boundary with event-sourced state |
| **Command** | Intent to change state, produces events |
| **Event** | Immutable record of something that happened |
| **Projection** | Read model derived from events |
| **Principal** | Identity reference (user, group, role) |
| **Tenant** | Organizational boundary |
| **ACL** | Access Control List |
| **ReBAC** | Relationship-Based Access Control |

---

## Domain Rules

Each bounded context defines invariants that must hold. Example patterns:

### Cross-Cutting Rules

1. Every aggregate mutation must produce at least one event
2. All queries must include tenant_id scoping
3. ACLs propagate through resource hierarchies
4. Deny takes precedence over allow
5. All access decisions are audited

### Example: Order Context

1. An order can only be placed if at least one line item exists
2. Order total must match sum of line item amounts
3. Cancelled orders cannot be modified
4. Shipped orders cannot be cancelled

---

## See Also

- [Architecture Layers](con-layers.md) — Layer responsibilities
- [Domain Modeling](con-domain-modeling.md) — Events, commands, queries
- [Package Types](con-package-types.md) — Dependency rules
