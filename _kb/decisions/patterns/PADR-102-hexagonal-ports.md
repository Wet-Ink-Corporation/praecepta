<!-- Derived from {Project} PADR-102-hexagonal-ports -->
# PADR-102: Hexagonal Architecture (Ports & Adapters)

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Pattern, Architecture

---

## Context

Each bounded context needs clear separation between:

- **Domain logic** (business rules, entities, value objects)
- **Application logic** (use cases, orchestration)
- **Infrastructure** (databases, external services, APIs)

This separation enables:

- Testing domain logic without infrastructure
- Swapping infrastructure implementations
- Protecting domain from external changes

## Decision

**We will apply Hexagonal Architecture (Ports & Adapters)** within each bounded context, with the domain layer having zero external dependencies.

### Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      API LAYER                              │
│   (FastAPI endpoints, request/response handling)            │
│   - Primary adapters (driving)                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                          │
│   (Command/Query handlers, use case orchestration)          │
│   - Uses domain entities                                    │
│   - Depends on port interfaces                              │
└────────────────────────┬────────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│    DOMAIN LAYER     │     │      INFRASTRUCTURE LAYER       │
│  (Entities, VOs,    │     │   (Repository implementations,  │
│   domain events,    │     │    external service clients,    │
│   business rules)   │     │    database adapters)           │
│                     │     │                                 │
│  NO EXTERNAL DEPS   │     │   - Secondary adapters (driven) │
└─────────────────────┘     └─────────────────────────────────┘
```

### Dependency Rule

```
API → Application → Domain ← Infrastructure
                         ↑
                   (implements ports)
```

- Domain has **no imports** from other layers
- Application depends on Domain and **port interfaces**
- Infrastructure **implements** port interfaces
- API calls Application layer

### Package Organization

```
src/{Project}/ordering/
├── domain/                     # Core domain (no external deps)
│   ├── entities.py             # Order, BlockMembership
│   ├── value_objects.py        # ScopeType, ContentType
│   ├── events.py               # Domain events
│   ├── exceptions.py           # Domain exceptions
│   └── services.py             # Domain services (pure logic)
│
├── ports/                      # Interface definitions
│   ├── repositories.py         # Repository interfaces
│   ├── event_publisher.py      # Event publishing interface
│   └── services.py             # External service interfaces
│
├── application/                # Use cases (if not using slices)
│   └── ...
│
├── slices/                     # Feature slices (handlers use ports)
│   └── ...
│
├── infrastructure/             # Adapter implementations
│   ├── repositories/
│   │   └── postgres_repository.py
│   ├── publishers/
│   │   └── event_store_publisher.py
│   └── services/
│       └── spicedb_security.py
│
└── api/                        # Primary adapters
    └── endpoints.py
```

## Port Definitions

### Repository Port

```python
# ports/repositories.py
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from ..domain.entities import Order

class OrderRepository(ABC):
    """Port for order persistence."""

    @abstractmethod
    async def save(self, block: Order) -> None:
        """Persist a order."""
        ...

    @abstractmethod
    async def get(self, block_id: UUID) -> Optional[Order]:
        """Retrieve a order by ID."""
        ...

    @abstractmethod
    async def get_by_scope(
        self,
        scope_type: str,
        scope_id: str,
        tenant_id: str
    ) -> list[Order]:
        """Get all blocks for a scope."""
        ...

    @abstractmethod
    async def delete(self, block_id: UUID) -> None:
        """Delete a order."""
        ...
```

### Event Publisher Port

```python
# ports/event_publisher.py
from abc import ABC, abstractmethod
from typing import Sequence

from ..domain.events import DomainEvent

class EventPublisher(ABC):
    """Port for publishing domain events."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single event."""
        ...

    @abstractmethod
    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        """Publish multiple events atomically."""
        ...
```

### External Service Port

```python
# ports/services.py
from abc import ABC, abstractmethod

class SecurityService(ABC):
    """Port for security/authorization checks."""

    @abstractmethod
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """Check if user has permission on resource."""
        ...

    @abstractmethod
    async def get_user_principals(self, user_id: str) -> list[str]:
        """Get all principals for a user."""
        ...
```

## Adapter Implementations

### Repository Adapter

```python
# infrastructure/repositories/postgres_repository.py
from uuid import UUID
from typing import Optional

from ...domain.entities import Order
from ...ports.repositories import OrderRepository

class PostgresOrderRepository(OrderRepository):
    """PostgreSQL implementation of OrderRepository."""

    def __init__(self, db: Database):
        self._db = db

    async def save(self, block: Order) -> None:
        await self._db.execute("""
            INSERT INTO orders (id, title, scope_type, scope_id,
                                       owner_id, tenant_id, tags, created_at, archived)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                tags = EXCLUDED.tags,
                archived = EXCLUDED.archived
        """, block.id, block.title, block.scope_type.value,
            block.scope_id, block.owner_id, block.tenant_id,
            block.tags, block.created_at, block.archived)

    async def get(self, block_id: UUID) -> Optional[Order]:
        row = await self._db.fetch_one(
            "SELECT * FROM orders WHERE id = $1",
            block_id
        )
        return Order.from_row(row) if row else None

    async def get_by_scope(
        self,
        scope_type: str,
        scope_id: str,
        tenant_id: str
    ) -> list[Order]:
        rows = await self._db.fetch("""
            SELECT * FROM orders
            WHERE scope_type = $1 AND scope_id = $2 AND tenant_id = $3
            ORDER BY created_at DESC
        """, scope_type, scope_id, tenant_id)
        return [Order.from_row(r) for r in rows]

    async def delete(self, block_id: UUID) -> None:
        await self._db.execute(
            "DELETE FROM orders WHERE id = $1",
            block_id
        )
```

### Event Publisher Adapter

```python
# infrastructure/publishers/event_store_publisher.py
from typing import Sequence

from eventsourcing.application import Application

from ...domain.events import DomainEvent
from ...ports.event_publisher import EventPublisher

class EventStorePublisher(EventPublisher):
    """Publish events via eventsourcing library."""

    def __init__(self, app: Application):
        self._app = app

    async def publish(self, event: DomainEvent) -> None:
        # Events are published when aggregate is saved
        # This adapter may just log or notify subscribers
        await self._notify_subscribers(event)

    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def _notify_subscribers(self, event: DomainEvent) -> None:
        # Integration event publishing logic
        ...
```

## Rationale

### Why Hexagonal?

| Benefit | Explanation |
|---------|-------------|
| **Testability** | Domain logic tested without infrastructure |
| **Flexibility** | Swap databases, external services easily |
| **Domain Focus** | Business rules isolated from technical concerns |
| **Clear Boundaries** | Ports define explicit contracts |

### Domain Purity

```python
# domain/entities.py - NO external imports
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from enum import Enum

class ScopeType(Enum):
    PROJECT = "PROJECT"
    TEAM = "TEAM"
    AGENT = "AGENT"
    USER = "USER"

@dataclass
class Order:
    id: UUID
    title: str
    scope_type: ScopeType
    scope_id: str
    owner_id: str
    tenant_id: str
    tags: list[str]
    created_at: datetime
    archived: bool = False

    def archive(self) -> None:
        """Archive this block."""
        if self.archived:
            raise BlockAlreadyArchivedError(self.id)
        self.archived = True

    def add_tag(self, tag: str) -> None:
        """Add a tag to this block."""
        normalized = self._normalize_tag(tag)
        if normalized not in self.tags:
            self.tags.append(normalized)

    def _normalize_tag(self, tag: str) -> str:
        return tag.lower().strip()
```

## Consequences

### Positive

1. **Isolated Testing:** Domain tests use no mocks/stubs
2. **Implementation Flexibility:** Can change database without touching domain
3. **Explicit Dependencies:** Ports document external needs
4. **Framework Independence:** Domain doesn't depend on FastAPI, SQLAlchemy, etc.

### Negative

1. **More Interfaces:** Must define ports for everything external
2. **Indirection:** Extra layer between application and infrastructure
3. **Initial Overhead:** Setup cost for abstractions

### Mitigations

| Risk | Mitigation |
|------|------------|
| Too many interfaces | Only create ports for what varies |
| Indirection confusion | Consistent naming conventions |
| Initial overhead | Generate boilerplate with templates |

## Dependency Injection

```python
# Container configuration (using dependency_injector or manual DI)
from dependency_injector import containers, providers

class MemoryContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    database = providers.Singleton(Database, url=config.database_url)

    # Repositories
    block_repository = providers.Factory(
        PostgresOrderRepository,
        db=database
    )

    # Event publisher
    event_publisher = providers.Factory(
        EventStorePublisher,
        app=providers.Dependency()
    )

    # Handlers
    create_block_handler = providers.Factory(
        CreateBlockHandler,
        repository=block_repository,
        event_publisher=event_publisher
    )
```

## Import Linter Enforcement

```ini
[importlinter:contract:domain-purity]
name = Domain has no infrastructure dependencies
type = layers
layers =
    {Project}.ordering.api
    {Project}.ordering.slices
    {Project}.ordering.ports
    {Project}.ordering.domain
    {Project}.ordering.infrastructure
```

## Related Decisions

- PADR-002: Modular Monolith (hexagonal within contexts)
- PADR-101: Vertical Slices (slices use ports)

## References

- [Alistair Cockburn - Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Robert Martin - Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- Research: `hexagonal-architecture.md`
