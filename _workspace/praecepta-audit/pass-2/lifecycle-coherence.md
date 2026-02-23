# Lifecycle Coherence -- Cross-Cutting Audit

**Theme:** XC-L (Lifecycle Coherence)
**Packages Analyzed:** infra-fastapi, infra-eventsourcing, infra-persistence, infra-observability, infra-auth, infra-taskiq
**Pass 1 Reports Used:** All five infra package audit reports
**Date:** 2026-02-22

---

## Lifecycle Inventory

### Lifespan Hook Registration Summary

| Package | Has LifespanContribution? | Entry Point Registered? | Priority |
|---------|--------------------------|------------------------|----------|
| infra-observability | Yes | `praecepta.lifespan: observability` | 50 |
| infra-eventsourcing (event store) | Yes | `praecepta.lifespan: event_store` | 100 |
| infra-eventsourcing (projections) | Yes | `praecepta.lifespan: projection_runner` | 200 |
| infra-persistence | **No** | **None** | N/A |
| infra-auth | **No** | **None** | N/A |
| infra-taskiq | **No** | **None** | N/A |

### Startup Order (by ascending priority -- lower starts first)

| Priority | Package | Hook | What it initializes |
|----------|---------|------|---------------------|
| 50 | infra-observability | `_observability_lifespan` | structlog configuration (`configure_logging()`), OpenTelemetry tracing (`configure_tracing()`) |
| 100 | infra-eventsourcing | `event_store_lifespan` | Bridges `EventSourcingSettings` to `os.environ`, initializes `EventStoreFactory` singleton |
| 200 | infra-eventsourcing | `projection_runner_lifespan` | Discovers projection classes via entry points, creates `SubscriptionProjectionRunner` per upstream application, starts LISTEN/NOTIFY subscriptions |

### Shutdown Order (reverse of startup via AsyncExitStack LIFO)

| Priority | Package | Hook | What it tears down |
|----------|---------|------|--------------------|
| 200 | infra-eventsourcing | `projection_runner_lifespan` | Stops projection runners in reverse order (`runner.stop()`) |
| 100 | infra-eventsourcing | `event_store_lifespan` | Closes `EventStoreFactory` singleton (`store.close()`) |
| 50 | infra-observability | `_observability_lifespan` | Flushes and shuts down OpenTelemetry `TracerProvider` (`shutdown_tracing()`) |

### Unmanaged Resources (no lifespan participation)

| Package | Resource | Creation Pattern | Cleanup Pattern |
|---------|----------|------------------|-----------------|
| infra-persistence | SQLAlchemy async engine (pool_size=20, max_overflow=10) | Lazy singleton on first `get_engine()` call | `dispose_engine()` exists but is **never called** |
| infra-persistence | SQLAlchemy sync engine (pool_size=5, max_overflow=5) | Lazy singleton on first `get_sync_engine()` call | `dispose_engine()` exists but is **never called** |
| infra-persistence | Redis client (via `RedisFactory`) | Lazy singleton via `@lru_cache` on `get_redis_factory()` | `factory.close()` exists but is **never called** |
| infra-persistence | Tenant context event handler | `register_tenant_context_handler()` exists but is **never called outside tests** | N/A (idempotent listener) |
| infra-auth | `httpx.AsyncClient` for OIDC | Per-call instantiation (`async with httpx.AsyncClient()`) | Closed per-call via context manager |
| infra-auth | `JWKSProvider` / `PyJWKClient` | Created during middleware init, stored in `app.state` | Never explicitly closed (relies on GC) |
| infra-taskiq | `RedisStreamBroker` | **Module-level instantiation at import time** | `broker.shutdown()` is **never called** |
| infra-taskiq | `RedisAsyncResultBackend` | **Module-level instantiation at import time** | Never explicitly closed |
| infra-taskiq | `TaskiqScheduler` | **Module-level instantiation at import time** | Never explicitly stopped |

### Dependency Graph

```
infra-observability (priority 50)
    |
    v
infra-persistence (NO LIFESPAN -- database engines, Redis)
    |
    v
infra-eventsourcing / event_store (priority 100)
    |  - depends on: database being reachable (persistence layer)
    |  - depends on: os.environ being populated (self-bridges from settings)
    v
infra-eventsourcing / projections (priority 200)
    |  - depends on: event store initialized (priority 100)
    |  - depends on: sync database sessions (persistence layer)
    |  - depends on: structlog configured (observability, priority 50)
    v
infra-auth (NO LIFESPAN -- JWKS, OIDC)
    |  - depends on: network access to IdP (external)
    |
infra-taskiq (NO LIFESPAN -- Redis broker)
    |  - depends on: Redis being reachable (same as persistence)
```

---

## Findings

| ID | Severity | Packages Affected | Description | Recommendation |
|----|----------|-------------------|-------------|----------------|
| XC-L1-01 | CRITICAL | infra-persistence | **Database engines have no lifespan hook.** `dispose_engine()` is defined but never called from any lifespan, shutdown handler, or atexit registration. On application shutdown, up to 40 connections per process (20+10 async, 5+5 sync) are abandoned without graceful close. PostgreSQL must detect them via `tcp_keepalives_idle` timeout, which can take minutes. During rolling deployments, connection exhaustion is possible as old processes hold connections while new processes open fresh pools. | Create a `LifespanContribution` in `infra-persistence` (priority 75, between observability at 50 and event store at 100) that calls `dispose_engine()` on shutdown and optionally `register_tenant_context_handler()` on startup. Register it as `[project.entry-points."praecepta.lifespan"] persistence = "praecepta.infra.persistence:lifespan_contribution"`. |
| XC-L1-02 | CRITICAL | infra-taskiq | **Broker resources are created at import time with no lifecycle management.** `RedisStreamBroker`, `RedisAsyncResultBackend`, and `TaskiqScheduler` are module-level globals instantiated as side effects of `import praecepta.infra.taskiq`. `broker.startup()` is never called (consumer groups not initialized) and `broker.shutdown()` is never called (connections leaked, unacked messages lost). This was also identified as TQ-7 and TQ-11 in the Pass 1 report. | Convert to factory functions with lazy initialization. Create a `LifespanContribution` (priority 150, after event store but before projections) that calls `await broker.startup()` on entry and `await broker.shutdown()` on exit. Register via `[project.entry-points."praecepta.lifespan"]`. |
| XC-L1-03 | HIGH | infra-persistence | **`register_tenant_context_handler()` is never called in production.** The function exists and is tested, but no lifespan hook or app factory code invokes it. The SQLAlchemy `after_begin` event listener for RLS `SET LOCAL` is never registered outside of test fixtures. This means **Row-Level Security tenant isolation is non-functional** in a deployed application unless the consumer manually calls the registration. | Include `register_tenant_context_handler()` in the persistence lifespan hook (see XC-L1-01). This must execute before any request-handling code runs. |
| XC-L1-04 | HIGH | infra-persistence | **Redis client (`RedisFactory`) has no shutdown path.** `RedisFactory.close()` exists but is never invoked from any lifespan hook. The `@lru_cache` singleton means the factory persists for the process lifetime, and the underlying `aioredis` connection pool is never explicitly closed. | Include `await get_redis_factory().close()` in the persistence lifespan shutdown path. |
| XC-L1-05 | HIGH | infra-persistence, infra-eventsourcing | **Database must be reachable before event store, but persistence has no startup hook.** The event store lifespan (priority 100) bridges settings to `os.environ` and initializes the `EventStoreFactory`, but the actual database connection pools in `infra-persistence` are created lazily on first use. If the database is unreachable, the failure surfaces at first-request time rather than at startup. There is no startup validation that the database is accessible. | Add a startup health check to the persistence lifespan that validates database connectivity (e.g., `SELECT 1` via `pool_pre_ping` or explicit check). Fail fast at startup rather than at first request. |
| XC-L1-06 | MEDIUM | infra-eventsourcing, infra-persistence | **Implicit ordering dependency between persistence and event store is not enforced.** The event store (priority 100) depends on PostgreSQL being accessible, but there is no persistence lifespan hook with a lower priority to guarantee the database layer is initialized first. Currently this works because persistence uses lazy singletons (no startup needed), but if persistence gains a startup hook, its priority must be lower than 100. This constraint is documented only in projection_lifespan.py comments, not programmatically. | When creating the persistence lifespan hook, assign priority 75 and add a comment documenting the ordering constraint. Consider adding a startup-order validation in `compose_lifespan` that checks declared dependencies. |
| XC-L1-07 | MEDIUM | infra-eventsourcing | **Projection runner startup failure partially handled but could leave event store initialized.** The `projection_runner_lifespan` correctly stops already-started runners on failure (`except` block at line 139-143), but then re-raises. The `AsyncExitStack` in `compose_lifespan` will then unwind the event store and observability hooks. This is correct behavior -- however, there is no logging from `compose_lifespan` itself indicating which hook failed. The raw exception propagates without operational context. | Add structured logging in `compose_lifespan` around `stack.enter_async_context(ctx)` that records which hook (by priority and name) failed. This was also identified as F-09 in the infra-fastapi Pass 1 report. |
| XC-L1-08 | MEDIUM | infra-auth | **No lifespan hook for JWKS provider or OIDC client initialization.** The `JWKSProvider` is documented as "created once during app lifespan startup, stored in app.state" but no lifespan hook performs this initialization. The auth middleware contributions register only middleware classes, not lifespan hooks. The JWKS cache is populated lazily on first JWT validation request, meaning the first request after startup incurs a cold-start latency penalty (JWKS fetch + key parsing). | Create a lifespan hook (priority 80, after observability but before event store) that pre-warms the JWKS cache and validates IdP reachability. This enables fail-fast if the OIDC issuer is misconfigured. |
| XC-L1-09 | MEDIUM | infra-observability, infra-fastapi | **Middleware priority semantics create implicit lifecycle coupling.** `TraceContextMiddleware` (priority 20) documents itself as "outermost band (0-99)" but runs inner to `RequestIdMiddleware` (priority 10). The observability package's `request_id` correlation depends on `infra-fastapi`'s `RequestIdMiddleware` binding it to `structlog.contextvars` first. This is a convention-gap dependency -- it works but is fragile and undocumented at the code level. | Clarify the middleware priority contract in a shared location (e.g., `LifespanContribution` or `MiddlewareContribution` docstring). Fix the misleading "outermost band" comment on `TraceContextMiddleware`. |
| XC-L1-10 | LOW | infra-fastapi | **Health check provides no readiness signal.** The `/healthz` endpoint returns `{"status": "ok"}` unconditionally. It does not verify database connectivity, event store accessibility, projection runner status, or Redis reachability. Kubernetes readiness probes using this endpoint will route traffic to pods that may have non-functional database connections or stalled projections. | Implement a `/readyz` endpoint that aggregates health from registered providers. Each infrastructure package should contribute a health check function via entry points (e.g., `praecepta.health_checks`). |
| XC-L1-11 | LOW | All packages | **No lifespan priority constants or bands are defined centrally.** Priorities are scattered across packages as magic numbers (50, 100, 200) with only inline comments explaining the ordering rationale. There is no shared constants module or enum defining the priority bands. | Define priority band constants in `praecepta.foundation.application` (e.g., `PRIORITY_OBSERVABILITY = 50`, `PRIORITY_PERSISTENCE = 75`, `PRIORITY_EVENT_STORE = 100`, `PRIORITY_TASK_QUEUE = 150`, `PRIORITY_PROJECTIONS = 200`). Reference these from each package's lifespan contribution. |

---

## Analysis

### Overall Lifecycle Coherence Assessment: WEAK

Of the six infrastructure packages analyzed, only two (infra-observability and infra-eventsourcing) participate in the lifespan protocol. Three packages (infra-persistence, infra-auth, infra-taskiq) manage resources that require explicit initialization and/or cleanup but have no lifespan hooks. The fourth (infra-fastapi) orchestrates the lifespan protocol itself and does not need its own hook.

### The Persistence Gap (XC-L1-01, XC-L1-03, XC-L1-04, XC-L1-05)

The most impactful finding is that `infra-persistence` -- the foundational data access layer -- has no lifespan participation whatsoever. This creates four cascading problems:

1. **Connection leaks on shutdown.** `dispose_engine()` exists as a cleanup function but is orphaned -- no code path calls it. On each application shutdown, 40 database connections and an unknown number of Redis connections are abandoned.

2. **RLS tenant isolation is non-functional.** `register_tenant_context_handler()` must be called once at startup to register the SQLAlchemy `after_begin` event listener that sets `app.current_tenant` via `SET LOCAL`. Without this registration, RLS policies receive no tenant context, and depending on the policy design, either all rows are visible (data leak) or no rows are visible (data loss). This function is only called in test fixtures.

3. **No fail-fast on database unreachability.** The lazy singleton pattern means database connection failures surface at first-request time rather than at startup. In a Kubernetes deployment, the pod passes readiness checks and receives traffic before discovering the database is unreachable.

4. **Redis client never closed.** The `RedisFactory` singleton created via `@lru_cache` persists for the process lifetime with no shutdown path.

### The TaskIQ Gap (XC-L1-02)

The `infra-taskiq` package has the worst lifecycle coherence of any package. Resources are created at import time (violating XC-L1), `startup()` is never called (consumer groups not initialized), and `shutdown()` is never called (connections leaked, messages potentially lost). This package appears to be early scaffold that has not been integrated with the lifespan protocol used by sibling packages.

### What Works Well

The lifespan composition mechanism in `infra-fastapi` is well-designed:

- `compose_lifespan()` sorts hooks by priority and uses `AsyncExitStack` for guaranteed LIFO teardown.
- The `AsyncExitStack` pattern ensures that if hook N fails during startup, hooks 1 through N-1 are properly torn down.
- The eventsourcing package correctly uses two priority levels (100 for event store, 200 for projections) with explicit documentation of the ordering dependency.
- The observability package correctly uses priority 50 to ensure logging and tracing are available before any other infrastructure initializes.

### Shutdown Ordering Correctness

For the hooks that do exist, shutdown ordering is correct by construction:

1. Projections stop (priority 200) -- runners cease event consumption
2. Event store closes (priority 100) -- connection pools released
3. Tracing shuts down (priority 50) -- pending spans flushed to collector

This is the correct reverse order. However, the gap is that database engine disposal and Redis cleanup are not part of this sequence at all.

### Failure Scenario: Rolling Deployment

Consider a rolling deployment where old pods are drained while new pods start:

1. Old pod receives SIGTERM.
2. FastAPI calls `lifespan.__aexit__()`.
3. `AsyncExitStack` unwinds: projections stop, event store closes, tracing flushes.
4. **Database connections are NOT closed** (no persistence lifespan hook).
5. **Redis connections are NOT closed** (no persistence or taskiq lifespan hook).
6. **TaskIQ broker is NOT shut down** (no taskiq lifespan hook).
7. Pod terminates. OS closes TCP sockets abruptly.
8. PostgreSQL detects stale connections via keepalive timeout (default ~2 hours on many systems).
9. Meanwhile, new pod opens 40 fresh connections.
10. After several rolling deployments, PostgreSQL `max_connections` is exhausted.

### Recommended Priority Band Allocation

If all findings are addressed, the target startup order should be:

| Priority | Package | Hook | Rationale |
|----------|---------|------|-----------|
| 50 | infra-observability | Logging + tracing | Must be first so all subsequent hooks have structured logging |
| 75 | infra-persistence | Database engines + Redis + tenant context | Must be before event store; database must be reachable |
| 80 | infra-auth | JWKS pre-warm + IdP validation | Can run in parallel with persistence conceptually, but ordered after for simplicity |
| 100 | infra-eventsourcing | Event store init + env bridging | Depends on database being accessible |
| 150 | infra-taskiq | Broker startup | Depends on Redis being accessible |
| 200 | infra-eventsourcing | Projection runners | Depends on event store + database sessions |

Shutdown would then correctly reverse: projections, taskiq broker, event store, auth cleanup, persistence disposal, tracing flush.
