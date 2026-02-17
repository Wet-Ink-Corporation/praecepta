# Testing Strategy

> Test pyramid, patterns, and quality assurance approach

---

## Overview

{Project} uses a testing pyramid strategy optimized for its event-sourced, modular monolith architecture. Tests are organized by scope and speed, with the majority being fast unit tests and targeted integration tests for infrastructure boundaries.

---

## Test Pyramid

```
                         ┌─────────────────────────────────────┐
                         │            E2E Tests                │
                         │    (Critical paths, ~15 min)        │
                         │         ~5% of tests                │
                         └─────────────────────────────────────┘
                    ┌───────────────────────────────────────────────┐
                    │           Integration Tests                    │
                    │   (Repositories, external services, ~5 min)   │
                    │              ~15% of tests                     │
                    └───────────────────────────────────────────────┘
               ┌─────────────────────────────────────────────────────────┐
               │                    Unit Tests                           │
               │   (Domain, handlers, pure functions, < 30 sec)         │
               │                   ~80% of tests                         │
               └─────────────────────────────────────────────────────────┘
```

### Coverage Targets

| Test Type | Coverage Target | Runtime Target | Focus |
|-----------|-----------------|----------------|-------|
| **Unit** | 90%+ domain/handlers | < 30 seconds | Logic correctness |
| **Integration** | 80%+ infrastructure | < 5 minutes | Data persistence |
| **E2E** | Critical paths | < 15 minutes | User journeys |

---

## Test Organization

### Directory Structure

```
tests/
├── unit/
│   ├── memory/
│   │   ├── domain/
│   │   │   ├── test_memory_block.py
│   │   │   ├── test_memory_entry.py
│   │   │   └── test_events.py
│   │   └── slices/
│   │       ├── test_create_block_handler.py
│   │       ├── test_add_entry_handler.py
│   │       └── test_apply_decay_handler.py
│   ├── ingestion/
│   │   ├── domain/
│   │   └── slices/
│   ├── query/
│   ├── security/
│   └── shared/
│
├── integration/
│   ├── memory/
│   │   ├── test_postgres_repository.py
│   │   └── test_event_store.py
│   ├── ingestion/
│   │   └── test_voyage_ai_adapter.py
│   ├── query/
│   │   ├── test_pgvector_search.py
│   │   └── test_neo4j_graph.py
│   └── conftest.py              # Testcontainers fixtures
│
├── e2e/
│   ├── test_block_lifecycle.py
│   ├── test_query_flow.py
│   ├── test_ingestion_pipeline.py
│   └── conftest.py              # Full stack fixtures
│
├── factories/
│   ├── memory_factories.py
│   ├── ingestion_factories.py
│   └── query_factories.py
│
└── conftest.py                  # Global fixtures
```

---

## Unit Testing

### Domain Entity Tests

Test domain logic without dependencies:

```python
# tests/unit/memory/domain/test_memory_block.py
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from {project}.memory.domain.entities import MemoryBlock, ScopeType
from {project}.memory.domain.value_objects import RelevanceScore
from {project}.memory.domain.exceptions import (
    BlockArchivedError,
    EntryNotFoundError,
)

class TestMemoryBlock:
    @pytest.fixture
    def block(self):
        return MemoryBlock(
            id=uuid4(),
            title="Test Block",
            scope_type=ScopeType.PROJECT,
            scope_id=uuid4(),
            owner_id=uuid4(),
            tenant_id="test-tenant",
            tags=["initial"],
        )

    def test_add_entry_creates_entry(self, block):
        content_id = uuid4()

        entry = block.add_entry(
            content_type="CHUNK",
            content_id=content_id,
            relevance_score=0.9,
        )

        assert entry.content_id == content_id
        assert len(block.entries) == 1

    def test_add_duplicate_entry_raises_error(self, block):
        content_id = uuid4()
        block.add_entry("CHUNK", content_id, 0.9)

        with pytest.raises(EntryAlreadyExistsError):
            block.add_entry("CHUNK", content_id, 0.8)

    def test_archive_prevents_modifications(self, block):
        block.archive()

        with pytest.raises(BlockArchivedError):
            block.add_tag("new-tag")

    def test_apply_decay_reduces_relevance(self, block):
        content_id = uuid4()
        block.add_entry("CHUNK", content_id, 1.0)

        block.apply_decay(decay_factor=0.95)

        entry = block.get_entry(content_id)
        assert entry.relevance_score == 0.95

    def test_pinned_entry_not_decayed(self, block):
        content_id = uuid4()
        entry = block.add_entry("CHUNK", content_id, 1.0)
        entry.pin()

        block.apply_decay(decay_factor=0.95)

        assert entry.relevance_score == 1.0
```

### Command Handler Tests

Test handlers with mocked dependencies:

```python
# tests/unit/memory/slices/test_create_block_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from {project}.memory.slices.create_block.command import CreateBlock
from {project}.memory.slices.create_block.handler import CreateBlockHandler

class TestCreateBlockHandler:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.save = MagicMock()
        app.repository = MagicMock()
        return app

    @pytest.fixture
    def handler(self, mock_app):
        return CreateBlockHandler(app=mock_app)

    @pytest.fixture
    def valid_command(self):
        return CreateBlock(
            title="Test Block",
            scope_type="PROJECT",
            scope_id="proj-123",
            owner_id="user-456",
            tenant_id="tenant-789",
            tags=["test"],
        )

    async def test_handle_returns_block_id(self, handler, valid_command):
        result = await handler.handle(valid_command)

        assert isinstance(result, UUID)

    async def test_handle_saves_aggregate(self, handler, valid_command, mock_app):
        await handler.handle(valid_command)

        mock_app.save.assert_called_once()
        saved_aggregate = mock_app.save.call_args[0][0]
        assert saved_aggregate.title == "Test Block"

    async def test_handle_with_empty_title_raises(self, handler):
        command = CreateBlock(
            title="",
            scope_type="PROJECT",
            scope_id="proj-123",
            owner_id="user-456",
            tenant_id="tenant-789",
        )

        with pytest.raises(ValidationError):
            await handler.handle(command)
```

### Event Sourcing Tests

Test aggregate event emission:

```python
# tests/unit/memory/domain/test_events.py
import pytest
from uuid import uuid4

from {project}.memory.domain.aggregates import MemoryBlockAggregate

class TestMemoryBlockAggregate:
    def test_creation_emits_created_event(self):
        block = MemoryBlockAggregate(
            title="Test Block",
            owner_id="user-1",
            tenant_id="tenant-1",
        )

        events = block.collect_events()

        assert len(events) == 1
        assert events[0].__class__.__name__ == "Created"
        assert events[0].title == "Test Block"

    def test_add_tag_emits_tag_added_event(self):
        block = MemoryBlockAggregate("Test", "u1", "t1")
        block.collect_events()  # Clear creation event

        block.add_tag("important")

        events = block.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "TagAdded"
        assert events[0].tag == "important"

    def test_replay_rebuilds_state(self):
        # Create and modify
        block = MemoryBlockAggregate("Test", "u1", "t1")
        block.add_tag("tag1")
        block.add_tag("tag2")
        content_id = uuid4()
        block.add_entry(content_id)

        # Collect all events
        events = list(block.pending_events)

        # Replay on new instance
        replayed = MemoryBlockAggregate.__new__(MemoryBlockAggregate)
        for event in events:
            replayed._apply(event)

        # State should match
        assert replayed.title == "Test"
        assert "tag1" in replayed.tags
        assert "tag2" in replayed.tags
        assert content_id in replayed.entry_ids
```

---

## Integration Testing

### Repository Tests

Test data persistence with real database:

```python
# tests/integration/memory/test_postgres_repository.py
import pytest
from uuid import uuid4

from {project}.memory.infrastructure.repositories import PostgresBlockRepository

@pytest.mark.integration
class TestPostgresBlockRepository:
    @pytest.fixture
    async def repository(self, db_session):
        return PostgresBlockRepository(db_session)

    @pytest.fixture
    def sample_block(self, block_factory):
        return block_factory.create(
            title="Integration Test",
            tenant_id="test-tenant",
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

    async def test_list_by_scope(self, repository, sample_block):
        await repository.save(sample_block)

        blocks = await repository.list_by_scope(
            scope_type=sample_block.scope_type,
            scope_id=sample_block.scope_id,
            tenant_id=sample_block.tenant_id,
        )

        assert len(blocks) >= 1
        assert any(b.id == sample_block.id for b in blocks)

    async def test_tenant_isolation(self, repository, block_factory):
        block1 = block_factory.create(tenant_id="tenant-a")
        block2 = block_factory.create(tenant_id="tenant-b")

        await repository.save(block1)
        await repository.save(block2)

        # Should only see tenant-a blocks
        blocks = await repository.list_all(tenant_id="tenant-a")

        assert all(b.tenant_id == "tenant-a" for b in blocks)
```

### Testcontainers Fixtures

```python
# tests/integration/conftest.py
import pytest
import asyncio
from testcontainers.postgres import PostgresContainer
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as neo4j:
        yield neo4j

@pytest.fixture
async def db_session(postgres_container):
    import asyncpg

    conn = await asyncpg.connect(
        postgres_container.get_connection_url()
    )

    # Run migrations
    await _run_migrations(conn)

    yield conn

    # Cleanup
    await conn.execute("TRUNCATE memory_blocks CASCADE")
    await conn.close()

async def _run_migrations(conn):
    """Apply database migrations for tests."""
    # ... migration logic
    pass
```

### External Service Tests

```python
# tests/integration/ingestion/test_voyage_ai_adapter.py
import pytest
import os

from {project}.ingestion.infrastructure.adapters import VoyageAIAdapter

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("VOYAGE_API_KEY"),
    reason="VOYAGE_API_KEY not set"
)
class TestVoyageAIAdapter:
    @pytest.fixture
    def adapter(self):
        return VoyageAIAdapter(
            api_key=os.getenv("VOYAGE_API_KEY"),
        )

    async def test_embed_single_text(self, adapter):
        embedding = await adapter.embed("Hello, world!")

        assert len(embedding) == 1024  # voyage-large-2 dimensions
        assert all(isinstance(x, float) for x in embedding)

    async def test_embed_batch(self, adapter):
        texts = ["Text one", "Text two", "Text three"]

        embeddings = await adapter.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 1024 for e in embeddings)
```

---

## End-to-End Testing

### API Flow Tests

```python
# tests/e2e/test_block_lifecycle.py
import pytest
from httpx import AsyncClient
from uuid import uuid4

@pytest.mark.e2e
class TestBlockLifecycle:
    @pytest.fixture
    async def client(self, app):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def auth_headers(self, test_user_token):
        return {"Authorization": f"Bearer {test_user_token}"}

    async def test_full_block_lifecycle(self, client, auth_headers):
        # 1. Create block
        create_response = await client.post(
            "/api/v1/memory/blocks",
            json={
                "title": "E2E Test Block",
                "scope_type": "PROJECT",
                "scope_id": str(uuid4()),
                "tags": ["e2e", "test"],
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        block_id = create_response.json()["id"]

        # 2. Get block
        get_response = await client.get(
            f"/api/v1/memory/blocks/{block_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "E2E Test Block"

        # 3. Add entry
        content_id = str(uuid4())
        entry_response = await client.post(
            f"/api/v1/memory/blocks/{block_id}/entries",
            json={
                "content_type": "CHUNK",
                "content_id": content_id,
            },
            headers=auth_headers,
        )
        assert entry_response.status_code == 201

        # 4. Verify entry
        block_response = await client.get(
            f"/api/v1/memory/blocks/{block_id}",
            headers=auth_headers,
        )
        entries = block_response.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["content_id"] == content_id

        # 5. Archive block
        archive_response = await client.post(
            f"/api/v1/memory/blocks/{block_id}/archive",
            headers=auth_headers,
        )
        assert archive_response.status_code == 200

        # 6. Verify archived
        final_response = await client.get(
            f"/api/v1/memory/blocks/{block_id}",
            headers=auth_headers,
        )
        assert final_response.json()["status"] == "ARCHIVED"
```

### Query Flow Tests

```python
# tests/e2e/test_query_flow.py
import pytest

@pytest.mark.e2e
class TestQueryFlow:
    async def test_search_returns_relevant_results(
        self,
        client,
        auth_headers,
        seeded_documents,
    ):
        # Search for known content
        response = await client.post(
            "/api/v1/query/search",
            json={
                "query": "machine learning algorithms",
                "scope": {"type": "PROJECT", "id": "test-project"},
                "limit": 10,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) > 0

        # Should find the ML document
        assert any(
            "machine learning" in r["content"].lower()
            for r in results
        )

    async def test_security_trimming_filters_unauthorized(
        self,
        client,
        auth_headers,
        restricted_documents,
    ):
        # Search should not return restricted content
        response = await client.post(
            "/api/v1/query/search",
            json={
                "query": "confidential report",
                "limit": 50,
            },
            headers=auth_headers,
        )

        results = response.json()["results"]

        # User should not see restricted documents
        assert not any(
            r["document_id"] in restricted_documents
            for r in results
        )
```

---

## Test Utilities

### Factories

```python
# tests/factories/memory_factories.py
from dataclasses import dataclass, field
from uuid import uuid4, UUID
from datetime import datetime, UTC
from typing import Optional

from {project}.memory.domain.entities import MemoryBlock, ScopeType

@dataclass
class MemoryBlockFactory:
    """Factory for creating test MemoryBlock instances."""

    _sequence: int = field(default=0, init=False)

    def create(
        self,
        id: Optional[UUID] = None,
        title: Optional[str] = None,
        scope_type: ScopeType = ScopeType.PROJECT,
        scope_id: Optional[UUID] = None,
        owner_id: Optional[UUID] = None,
        tenant_id: str = "test-tenant",
        tags: Optional[list[str]] = None,
        **kwargs,
    ) -> MemoryBlock:
        self._sequence += 1

        return MemoryBlock(
            id=id or uuid4(),
            title=title or f"Test Block {self._sequence}",
            scope_type=scope_type,
            scope_id=scope_id or uuid4(),
            owner_id=owner_id or uuid4(),
            tenant_id=tenant_id,
            tags=tags or [],
            created_at=kwargs.get("created_at", datetime.now(UTC)),
            **kwargs,
        )

    def create_batch(self, count: int, **kwargs) -> list[MemoryBlock]:
        return [self.create(**kwargs) for _ in range(count)]
```

### Property-Based Testing

```python
# tests/unit/memory/domain/test_properties.py
from hypothesis import given, strategies as st
import hypothesis

from {project}.memory.domain.value_objects import RelevanceScore

class TestRelevanceScoreProperties:
    @given(st.floats(min_value=0.0, max_value=1.0))
    def test_valid_scores_accepted(self, value):
        score = RelevanceScore(value)
        assert score.value == value

    @given(st.floats().filter(lambda x: x < 0 or x > 1))
    def test_invalid_scores_rejected(self, value):
        with pytest.raises(ValueError):
            RelevanceScore(value)

    @given(
        st.floats(min_value=0.0, max_value=1.0),
        st.floats(min_value=0.0, max_value=1.0),
    )
    def test_decay_always_reduces(self, initial, factor):
        hypothesis.assume(factor < 1.0)

        score = RelevanceScore(initial)
        decayed = score.apply_decay(factor)

        assert decayed.value <= initial
```

---

## Test Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto

markers =
    unit: Unit tests (fast, no I/O)
    integration: Integration tests (database, external services)
    e2e: End-to-end tests (full stack)
    slow: Slow tests (run separately)

addopts =
    -v
    --tb=short
    --strict-markers
```

### Running Tests

```bash
# All unit tests (fast)
pytest tests/unit -v

# Integration tests
pytest tests/integration -v -m integration

# E2E tests
pytest tests/e2e -v -m e2e

# With coverage
pytest tests/unit --cov={Project} --cov-report=html

# Parallel execution
pytest tests/unit -n auto
```

---

## See Also

- [PADR-104: Testing Strategy](../../decisions/patterns/PADR-104-testing-strategy.md)
- [Error Handling](con-error-handling.md) - Testing error paths
