<!-- Derived from {Project} PADR-110-application-lifecycle -->
# PADR-110: Application Lifecycle Management

**Status:** Accepted
**Date:** 2026-02-02
**Deciders:** Architecture Team
**Categories:** Pattern, API

---

## Context

Each of the 11 command endpoints instantiated a new `CoreApplication()` per request via a local `get_memory_app()` dependency:

```python
def get_memory_app() -> CoreApplication:
    return CoreApplication()  # New instance per request
```

Each `CoreApplication()` call creates new eventsourcing infrastructure (mappers, recorders, connection pools), resulting in unnecessary resource consumption and preventing connection pool sharing.

The official [pyeventsourcing/example-fastapi](https://github.com/pyeventsourcing/example-fastapi) uses a module-level singleton: `accounts = BankAccounts()`.

## Decision

We use a **lifespan-managed singleton** with **FastAPI Depends injection**:

### Singleton Creation

The `CoreApplication` instance is created once during FastAPI lifespan startup:

```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.memory_app = CoreApplication()
    yield
```

### Shared Dependency

A centralized dependency in `memory/_shared/dependencies.py`:

```python
def get_memory_app(request: Request) -> CoreApplication:
    return request.app.state.memory_app

MemoryApp = Annotated[CoreApplication, Depends(get_memory_app)]
```

### Endpoint Usage

All 11 command endpoints use the shared `MemoryApp` type alias:

```python
@router.post("/blocks")
def create_block(app: MemoryApp) -> CreateBlockResponse:
    handler = CreateBlockHandler(app)
    ...
```

## Rationale

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Singleton pattern | Lifespan-managed | Proper lifecycle, cleaner than module-level |
| DI mechanism | FastAPI Depends | Testable via `dependency_overrides` |
| Centralized dep | Shared module | Single import for all endpoints |
| Type alias | `MemoryApp` | Clean endpoint signatures |

## Consequences

### Positive

1. **Single instance** - One `CoreApplication` shares connection pool
2. **Proper lifecycle** - Created at startup, available for cleanup at shutdown
3. **Testable** - `app.dependency_overrides[get_memory_app]` for test isolation
4. **DRY** - Eliminates 11 duplicate `get_memory_app()` definitions

### Negative

1. **Global state** - Application singleton in `app.state`
2. **Startup dependency** - Endpoints fail if lifespan doesn't run

### Mitigations

| Risk | Mitigation |
|------|------------|
| Missing singleton | Startup logs confirm initialization; fails fast |
| Test isolation | Each test creates its own `CoreApplication` via overrides |

## Alternatives Considered

| Alternative | Rejection Reason |
|-------------|------------------|
| Module-level singleton | No lifecycle management; harder to test |
| Per-request instantiation | Wastes resources; no pool sharing |
| Container framework (dependency-injector) | Over-engineering for single dependency |

## Related Decisions

- [PADR-109: Sync-First Event Sourcing](./PADR-109-sync-first-eventsourcing.md) - Async strategy
- [PADR-107: API Documentation](./PADR-107-api-documentation.md) - Endpoint patterns

## References

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [pyeventsourcing/example-fastapi](https://github.com/pyeventsourcing/example-fastapi)
