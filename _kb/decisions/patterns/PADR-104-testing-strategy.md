<!-- Derived from {Project} PADR-104-testing-strategy -->
# PADR-104: Testing Strategy

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Pattern, Testing

---

## Context

{Project}'s architecture (event sourcing, modular monolith, hexagonal) requires a testing strategy that:

- Validates domain logic without infrastructure
- Tests event sourcing behavior
- Verifies cross-context integration
- Ensures API contract correctness
- Maintains high confidence with reasonable test suite runtime

## Decision

**We will implement a Testing Pyramid** with clear boundaries for unit, integration, and end-to-end tests.

### Test Pyramid

```
                    ┌───────────────┐
                    │     E2E       │  ← Few, slow, critical paths
                    │   (Cypress)   │
                    └───────────────┘
               ┌─────────────────────────┐
               │     Integration         │  ← Medium, some I/O
               │   (pytest, testcontainers)│
               └─────────────────────────┘
          ┌───────────────────────────────────┐
          │            Unit Tests             │  ← Many, fast, no I/O
          │         (pytest, hypothesis)       │
          └───────────────────────────────────┘
```

### Coverage Targets

| Test Type | Coverage Target | Runtime Target |
|-----------|-----------------|----------------|
| **Unit** | 90%+ domain/application | < 30 seconds |
| **Integration** | 80%+ repositories, handlers | < 5 minutes |
| **E2E** | Critical user journeys | < 15 minutes |

### Test Organization

```
tests/
├── unit/
│   ├── memory/
│   │   ├── domain/
│   │   │   ├── test_order.py
│   │   │   └── test_events.py
│   │   └── slices/
│   │       ├── test_create_block_handler.py
│   │       └── test_add_membership_handler.py
│   ├── Processing/
│   └── query/
│
├── integration/
│   ├── memory/
│   │   ├── test_postgres_repository.py
│   │   └── test_event_sourcing.py
│   ├── Processing/
│   └── conftest.py  # Shared fixtures (testcontainers)
│
├── e2e/
│   ├── test_block_lifecycle.py
│   ├── test_search_flow.py
│   └── conftest.py
│
└── conftest.py      # Global fixtures
```

## Unit Testing

### Domain Entity Tests

```python
# tests/unit/ordering/domain/test_order.py
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from {Project}.ordering.domain.entities import Order, ScopeType
from {Project}.ordering.domain.exceptions import BlockAlreadyArchivedError

class TestOrder:
    @pytest.fixture
    def block(self):
        return Order(
            id=uuid4(),
            title="Test Block",
            scope_type=ScopeType.PROJECT,
            scope_id="proj-1",
            owner_id="user-1",
            tenant_id="tenant-1",
            tags=["test"],
            created_at=datetime.now(UTC)
        )

    def test_archive_sets_archived_flag(self, block):
        assert not block.archived
        block.archive()
        assert block.archived

    def test_archive_already_archived_raises_error(self, block):
        block.archive()
        with pytest.raises(BlockAlreadyArchivedError):
            block.archive()

    def test_add_tag_normalizes_and_adds(self, block):
        block.add_tag("  New Tag  ")
        assert "new tag" in block.tags

    def test_add_duplicate_tag_is_idempotent(self, block):
        block.add_tag("test")
        assert block.tags.count("test") == 1
```

### Handler Tests (with Mocks)

```python
# tests/unit/ordering/slices/test_create_block_handler.py
import pytest
from unittest.mock import AsyncMock
from uuid import UUID

from {Project}.ordering.slices.create_block.command import CreateBlockCommand
from {Project}.ordering.slices.create_block.handler import CreateBlockHandler
from {Project}.ordering.ports.repositories import OrderRepository
from {Project}.ordering.ports.event_publisher import EventPublisher

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

    @pytest.fixture
    def valid_command(self):
        return CreateBlockCommand(
            title="Test Block",
            scope_type="PROJECT",
            scope_id="proj-1",
            owner_id="user-1",
            tenant_id="tenant-1",
            tags=["test"]
        )

    async def test_creates_block_with_generated_id(self, handler, valid_command):
        block_id = await handler.handle(valid_command)
        assert isinstance(block_id, UUID)

    async def test_saves_block_to_repository(self, handler, valid_command, mock_repository):
        await handler.handle(valid_command)

        mock_repository.save.assert_called_once()
        saved_block = mock_repository.save.call_args[0][0]
        assert saved_block.title == "Test Block"
        assert saved_block.scope_type.value == "PROJECT"

    async def test_publishes_block_created_event(self, handler, valid_command, mock_event_publisher):
        block_id = await handler.handle(valid_command)

        mock_event_publisher.publish.assert_called_once()
        event = mock_event_publisher.publish.call_args[0][0]
        assert event.block_id == block_id
```

### Event Sourcing Tests

```python
# tests/unit/ordering/domain/test_events.py
import pytest
from eventsourcing.domain import Aggregate

from {Project}.ordering.domain.aggregates import OrderAggregate

class TestOrderAggregate:
    def test_creation_emits_created_event(self):
        block = OrderAggregate(
            title="Test",
            owner_id="user-1",
            tenant_id="tenant-1"
        )

        events = block.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Created"
        assert events[0].title == "Test"

    def test_add_membership_emits_event(self):
        block = OrderAggregate("Test", "u1", "t1")
        block.collect_events()  # Clear creation

        content_id = uuid4()
        block.add_membership(content_id)

        events = block.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "MembershipAdded"
        assert events[0].content_id == content_id

    def test_duplicate_membership_emits_no_event(self):
        block = OrderAggregate("Test", "u1", "t1")
        content_id = uuid4()
        block.add_membership(content_id)
        block.collect_events()

        block.add_membership(content_id)  # Duplicate

        events = block.collect_events()
        assert len(events) == 0
```

## Integration Testing

### Repository Tests

```python
# tests/integration/ordering/test_postgres_repository.py
import pytest
from uuid import uuid4

from {Project}.ordering.infrastructure.repositories.postgres_repository import (
    PostgresOrderRepository
)
from {Project}.ordering.domain.entities import Order, ScopeType

@pytest.mark.integration
class TestPostgresOrderRepository:
    @pytest.fixture
    async def repository(self, db_connection):
        return PostgresOrderRepository(db_connection)

    @pytest.fixture
    def sample_block(self):
        return Order(
            id=uuid4(),
            title="Integration Test Block",
            scope_type=ScopeType.PROJECT,
            scope_id="proj-test",
            owner_id="user-test",
            tenant_id="tenant-test",
            tags=["integration"],
            created_at=datetime.now(UTC)
        )

    async def test_save_and_retrieve(self, repository, sample_block):
        await repository.save(sample_block)

        retrieved = await repository.get(sample_block.id)

        assert retrieved is not None
        assert retrieved.id == sample_block.id
        assert retrieved.title == sample_block.title

    async def test_get_nonexistent_returns_none(self, repository):
        result = await repository.get(uuid4())
        assert result is None

    async def test_get_by_scope(self, repository, sample_block):
        await repository.save(sample_block)

        blocks = await repository.get_by_scope(
            scope_type="PROJECT",
            scope_id="proj-test",
            tenant_id="tenant-test"
        )

        assert len(blocks) >= 1
        assert any(b.id == sample_block.id for b in blocks)
```

### Testcontainers Setup

```python
# tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as neo4j:
        yield neo4j

@pytest.fixture
async def db_connection(postgres_container):
    import asyncpg
    conn = await asyncpg.connect(postgres_container.get_connection_url())

    # Run migrations
    await run_migrations(conn)

    yield conn

    # Cleanup
    await conn.execute("TRUNCATE orders, block_memberships CASCADE")
    await conn.close()
```

### Event Store Integration

```python
# tests/integration/ordering/test_event_sourcing.py
import pytest
from eventsourcing.application import Application

from {Project}.ordering.domain.aggregates import OrderAggregate

@pytest.mark.integration
class TestEventStoreIntegration:
    @pytest.fixture
    def app(self, postgres_container):
        return CoreApplication(env={
            "PERSISTENCE_MODULE": "eventsourcing_postgres",
            "POSTGRES_DBNAME": "test",
            # ... connection settings from container
        })

    async def test_aggregate_persisted_and_retrieved(self, app):
        # Create
        block = OrderAggregate("Test", "user-1", "tenant-1")
        block_id = block.id
        app.save(block)

        # Retrieve
        retrieved = app.repository.get(block_id)

        assert retrieved.title == "Test"
        assert retrieved.version == 1

    async def test_event_replay_rebuilds_state(self, app):
        # Create and modify
        block = OrderAggregate("Test", "user-1", "tenant-1")
        block.add_tag("important")
        block.add_membership(uuid4())
        app.save(block)

        # Retrieve (replays events)
        retrieved = app.repository.get(block.id)

        assert "important" in retrieved.tags
        assert len(retrieved.memberships) == 1
```

## End-to-End Testing

### API Tests

```python
# tests/e2e/test_block_lifecycle.py
import pytest
from httpx import AsyncClient

@pytest.mark.e2e
class TestBlockLifecycle:
    @pytest.fixture
    async def client(self, app):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def auth_headers(self, test_user_token):
        return {"Authorization": f"Bearer {test_user_token}"}

    async def test_create_block_returns_id(self, client, auth_headers):
        response = await client.post(
            "/ordering/blocks",
            json={
                "title": "E2E Test Block",
                "scope_type": "PROJECT",
                "scope_id": "proj-e2e",
                "tags": ["e2e"]
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    async def test_full_block_lifecycle(self, client, auth_headers):
        # Create
        create_response = await client.post(
            "/ordering/blocks",
            json={"title": "Lifecycle Test", "scope_type": "USER", "scope_id": "user-1"},
            headers=auth_headers
        )
        block_id = create_response.json()["id"]

        # Read
        get_response = await client.get(
            f"/ordering/blocks/{block_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "Lifecycle Test"

        # Add membership
        membership_response = await client.post(
            f"/ordering/blocks/{block_id}/memberships",
            json={"content_type": "Segment", "content_id": str(uuid4())},
            headers=auth_headers
        )
        assert membership_response.status_code == 200

        # Archive
        archive_response = await client.post(
            f"/ordering/blocks/{block_id}/archive",
            headers=auth_headers
        )
        assert archive_response.status_code == 200

        # Verify archived
        final_response = await client.get(
            f"/ordering/blocks/{block_id}",
            headers=auth_headers
        )
        assert final_response.json()["archived"] is True
```

## Test Utilities

### Factories

```python
# tests/factories.py
from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime, UTC

from {Project}.ordering.domain.entities import Order, ScopeType

@dataclass
class OrderFactory:
    @staticmethod
    def create(
        title: str = "Test Block",
        scope_type: ScopeType = ScopeType.PROJECT,
        scope_id: str = "proj-1",
        **kwargs
    ) -> Order:
        return Order(
            id=kwargs.get("id", uuid4()),
            title=title,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_id=kwargs.get("owner_id", "user-1"),
            tenant_id=kwargs.get("tenant_id", "tenant-1"),
            tags=kwargs.get("tags", []),
            created_at=kwargs.get("created_at", datetime.now(UTC)),
            archived=kwargs.get("archived", False)
        )
```

### Property-Based Testing

```python
# tests/unit/ordering/domain/test_order_properties.py
from hypothesis import given, strategies as st

from {Project}.ordering.domain.entities import Order

class TestOrderProperties:
    @given(st.text(min_size=1, max_size=100))
    def test_add_tag_preserves_tag(self, tag):
        block = OrderFactory.create()
        block.add_tag(tag)
        assert tag.lower().strip() in block.tags

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
    def test_multiple_tags_all_present(self, tags):
        block = OrderFactory.create()
        for tag in tags:
            block.add_tag(tag)

        for tag in tags:
            assert tag.lower().strip() in block.tags
```

## CI Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit -v --cov={Project} --cov-report=xml
      - uses: codecov/codecov-action@v3

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
      - run: pip install -e ".[dev]"
      - run: pytest tests/integration -v -m integration

  e2e:
    runs-on: ubuntu-latest
    needs: [unit, integration]
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d
      - run: pytest tests/e2e -v -m e2e
```

## Related Decisions

- PADR-101: Vertical Slices (test organization mirrors slices)
- PADR-102: Hexagonal Ports (ports enable mocking)
- PADR-103: Error Handling (test exception scenarios)

## References

- [pytest Documentation](https://docs.pytest.org/)
- [Testcontainers Python](https://testcontainers-python.readthedocs.io/)
- [Hypothesis](https://hypothesis.readthedocs.io/)
