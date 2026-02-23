# Remediation Backlog

## Overview

The consolidated audit produced **42 unique findings** across five infrastructure packages and cross-cutting concerns. Distribution by severity: 4 CRITICAL, 12 HIGH, 19 MEDIUM, 11 LOW (note: some original counts were adjusted during deduplication in Pass 3; this backlog covers all 42 finding IDs CF-01 through CF-42).

Priority classification after triage:

| Priority | Count | Description |
|----------|-------|-------------|
| P1 | 10 | CRITICAL and HIGH items affecting correctness, security, or resource safety |
| P2 | 17 | MEDIUM items affecting performance, maintainability, or convention compliance |
| P3 | 11 | LOW items and deferred improvements |

Four findings overlap or are preconditions for others; the dependency graph at the end captures these relationships.

## Priority Classification

- **P1 -- Fix Before Next Release:** CRITICAL and HIGH severity items that affect correctness, security, or resource safety
- **P2 -- Fix Before Beta:** MEDIUM severity items that affect performance, maintainability, or convention compliance
- **P3 -- Improvement Backlog:** LOW severity items and nice-to-haves

---

## P1 -- Fix Before Next Release

| ID | Finding | Package | Effort | Depends On | Verification |
|----|---------|---------|--------|------------|--------------|
| CF-02 | Persistence has no lifespan hook; RLS tenant isolation non-functional in production | infra-persistence | M | CF-07, CF-08 | `make verify`; integration test calling endpoint and asserting tenant-scoped query |
| CF-01 | SQL identifier injection in RLS helpers | infra-persistence | S | -- | `make test-unit`; new test with SQL metacharacters in table name |
| CF-03 | TaskIQ broker never started/stopped; no lifespan hook | infra-taskiq | L | CF-12, CF-27 | `make verify`; integration test confirming `startup()`/`shutdown()` called |
| CF-04 | Aggregate PostgreSQL connections exceed `max_connections=100` | cross-cutting | M | CF-07, CF-14 | `make test-unit`; startup health check logs total budget |
| CF-07 | Persistence pool sizes hardcoded, not configurable | infra-persistence | S | -- | `make test-unit`; assert settings override propagates to engine |
| CF-08 | Engine/session are module-level singletons; untestable | infra-persistence | L | -- | `make verify`; existing tests pass with injected manager |
| CF-09 | Redis client never closed on shutdown | infra-persistence | S | CF-02 | `make test-unit`; assert `close()` called in lifespan shutdown |
| CF-06 | OIDC client creates new httpx client per call | infra-auth | M | -- | `make test-unit`; assert single client reused across calls |
| CF-10 | No startup health check for database connectivity | infra-persistence | S | CF-02 | `make test-int`; startup fails fast when DB unreachable |
| CF-12 | TaskIQ has no BaseSettings; raw `os.getenv` | infra-taskiq | S | -- | `make verify`; `TaskIQSettings` validates fields |

### CF-02: Persistence lifespan hook -- RLS tenant isolation non-functional

**Finding:** `dispose_engine()` and `register_tenant_context_handler()` exist but are never called outside tests. In production, RLS tenant context is never set on connections, meaning row-level security policies either leak all data or block all data depending on policy design. On shutdown, up to 40 database connections and Redis connections are abandoned.

**Root Cause:** When `infra-persistence` was built, no `LifespanContribution` was created. The cleanup functions were written but the wiring to the application lifecycle was omitted. The entry-point auto-discovery pattern was adopted later (in `infra-eventsourcing` and `infra-observability`) but never back-ported to persistence.

**Fix:**
1. Create `packages/infra-persistence/src/praecepta/infra/persistence/lifespan.py`.
2. Implement a `LifespanContribution` with `priority=75` (before event store at 100).
3. On startup: call `register_tenant_context_handler()`, optionally run `SELECT 1` health check (CF-10).
4. On shutdown: call `dispose_engine()` for both async and sync engines, call `await get_redis_factory().close()`.
5. Register in `pyproject.toml` under `[project.entry-points."praecepta.lifespan"]`.
6. Update `__init__.py` exports.

**Verification:** `make verify` passes. Write an integration test that boots the app via `create_app()`, confirms `register_tenant_context_handler` was called (mock or spy), and confirms `dispose_engine` runs on shutdown.

**Risk if deferred:** Multi-tenant data isolation is broken. Connections leak on every restart, accumulating toward `max_connections`. This is the single highest-impact finding.

### CF-01: SQL identifier injection in RLS helpers

**Finding:** `rls_helpers.py` uses f-string interpolation for `table_name`, `policy_name`, and `cast_type` in DDL SQL statements. While these values are developer-supplied (not user input), an identifier containing SQL metacharacters produces injectable DDL.

**Root Cause:** The RLS helper functions were written as convenience wrappers around Alembic `op.execute()`. Standard parameterized queries do not work for DDL identifiers (table/policy names), so f-strings were used without quoting.

**Fix:**
1. Add a validation function: `_validate_identifier(name: str) -> str` that asserts `re.fullmatch(r"[a-z_][a-z0-9_]*", name)` and raises `ValueError` otherwise.
2. Apply `_validate_identifier()` to `table_name`, `policy_name`, and `cast_type` at the top of each helper function.
3. Alternatively, use `sqlalchemy.sql.quoted_name()` for all identifiers.

**Verification:** `make test-unit`. Add tests passing identifiers with semicolons, quotes, and spaces; assert `ValueError` raised.

**Risk if deferred:** Latent injection surface in security-critical DDL. While exploitation requires a malicious developer or compromised migration file, the RLS subsystem is the tenant isolation boundary -- any weakness here is severe.

### CF-03: TaskIQ broker lifecycle completely missing

**Finding:** No `LifespanContribution` registered. `broker.startup()` never called (consumer groups not initialized). `broker.shutdown()` never called (connections leaked, unacknowledged messages lost). Broker, result backend, and scheduler are module-level singletons constructed at import time.

**Root Cause:** `infra-taskiq` is the least mature infrastructure package. It was scaffolded as a thin wrapper around taskiq-redis but never underwent the convention alignment pass applied to other packages.

**Fix:**
1. Create `TaskIQSettings(BaseSettings)` with `env_prefix="TASKIQ_"` (CF-12, prerequisite).
2. Convert module-level singletons to factory functions with `@lru_cache` (CF-27, prerequisite).
3. Create `packages/infra-taskiq/src/praecepta/infra/taskiq/lifespan.py` with `LifespanContribution` at `priority=150`.
4. On startup: instantiate broker via factory, call `await broker.startup()`.
5. On shutdown: call `await broker.shutdown()`.
6. Register in `pyproject.toml` under `[project.entry-points."praecepta.lifespan"]`.

**Verification:** `make verify`. Integration test confirming broker `startup`/`shutdown` are called. Unit test confirming factory is not invoked at import time.

**Risk if deferred:** Any application using background tasks has non-functional consumer groups. Messages may be published but never consumed, or consumed but never acknowledged, leading to data loss.

### CF-04: Aggregate PostgreSQL connection budget exceeds defaults

**Finding:** Single process with 4 projections: async pool (30) + sync pool (10) + event store (15) + projection runners (4x15=60) = 115 connections vs PostgreSQL default `max_connections=100`. With multiple workers, multiplied further.

**Root Cause:** Three independent packages maintain their own connection pools with no aggregate awareness. Projection runners each create a full application instance with its own pool. Pool sizes are hardcoded in persistence (CF-07) and not tuned for sequential workloads in projection runners.

**Fix:**
1. Make persistence pool sizes configurable via `DatabaseSettings` (CF-07, prerequisite).
2. Reduce projection runner pool defaults to `pool_size=1, max_overflow=2` (sequential processing needs minimal concurrency).
3. Add configurable `max_projection_runners` setting in `EventSourcingSettings` (CF-14).
4. Add startup health check that queries `SHOW max_connections` and logs a warning if total budget exceeds 80% of available connections.

**Verification:** `make test-unit`. Assert that default settings for a 4-projection deployment produce fewer than 100 total connections. Health check test with mocked `max_connections`.

**Risk if deferred:** Connection exhaustion under default settings. Rolling deployments compound the issue when orphaned connections from CF-02 persist alongside new connections. Database becomes unavailable.

### CF-07: Persistence pool sizes hardcoded

**Finding:** `pool_size=20, max_overflow=10` (async) and `pool_size=5, max_overflow=5` (sync) are hardcoded. Not configurable via `DatabaseSettings` or environment. Production tuning requires code changes.

**Root Cause:** Pool configuration was set to reasonable defaults during initial development but never promoted to the settings surface.

**Fix:**
1. Add fields to `DatabaseSettings`: `async_pool_size: int = 10`, `async_max_overflow: int = 5`, `sync_pool_size: int = 3`, `sync_max_overflow: int = 2`, `pool_timeout: int = 30`, `pool_recycle: int = 3600`.
2. Wire these into `create_async_engine()` and `create_engine()` calls.
3. Reduce defaults from current values (20/10 async, 5/5 sync) to more conservative values.

**Verification:** `make test-unit`. Assert settings values propagate to engine creation arguments.

**Risk if deferred:** Operators cannot tune connection pools without code changes. Directly contributes to CF-04 connection exhaustion.

### CF-08: Engine/session module-level singletons

**Finding:** Engine and session factory are module-level global singletons. This makes testing difficult, prevents per-tenant connection routing, and couples all callers to a single database configuration.

**Root Cause:** The persistence module was originally designed as a simple utility. The module-level singleton pattern was expedient but does not scale to multi-tenant or test-isolated use cases.

**Fix:**
1. Encapsulate engine, session factories, and configuration in a `DatabaseManager` class.
2. Provide a module-level default instance via `@lru_cache` factory for backward compatibility.
3. Allow `DatabaseManager` to be injected via FastAPI dependency override for testing and per-tenant routing.
4. Update all consumers to accept an optional manager parameter.

**Verification:** `make verify`. All existing tests pass. New test demonstrating two `DatabaseManager` instances with different configs coexist.

**Risk if deferred:** Prevents per-tenant database routing. Makes integration testing fragile (shared mutable state). Blocks future multi-database support.

### CF-09: Redis client never closed

**Finding:** `RedisFactory.close()` exists but is never invoked from any lifespan hook. The `@lru_cache` singleton persists for process lifetime; underlying connection pool is never closed.

**Root Cause:** Same lifecycle gap as CF-02. Cleanup function implemented but not wired.

**Fix:** Include `await get_redis_factory().close()` in the persistence lifespan shutdown path created for CF-02.

**Verification:** `make test-unit`. Mock `RedisFactory.close()` and assert it is called during lifespan shutdown.

**Risk if deferred:** Redis connections leaked on every process restart. Under high churn (frequent deployments), Redis connection limit may be reached.

### CF-06: OIDC client creates new httpx client per call

**Finding:** `OIDCTokenClient` creates a new `httpx.AsyncClient` per method call. Each instantiation performs a fresh TLS handshake and TCP setup.

**Root Cause:** The client was written for simplicity without considering connection reuse. No shared client lifecycle management exists.

**Fix:**
1. Accept an optional `httpx.AsyncClient` in the `OIDCTokenClient` constructor.
2. If not provided, create one lazily and store as instance attribute.
3. Add `async def aclose()` method to close the owned client.
4. In the auth lifespan hook (CF-31, P2), register `aclose()` on shutdown.

**Verification:** `make test-unit`. Assert that two consecutive method calls reuse the same underlying client (check via mock).

**Risk if deferred:** Performance degradation under token refresh storms. TLS handshake overhead on every call. Under load, file descriptor exhaustion possible.

### CF-10: No startup health check for database

**Finding:** No startup validation that the database is reachable. Lazy singleton means connection failures surface at first-request time. Pod passes Kubernetes readiness checks then fails on first request.

**Root Cause:** No persistence lifespan hook exists (CF-02). Without startup logic, there is no place to run health checks.

**Fix:** In the persistence lifespan hook (CF-02), execute `SELECT 1` on both async and sync engines during startup. Raise on failure to prevent the application from accepting traffic.

**Verification:** `make test-int`. Test with unreachable database URL; assert application fails to start.

**Risk if deferred:** Kubernetes routes traffic to pods that cannot serve requests. First-request failures instead of fast startup failures.

### CF-12: TaskIQ has no BaseSettings

**Finding:** Uses raw `os.getenv("REDIS_URL")`. The only infra package without `pydantic_settings.BaseSettings`. Breaks monorepo convention.

**Root Cause:** `infra-taskiq` was scaffolded minimally and never went through the settings standardization pass.

**Fix:**
1. Create `packages/infra-taskiq/src/praecepta/infra/taskiq/settings.py`.
2. Define `TaskIQSettings(BaseSettings)` with `model_config = SettingsConfigDict(env_prefix="TASKIQ_")`.
3. Fields: `redis_url: str = "redis://localhost:6379/1"` (note: database 1, not 0, to avoid CF-13 collision), `result_ttl: int = 3600`, `stream_prefix: str = "taskiq"`.
4. Update `broker.py` to read from settings instead of raw `os.getenv`.

**Verification:** `make verify`. Assert settings are used. Assert `TASKIQ_REDIS_URL` env var is respected.

**Risk if deferred:** Cannot configure taskiq via standard `.env` mechanism. No type validation on configuration values. Redis URL collision with persistence (CF-13).

---

## P2 -- Fix Before Beta

| ID | Finding | Package | Effort | Depends On | Verification |
|----|---------|---------|--------|------------|--------------|
| CF-05 | CORS wildcard + credentials silent downgrade | infra-fastapi | S | -- | `make test-unit` |
| CF-13 | Redis URL collision between taskiq and persistence | infra-taskiq, infra-persistence | S | CF-12 | `make test-unit` |
| CF-14 | No limit on projection runner count | infra-eventsourcing | S | -- | `make test-unit` |
| CF-15 | `DEBUG` read from `os.environ` instead of app settings | infra-fastapi | S | -- | `make test-unit` |
| CF-17 | Middleware uses deprecated `BaseHTTPMiddleware` | infra-fastapi | L | -- | `make verify` |
| CF-18 | Middleware priority bands not enforced | infra-fastapi | S | -- | `make test-unit` |
| CF-19 | OIDC discovery document not fetched/validated | infra-auth | M | -- | `make test-unit` |
| CF-20 | `AuthSettings.issuer` has no format validation | infra-auth | S | -- | `make test-unit` |
| CF-11 | No trace sampler configuration (100% sampling) | infra-observability | S | -- | `make test-unit` |
| CF-21 | No Alembic async migration wiring | infra-persistence | M | -- | Documentation review |
| CF-22 | Redis pool lifecycle hidden inside `aioredis` | infra-persistence | M | CF-09 | `make test-unit` |
| CF-23 | `DatabaseSettings` does not validate connection string | infra-persistence | S | -- | `make test-unit` |
| CF-24 | Incomplete `__init__.py` exports | infra-persistence | S | -- | `make verify` |
| CF-25 | Request ID integration is implicit coupling | infra-observability | S | -- | Code review |
| CF-26 | Middleware priority comment contradicts ordering | infra-observability | S | -- | Code review |
| CF-27 | TaskIQ module-level singletons at import time | infra-taskiq | M | CF-12 | `make test-unit` |
| CF-28 | No error handling patterns in taskiq | infra-taskiq | M | CF-03 | `make test-unit` |

### P2 Fix Descriptions

- **CF-05:** Add `@model_validator(mode="after")` on `CORSSettings` that raises `ValueError` if `allow_credentials=True` and `allow_origins == ["*"]`.
- **CF-13:** After CF-12 creates `TaskIQSettings`, default `TASKIQ_REDIS_URL` to `redis://localhost:6379/1` (database 1). Document Redis database separation strategy.
- **CF-14:** Add `max_projection_runners: int = 8` to `EventSourcingSettings`. Enforce in `ProjectionPoller` or the subscription runner factory.
- **CF-15:** Replace `os.environ.get("DEBUG")` with `request.app.debug` in `error_handlers.py`.
- **CF-17:** Rewrite `RequestIdMiddleware`, `RequestContextMiddleware`, and `TenantStateMiddleware` as pure ASGI middleware using `async def __call__(self, scope, receive, send)`. This also resolves CF-33.
- **CF-18:** Add range validation on `MiddlewareContribution.priority` (e.g., 0-299) or define band constants with `field_validator`.
- **CF-19:** Fetch `/.well-known/openid-configuration`, extract `jwks_uri`, validate issuer match, enforce HTTPS.
- **CF-20:** Add `@field_validator("issuer")` enforcing HTTPS URL format when `dev_bypass` is False.
- **CF-11:** Add `sample_rate: float = 1.0` to `TracingSettings`. Pass `TraceIdRatioBasedSampler(sample_rate)` to `TracerProvider`.
- **CF-21:** Provide a reusable async `env.py` template for Alembic, or document that consumers must create their own.
- **CF-22:** Explicitly create `ConnectionPool` and pass to `Redis(connection_pool=pool)` for lifecycle control.
- **CF-23:** Add `@model_validator(mode="after")` calling `make_url()` on the connection string to fail fast on invalid URLs.
- **CF-24:** Add `RedisFactory`, `get_redis_factory`, `get_sync_session_factory`, `get_sync_engine` to `__all__`.
- **CF-25:** Document the implicit coupling between observability and fastapi request ID. Add defensive check for `request_id` presence.
- **CF-26:** Change `TraceContextMiddleware` priority to 5 (outermost) or update the comment to accurately describe its position.
- **CF-27:** Convert broker, result backend, and scheduler from module-level singletons to `@lru_cache` factory functions. Prerequisite for CF-03.
- **CF-28:** Add `RetryMiddleware` configuration. Define `TaskIQError` base exception. Add dead-letter queue configuration.

---

## P3 -- Improvement Backlog

| ID | Finding | Package | Effort | Depends On | Verification |
|----|---------|---------|--------|------------|--------------|
| CF-16 | Health check returns trivial `{"status": "ok"}` | infra-fastapi | M | CF-02, CF-10 | `make test-int` |
| CF-29 | Resource defaults tuned for neither dev nor production | cross-cutting | M | CF-07 | Documentation review |
| CF-30 | Implicit persistence/event-store ordering not enforced | cross-cutting | S | CF-02 | Code review |
| CF-31 | No lifespan hook for JWKS/OIDC initialization | infra-auth | M | CF-06 | `make test-unit` |
| CF-32 | No transient vs. permanent error classification | cross-cutting | L | -- | `make verify` |
| CF-33 | `BaseHTTPMiddleware` does not handle WebSocket | infra-fastapi | -- | CF-17 | Resolved by CF-17 |
| CF-34 | `AppSettings.version` does not match package version | infra-fastapi | S | -- | `make test-unit` |
| CF-35 | `compose_lifespan` has no logging on hook failure | infra-fastapi | S | -- | `make test-unit` |
| CF-36 | `dev_bypass.py` reads `ENVIRONMENT` via raw `os.environ` | infra-auth | S | -- | `make test-unit` |
| CF-37 | `echo=False` hardcoded, no SQL logging in dev | infra-persistence | S | CF-07 | `make test-unit` |
| CF-38 | `@lru_cache` on `get_redis_factory()` not async-safe | infra-persistence | S | -- | Acceptable as-is |
| CF-39 | No test coverage for `redis_client.py` | infra-persistence | M | -- | `make test-unit` |
| CF-40 | No explicit W3C TraceContext propagator | infra-observability | S | -- | `make test-unit` |
| CF-41 | No runtime thread budget logging | cross-cutting | S | -- | Manual verification |
| CF-42 | Lifespan priority constants are scattered magic numbers | cross-cutting | S | -- | `make verify` |

---

## Dependency Graph

```
CF-07 (configurable pool sizes)
  |
  +---> CF-04 (aggregate connection budget)
  |       |
  |       +---> CF-14 (projection runner limits)
  |
  +---> CF-02 (persistence lifespan hook)
          |
          +---> CF-09 (Redis close on shutdown)
          +---> CF-10 (startup health check)
          +---> CF-30 (ordering enforcement)
          +---> CF-16 (aggregated health checks)

CF-08 (DatabaseManager class)
  |
  +---> CF-02 (persistence lifespan can manage the class cleanly)

CF-12 (TaskIQ BaseSettings)
  |
  +---> CF-13 (Redis URL separation uses TASKIQ_ prefix)
  +---> CF-27 (factory functions read from settings)
          |
          +---> CF-03 (TaskIQ lifespan hook)
                  |
                  +---> CF-28 (error handling/retry on top of lifecycle)

CF-06 (shared httpx client)
  |
  +---> CF-31 (auth lifespan hook manages client lifecycle)

CF-17 (pure ASGI middleware)
  |
  +---> CF-33 (WebSocket support -- resolved by CF-17)
```

## Recommended Execution Order

The following sequence respects dependency ordering and groups related work to minimize context switching.

### Phase 1: Foundation fixes (settings and singletons)

1. **CF-07** -- Make persistence pool sizes configurable via `DatabaseSettings`. Small, isolated, and unblocks multiple downstream fixes.
2. **CF-12** -- Create `TaskIQSettings(BaseSettings)`. Small, isolated, unblocks taskiq lifecycle work.
3. **CF-01** -- Validate SQL identifiers in RLS helpers. Small, isolated, highest security value.

### Phase 2: Persistence lifecycle (the highest-impact cluster)

4. **CF-08** -- Refactor engine/session into `DatabaseManager` class. Large but foundational for clean lifecycle management.
5. **CF-02** -- Create persistence `LifespanContribution`. Wire startup (health check, RLS context handler) and shutdown (dispose engines, close Redis).
6. **CF-09** -- Redis close on shutdown (included in CF-02 lifespan, but verify independently).
7. **CF-10** -- Database startup health check (included in CF-02 lifespan, but verify independently).

### Phase 3: TaskIQ lifecycle

8. **CF-27** -- Convert taskiq module-level singletons to factory functions.
9. **CF-13** -- Separate Redis URLs (uses `TASKIQ_` prefix from CF-12).
10. **CF-03** -- Create taskiq `LifespanContribution` with broker `startup()`/`shutdown()`.

### Phase 4: Connection budget and resource governance

11. **CF-14** -- Add `max_projection_runners` setting and reduce per-runner pool defaults.
12. **CF-04** -- Add aggregate connection budget health check at startup.

### Phase 5: Auth and observability hardening

13. **CF-06** -- Shared httpx client in OIDC token client.
14. **CF-11** -- Trace sampler configuration.
15. **CF-15** -- Fix `DEBUG` env var bypass in error handlers.
16. **CF-05** -- CORS wildcard + credentials validator.
17. **CF-20** -- Auth issuer URL format validation.

### Phase 6: Convention alignment and middleware

18. **CF-23** -- Database connection string validation.
19. **CF-24** -- Fix `__init__.py` exports.
20. **CF-25, CF-26** -- Observability middleware documentation and priority fix.
21. **CF-18** -- Middleware priority band enforcement.
22. **CF-17** -- Migrate to pure ASGI middleware (large effort, low urgency since current middleware works).

### Phase 7: Remaining P2 items

23. **CF-19** -- OIDC discovery document validation.
24. **CF-21** -- Alembic async migration template.
25. **CF-22** -- Explicit Redis connection pool management.
26. **CF-28** -- TaskIQ error handling patterns.

### Phase 8: P3 improvements (as capacity allows)

27. **CF-29** -- Document dev vs. production deployment profiles.
28. **CF-16** -- Aggregated health check endpoint.
29. **CF-31** -- Auth lifespan hook for JWKS pre-warming.
30. **CF-30, CF-42** -- Priority constant consolidation and ordering enforcement.
31. **CF-32** -- Error taxonomy (transient vs. permanent).
32. **CF-34, CF-35, CF-36, CF-37** -- Small hygiene fixes.
33. **CF-39** -- Redis client test coverage.
34. **CF-40, CF-41** -- Observability minor improvements.
35. **CF-38** -- `lru_cache` async safety (acceptable as-is; fix only if issues observed).
36. **CF-33** -- Resolved by CF-17.
