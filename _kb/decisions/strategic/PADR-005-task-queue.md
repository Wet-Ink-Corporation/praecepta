<!-- Derived from {Project} PADR-005-task-queue -->
# PADR-005: TaskIQ for Asynchronous Task Processing

**Status:** Accepted
**Date:** 2026-01-26
**Deciders:** Architecture Team
**Categories:** Strategic, Infrastructure

---

## Context

{Project} requires background task processing for:

- **Scheduled jobs:** Scheduled cleanup calculations on resources
- **Async processing:** Embedding generation for ingested documents
- **Event-driven workflows:** Projection updates, notification delivery

The project's technology stack is fully async-first:

- FastAPI 0.110+ (async web framework)
- AnyIO 4.x (structured concurrency)
- eventsourcing 9.5+ (async-compatible)
- Redis 7.x (already in stack for caching)

We need a task queue that aligns with this async architecture without requiring adapters or workarounds.

## Decision

**We will use TaskIQ as the task queue library**, with Redis Stream as the broker and result backend.

### Core Configuration

```python
from taskiq_redis import RedisStreamBroker, RedisAsyncResultBackend

result_backend = RedisAsyncResultBackend(
    redis_url="redis://localhost:6379",
)

broker = RedisStreamBroker(
    url="redis://localhost:6379",
).with_result_backend(result_backend)
```

### Task Definition

```python
from {project}.shared.infrastructure.taskiq import broker

@broker.task
async def generate_embedding(chunk_id: str, text: str) -> list[float]:
    """Generate embedding vector for a text Segment."""
    async with get_embedding_client() as client:
        return await client.embed(text)

@broker.task(schedule=[{"cron": "0 * * * *"}])
async def apply_relevance_decay() -> int:
    """Hourly Scheduled cleanup across all resources."""
    async with get_application() as app:
        return await app.decay_all_blocks()
```

### FastAPI Integration

```python
from taskiq_fastapi import init as taskiq_init
from {project}.shared.infrastructure.taskiq import broker

taskiq_init(broker, "{Project}.main:app")
```

## Rationale

### Why TaskIQ?

| Requirement | TaskIQ Capability |
|-------------|-------------------|
| **Async-first** | Native async/await throughout; no sync wrappers needed |
| **FastAPI integration** | `taskiq-fastapi` shares DI context between routes and tasks |
| **Redis broker** | Redis Stream with acknowledgement (reliable delivery) |
| **Scheduling** | `TaskiqScheduler` with cron expressions |
| **Type safety** | PEP-612 support for full IDE autocompletion |
| **AnyIO compatible** | Works with asyncio/trio backends |

### Performance

Benchmark: 20,000 jobs, 10 workers, Redis broker ([source](https://stevenyue.com/blogs/exploring-python-task-queue-libraries-with-load-test)):

| Library | Time (seconds) | Relative |
|---------|----------------|----------|
| **TaskIQ** | 2.03 | 1.0x (fastest) |
| Celery (threads) | 11.68 | 5.8x slower |
| Celery (processes) | 17.60 | 8.7x slower |

### Why Not Celery?

| Aspect | Celery Limitation |
|--------|-------------------|
| **Async support** | No native async; requires sync wrappers or eventlet/gevent |
| **Redis reliability** | Uses Redis lists without acknowledgement (message loss on worker crash) |
| **FastAPI DI** | No dependency injection sharing with web routes |
| **Maintenance stance** | [Ideological resistance to asyncio](https://github.com/celery/celery/discussions/9049) |

While Celery is battle-tested with 12+ years of production use, its sync-first architecture creates impedance mismatch with our fully async stack.

### Why Not Dramatiq?

- No native FastAPI integration
- Less active development in async direction
- Similar performance to TaskIQ but without DI sharing

## Consequences

### Positive

1. **Architecture alignment:** Native async matches FastAPI, AnyIO, eventsourcing
2. **DI sharing:** Same database connections, SpiceDB clients in routes and tasks
3. **Reliable delivery:** Redis Stream acknowledgement prevents message loss
4. **Performance:** 5-8x faster than Celery for same workload
5. **Developer experience:** Hot reload, type hints, IDE autocompletion

### Negative

1. **Smaller community:** ~1.8k stars vs Celery's 24k; fewer StackOverflow answers
2. **Less production proof:** Newer library with less enterprise deployment history
3. **No task abort:** Cannot revoke running tasks (Celery supports this)
4. **Sync limitation:** Cannot enqueue tasks from synchronous code paths

### Mitigations

| Risk | Mitigation |
|------|------------|
| Smaller community | Pin versions, comprehensive integration tests, monitor GitHub issues |
| Less proven | Start with non-critical paths (projections), expand gradually |
| No task abort | Design tasks to be short-lived or checkpoint-based |
| Sync limitation | N/A—our codebase is fully async |

## Implementation Notes

### Worker Startup

```bash
# Start worker
taskiq worker {Project}.shared.infrastructure.taskiq:broker

# Start scheduler (single instance only)
taskiq scheduler {Project}.shared.infrastructure.taskiq:scheduler --skip-first-run
```

### Package Structure

```
src/{project}/shared/infrastructure/
├── taskiq.py           # Broker and scheduler configuration
└── tasks/
    ├── __init__.py
    ├── Processing.py    # Embedding, chunking tasks
    ├── Lifecycle.py     # Scheduled cleanup, cleanup
    └── projections.py  # Neo4j graph updates
```

### Testing

```python
from taskiq import InMemoryBroker

@pytest.fixture
async def test_broker():
    broker = InMemoryBroker()
    await broker.startup()
    yield broker
    await broker.shutdown()

async def test_embedding_task(test_broker):
    result = await generate_embedding.kiq(chunk_id="123", text="hello world")
    embedding = await result.wait_result()
    assert len(embedding) == 1024
```

### Scheduling Configuration

```python
from taskiq import TaskiqScheduler
from taskiq.schedules import CronSpec
from taskiq_redis import ListRedisScheduleSource

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        LabelScheduleSource(broker),  # @broker.task(schedule=[...])
        ListRedisScheduleSource(redis_url),  # Dynamic schedules
    ],
)
```

## Related Decisions

- PADR-001: Event Sourcing for State Management
- PADR-002: Modular Monolith Architecture
- Technology Decisions: Redis 7.x selection

## References

- [TaskIQ Documentation](https://taskiq-python.github.io/)
- [TaskIQ GitHub](https://github.com/taskiq-python/taskiq)
- [TaskIQ-Redis](https://github.com/taskiq-python/taskiq-redis)
- [TaskIQ-FastAPI](https://github.com/taskiq-python/taskiq-fastapi)
- [Performance Benchmark](https://stevenyue.com/blogs/exploring-python-task-queue-libraries-with-load-test)
- [Celery Async Discussion](https://github.com/celery/celery/discussions/9049)
