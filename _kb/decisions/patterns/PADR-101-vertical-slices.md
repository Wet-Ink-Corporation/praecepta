<!-- Derived from {Project} PADR-101-vertical-slices -->
# PADR-101: Vertical Slice Architecture

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Pattern, Code Organization

---

## Context

Within each bounded context, we need a code organization pattern that:

- Maximizes cohesion for individual features
- Minimizes coupling between features
- Supports CQRS (separate command/query handling)
- Enables team members to work on features independently
- Keeps related code together for easier maintenance

Traditional layered architecture (Controller → Service → Repository) scatters feature code across many directories, making changes difficult to scope.

## Decision

**We will organize code within bounded contexts using Vertical Slice Architecture**, where each feature/use case is a self-contained slice.

### Slice Structure

```
src/{Project}/ordering/
├── domain/                           # Shared domain model
│   ├── entities.py                   # Order, etc.
│   ├── events.py                     # Domain events
│   ├── value_objects.py              # ScopeType, ContentType
│   └── exceptions.py                 # Domain exceptions
│
├── slices/                           # Feature slices
│   ├── create_block/                 # Command slice
│   │   ├── __init__.py
│   │   ├── command.py                # CreateBlockCommand
│   │   ├── handler.py                # CreateBlockHandler
│   │   ├── endpoint.py               # POST /blocks
│   │   ├── validator.py              # Pydantic request schema
│   │   └── test_create_block.py
│   │
│   ├── get_block/                    # Query slice
│   │   ├── __init__.py
│   │   ├── query.py                  # GetBlockQuery
│   │   ├── handler.py                # GetBlockHandler
│   │   ├── endpoint.py               # GET /blocks/{id}
│   │   ├── dto.py                    # Response DTO
│   │   └── test_get_block.py
│   │
│   ├── add_membership/
│   ├── remove_membership/
│   ├── archive_block/
│   ├── list_blocks/
│   └── search_blocks/
│
├── shared/                           # Shared within context
│   ├── repository.py                 # Repository interface
│   ├── dtos.py                       # Shared DTOs
│   └── security.py                   # Context-specific security
│
├── infrastructure/                   # Adapters for this context
│   ├── postgres_repository.py
│   └── event_publisher.py
│
└── router.py                         # Compose slice routers
```

### Command Slice Pattern

```python
# slices/create_block/command.py
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class CreateBlockCommand:
    """Command to create a new order."""
    title: str
    scope_type: str
    scope_id: str
    owner_id: str
    tenant_id: str
    tags: list[str] = ()

# slices/create_block/handler.py
from uuid import uuid4
from datetime import datetime, UTC

class CreateBlockHandler:
    def __init__(
        self,
        repository: OrderRepository,
        event_publisher: EventPublisher
    ):
        self._repository = repository
        self._event_publisher = event_publisher

    async def handle(self, command: CreateBlockCommand) -> UUID:
        block = Order(
            id=uuid4(),
            title=command.title,
            scope_type=ScopeType(command.scope_type),
            scope_id=command.scope_id,
            owner_id=command.owner_id,
            tenant_id=command.tenant_id,
            tags=list(command.tags),
            created_at=datetime.now(UTC)
        )

        await self._repository.save(block)
        await self._event_publisher.publish(OrderPlaced(block_id=block.id))

        return block.id

# slices/create_block/endpoint.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

class CreateBlockRequest(BaseModel):
    title: str
    scope_type: str
    scope_id: str
    tags: list[str] = []

class CreateBlockResponse(BaseModel):
    id: str
    message: str = "Block created successfully"

router = APIRouter()

@router.post("/blocks", response_model=CreateBlockResponse)
async def create_block(
    request: CreateBlockRequest,
    handler: CreateBlockHandler = Depends(get_handler),
    current_user: User = Depends(get_current_user)
) -> CreateBlockResponse:
    command = CreateBlockCommand(
        title=request.title,
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        owner_id=current_user.id,
        tenant_id=current_user.tenant_id,
        tags=request.tags
    )
    block_id = await handler.handle(command)
    return CreateBlockResponse(id=str(block_id))
```

### Query Slice Pattern

```python
# slices/get_block/query.py
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class GetBlockQuery:
    """Query to retrieve a order."""
    block_id: UUID
    user_id: str
    tenant_id: str

# slices/get_block/handler.py
class GetBlockHandler:
    def __init__(self, db: Database, security: SecurityService):
        self._db = db
        self._security = security

    async def handle(self, query: GetBlockQuery) -> BlockDTO:
        # Queries can use optimized reads (raw SQL)
        result = await self._db.fetch_one("""
            SELECT id, title, scope_type, scope_id, owner_id,
                   tags, created_at, archived
            FROM orders
            WHERE id = $1 AND tenant_id = $2
        """, query.block_id, query.tenant_id)

        if not result:
            raise BlockNotFoundError(query.block_id)

        # Security check
        if not await self._security.can_view(query.user_id, result):
            raise AccessDeniedError()

        return BlockDTO.from_row(result)
```

## Rationale

### Why Vertical Slices?

| Aspect | Layered Architecture | Vertical Slices |
|--------|---------------------|-----------------|
| **Cohesion** | Low (spread across layers) | High (all in one place) |
| **Feature changes** | Touch 4-5 directories | Touch 1 directory |
| **Parallel work** | May conflict | Independent slices |
| **Testing** | Mock many layers | Test slice in isolation |
| **Onboarding** | Learn all layers | Understand one slice |

### CQRS Alignment

Slices naturally separate into:

- **Command slices:** `create_block`, `add_membership`, `archive_block`
- **Query slices:** `get_block`, `list_blocks`, `search_blocks`

Commands use domain model + events; queries can use optimized reads.

### Bogard's Principle

> "Minimize coupling between slices, and maximize coupling within a slice."

Each slice is independent; shared code only in `domain/` and `shared/`.

## Consequences

### Positive

1. **Feature Isolation:** Complete feature in one directory
2. **Independent Development:** Teams work on different slices
3. **Tailored Implementation:** Queries can use raw SQL, commands use ORM
4. **Focused Testing:** Tests mirror the slice structure (see Testing Strategy below)
5. **Easy Navigation:** Find feature code by use case name

### Negative

1. **Potential Duplication:** Similar code across slices
2. **Learning Curve:** Different from traditional layered architecture
3. **Slice Boundaries:** May be unclear for complex features

### Mitigations

| Risk | Mitigation |
|------|------------|
| Code duplication | Extract to `shared/` when pattern emerges 3+ times |
| Learning curve | Team training, code review standards |
| Unclear boundaries | Start with one slice per endpoint, refactor as needed |

## Router Composition

```python
# memory/router.py
from fastapi import APIRouter

from .slices.create_block.endpoint import router as create_router
from .slices.get_block.endpoint import router as get_router
from .slices.add_membership.endpoint import router as membership_router
from .slices.list_blocks.endpoint import router as list_router
from .slices.search_blocks.endpoint import router as search_router

memory_router = APIRouter(prefix="/memory", tags=["memory"])

memory_router.include_router(create_router)
memory_router.include_router(get_router)
memory_router.include_router(membership_router)
memory_router.include_router(list_router)
memory_router.include_router(search_router)
```

## Testing Strategy

### Test Location (Amended)

While this ADR originally prescribed co-locating tests within slice directories,
the project follows the standard Python convention of a separate `tests/` directory
tree mirroring the `src/` structure:

- `src/{Project}/ordering/slices/create_block/cmd.py` -> `tests/unit/ordering/slices/create_block/test_cmd.py`
- `src/{Project}/ordering/slices/get_block/handler.py` -> `tests/unit/ordering/slices/get_block/test_handler.py`

Rationale for this convention:

1. pytest discovery via `testpaths = ["tests"]` cleanly separates test/prod code
2. `--cov=src` excludes test code from coverage measurement without extra config
3. `src/` package stays free of test-only dependencies
4. The mirrored directory structure preserves the conceptual co-location

### Slice Testing Pattern

Each slice has corresponding tests in the mirrored `tests/` directory:

```python
# tests/unit/ordering/slices/create_block/test_cmd.py
import pytest
from unittest.mock import AsyncMock

class TestCreateBlockHandler:
    @pytest.fixture
    def mock_repository(self):
        return AsyncMock(spec=OrderRepository)

    @pytest.fixture
    def mock_event_publisher(self):
        return AsyncMock(spec=EventPublisher)

    @pytest.fixture
    def handler(self, mock_repository, mock_event_publisher):
        return CreateBlockHandler(mock_repository, mock_event_publisher)

    async def test_creates_block_with_valid_command(self, handler, mock_repository):
        command = CreateBlockCommand(
            title="Test Block",
            scope_type="PROJECT",
            scope_id="proj-1",
            owner_id="user-1",
            tenant_id="tenant-1",
            tags=["test"]
        )

        block_id = await handler.handle(command)

        assert block_id is not None
        mock_repository.save.assert_called_once()

    async def test_publishes_block_created_event(self, handler, mock_event_publisher):
        command = CreateBlockCommand(...)
        await handler.handle(command)
        mock_event_publisher.publish.assert_called_once()
```

## Related Decisions

- PADR-002: Modular Monolith (slices within contexts)
- PADR-102: Hexagonal Ports (handlers use ports)

## References

- [Jimmy Bogard - Vertical Slice Architecture](https://www.jimmybogard.com/vertical-slice-architecture/)
- [Milan Jovanovic - Vertical Slice Architecture](https://www.milanjovanovic.tech/blog/vertical-slice-architecture)
- Research: `vertical-slice-architecture.md`
