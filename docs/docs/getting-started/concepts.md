# Core Concepts

## Event Sourcing

Instead of storing current state, praecepta stores **events** — immutable facts about things that happened. Current state is derived by replaying events.

```
OrderPlaced → OrderShipped → OrderDelivered
       ↓              ↓              ↓
  state v1       state v2       state v3
```

This gives you a complete audit trail, temporal queries, and the ability to rebuild state from scratch.

## Domain-Driven Design

Praecepta uses DDD building blocks to organize business logic:

| Concept | Purpose | Example |
|---------|---------|---------|
| **Aggregate** | Consistency boundary | `Order`, `Tenant`, `User` |
| **Event** | Immutable fact | `OrderPlaced`, `TenantCreated` |
| **Value Object** | Immutable value with equality | `Email`, `TenantSlug`, `Money` |
| **Projection** | Read model derived from events | Order summary table, tenant dashboard |

## 4-Layer Architecture

All packages follow a strict layered dependency hierarchy, enforced by `import-linter`:

```
┌─────────────────────────────────────────────┐
│  Layer 3: Integration                       │
│  Cross-domain sagas and orchestration       │
├─────────────────────────────────────────────┤
│  Layer 2: Domain                            │
│  Reusable bounded contexts                  │
├─────────────────────────────────────────────┤
│  Layer 1: Infrastructure                    │
│  Adapter implementations                    │
├─────────────────────────────────────────────┤
│  Layer 0: Foundation                        │
│  Pure domain primitives (no frameworks)     │
└─────────────────────────────────────────────┘
```

Dependencies flow **strictly downward**. Foundation packages never import infrastructure frameworks like FastAPI, SQLAlchemy, or Redis.

## Multi-Tenancy

Every praecepta application is multi-tenant by default:

- **Row-Level Security (RLS)** enforced on all database tables
- **Tenant ID** propagated through request context middleware
- **Projections** scoped to tenant — `tenant_id` required on every projection table
- **Configuration** per-tenant via hierarchical config system

## Entry-Point Auto-Discovery

Packages declare what they contribute in `pyproject.toml`. The app factory discovers and wires everything automatically:

```toml
# In your package's pyproject.toml
[project.entry-points."praecepta.routers"]
orders = "my_app.api:router"

[project.entry-points."praecepta.applications"]
orders = "my_app.application:OrderApplication"
```

Install a package, and it activates. No manual wiring required.

## Two-Tier Validation

Validation happens in two stages:

1. **Structural validation** (Pydantic) — data types, required fields, format constraints
2. **Semantic validation** (domain rules) — business rules that require domain knowledge

```python
# Tier 1: Pydantic validates structure
class PlaceOrderRequest(BaseModel):
    order_id: str = Field(min_length=1)
    total: Decimal = Field(gt=0)

# Tier 2: Domain validates semantics
class Order(BaseAggregate):
    def place(self, order_id: str, total: Decimal) -> None:
        if self.is_cancelled:
            raise InvalidStateTransitionError("Cannot place cancelled order")
        self.trigger_event(OrderPlaced, order_id=order_id, total=total)
```

## Sync/Async Strategy

Commands and queries follow different execution models:

| Operation | Style | Rationale |
|-----------|-------|-----------|
| **Commands** | `def` (sync) | Event store writes are synchronous |
| **Queries** | `async def` | Database reads benefit from async I/O |
| **Projections** | `def` (sync) | Process events synchronously for consistency |
