<!-- Derived from {Project} PADR-109-sync-first-eventsourcing -->
# PADR-109: Sync-First Event Sourcing with Async Read Path

**Status:** Accepted
**Date:** 2026-02-02
**Deciders:** Architecture Team
**Categories:** Pattern, Persistence, API

---

## Context

The Python eventsourcing library (v9.5.2) is entirely synchronous. All core operations (`Application.save()`, `Repository.get()`, `ProcessApplication.policy()`) are blocking. GitHub Issue #233 (async support request) has been open since September 2021 with no resolution timeline.

Our codebase had two async/sync impedance patterns:

1. **Command endpoints** declared as `async def` but called only sync eventsourcing code (no `await` expressions). FastAPI ran these on the event loop, where they blocked.

2. **Projections** used a `_run_async()` bridge with `ThreadPoolExecutor` + `asyncio.run()` to call async repositories from sync `policy()` handlers. This introduced threading complexity and fragile event loop management.

## Decision

We adopt a **sync-first strategy for event sourcing operations** with an **async read path for queries**:

### Command Endpoints: `def` (sync)

All 11 command endpoints use plain `def` instead of `async def`. FastAPI automatically offloads sync handlers to a threadpool, matching the eventsourcing library's blocking nature.

### Query Endpoints: `async def` (async)

The 3 query endpoints (`get_block`, `query_blocks_by_scope`, `list_native_files`) remain `async def` because they use `await` with async SQLAlchemy repositories for genuine concurrent I/O.

### Projections: Sync Repositories

Projections use dedicated sync repository classes (`SyncBlockSummaryRepository`, `SyncNativeFileRepository`) that call `session.execute()` directly. This eliminates the `_run_async()` bridge entirely.

### Dual Sync/Async Repositories

- **Sync repos** (`*_sync.py`): Used by projections for event-driven writes. Only include methods needed by projection handlers.
- **Async repos** (existing): Used by query endpoints for read operations with pagination, filtering, and concurrent I/O.

Both use the same `postgresql+psycopg://` URL format. SQLAlchemy's psycopg3 dialect auto-selects sync or async mode based on `create_engine()` vs `create_async_engine()`.

## Rationale

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Command handlers | `def` (sync) | FastAPI offloads to threadpool; matches eventsourcing library |
| Query handlers | `async def` | Genuine async DB reads provide concurrency benefit |
| Projection repos | Sync | `policy()` is sync; eliminates ThreadPoolExecutor bridge |
| Dual repos | Yes | Clean separation; sync writes, async reads |

### Source Verification

- **FastAPI docs**: "When you declare a path operation function with normal `def`, FastAPI runs it in an external threadpool." Mixing `def` and `async def` is explicitly supported.
- **SQLAlchemy docs**: psycopg3 dialect supports both sync and async with the same URL format.
- **eventsourcing**: Official [example-fastapi](https://github.com/pyeventsourcing/example-fastapi) uses module-level singleton with all sync `def` handlers.

## Consequences

### Positive

1. **Simpler projections** - No threading, no event loop bridge, direct sync calls
2. **Correct FastAPI semantics** - Sync handlers run in threadpool as intended
3. **Matches library design** - Follows official eventsourcing patterns
4. **Type safety** - No `Any` returns from `_run_async()` bridge

### Negative

1. **Mixed `def`/`async def`** - Developers must understand which to use
2. **Dual repo maintenance** - Sync and async repos for the same tables

### Mitigations

| Risk | Mitigation |
|------|------------|
| Wrong handler type | Naming convention: command slices use `def`, query slices use `async def` |
| Repo drift | Sync repos only have projection-write methods; async repos have all methods |
| Developer confusion | This ADR serves as reference; code comments cite PADR-109 |

## Alternatives Considered

| Alternative | Rejection Reason |
|-------------|------------------|
| All async with bridge | ThreadPoolExecutor adds complexity; fragile event loop management |
| All sync | Loses concurrency benefits for query endpoints with DB reads |
| Wait for async eventsourcing | GitHub Issue #233 open since 2021; no timeline |
| Third-party asyncsourcing | Abandoned/non-functional project |

## Related Decisions

- [PADR-102: Hexagonal Ports](./PADR-102-hexagonal-ports.md) - Repository abstraction
- [PADR-107: API Documentation](./PADR-107-api-documentation.md) - Endpoint patterns
- [PADR-110: Application Lifecycle](./PADR-110-application-lifecycle.md) - CoreApplication singleton
- Delta counter projections use the sync-first pattern for event processing — see [ref-infra-delta-counter-projection.md](../../domains/event-store-cqrs/references/ref-infra-delta-counter-projection.md)

## References

- [FastAPI Async Docs](https://fastapi.tiangolo.com/async/)
- [SQLAlchemy PostgreSQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [eventsourcing 9.5.2 Docs](https://eventsourcing.readthedocs.io/en/stable/)
- [pyeventsourcing/example-fastapi](https://github.com/pyeventsourcing/example-fastapi)
- [GitHub Issue #233: Async Support](https://github.com/pyeventsourcing/eventsourcing/issues/233)

## Changelog

### 2026-02-05: Cross-Reference Addition (F-100-004)

- Added cross-reference to delta counter projection (reinforcement metrics projection workers use sync-first pattern)
- Core decision unchanged; status remains Accepted
