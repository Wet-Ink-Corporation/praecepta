# Consolidated Audit Findings

## Executive Summary

This audit examined five Praecepta infrastructure packages (`infra-fastapi`, `infra-auth`, `infra-persistence`, `infra-observability`, `infra-taskiq`) across three dimensions: per-package library usage correctness (Pass 1), cross-cutting resource budgets, lifecycle coherence, and convention compliance (Pass 2). All five packages received an AMBER RAG status -- none are RED (immediate production blocker) but none are GREEN (fully production-ready) either.

The audit identified 40 unique findings after deduplication: 4 CRITICAL, 10 HIGH, 16 MEDIUM, and 10 LOW. The most severe issues cluster in two areas. First, **lifecycle management gaps**: `infra-persistence` has no lifespan hook, meaning database connection pools (40 connections/process) are never disposed on shutdown, Redis clients are never closed, and critically, the RLS tenant context handler is never registered in production -- rendering row-level security non-functional. Second, **`infra-taskiq` is fundamentally incomplete**: it lacks `BaseSettings`, has no lifespan registration, creates broker resources at import time, and never calls `startup()` or `shutdown()`, risking connection leaks and unacknowledged message loss.

A cross-cutting resource budget analysis revealed that a single process running 4 projections consumes up to 115 PostgreSQL connections under default settings, exceeding PostgreSQL's default `max_connections=100`. With multiple Uvicorn workers, this multiplies further. The root cause is that three independent packages maintain their own connection pools with no aggregate awareness or budget validation. The remaining findings cover configuration rigidity (hardcoded pool sizes in `infra-persistence`), security hardening gaps (SQL identifier injection in RLS helpers, missing CORS misconfiguration validator), and convention deviations (direct `os.environ` reads bypassing the settings abstraction).

## Summary by Package

| Package | RAG | Critical | High | Medium | Low | Total |
|---------|-----|----------|------|--------|-----|-------|
| infra-fastapi | AMBER | 0 | 1 | 4 | 3 | 8 |
| infra-auth | AMBER | 0 | 2 | 2 | 1 | 5 |
| infra-persistence | AMBER | 1 | 4 | 4 | 4 | 13 |
| infra-observability | AMBER | 0 | 1 | 2 | 1 | 4 |
| infra-taskiq | AMBER | 2 | 3 | 3 | 0 | 8 |
| Cross-cutting | -- | 1 | 1 | 4 | 2 | 8 |
| **Total** | -- | **4** | **12** | **19** | **11** | **46** |

Note: Some findings span multiple packages. The cross-cutting row counts findings that are inherently multi-package and not attributable to a single package. The per-package counts reflect the primary package affected. Some findings are counted in both a package row and a cross-cutting context; the total is deduplicated to 40 unique findings.

## All Findings (sorted by severity, then package)

| ID | Package | Severity | Checklist | Description | File:Line | Recommendation |
|----|---------|----------|-----------|-------------|-----------|----------------|
| CF-01 | infra-persistence | CRITICAL | PE-7 | RLS helper functions use f-string interpolation for `table_name`, `policy_name`, and `cast_type` in DDL SQL. No identifier validation or quoting. A table name containing SQL metacharacters produces injectable DDL. | `packages/infra-persistence/src/praecepta/infra/persistence/rls_helpers.py:18,29,51-55,69` | Use `sqlalchemy.sql.quoted_name()` or validate identifiers match `^[a-z_][a-z0-9_]*$` before interpolation. |
| CF-02 | infra-persistence | CRITICAL | XC-L1-01, XC-L1-03 | Database engines have no lifespan hook. `dispose_engine()` is defined but never called. On shutdown, up to 40 connections/process are abandoned. More critically, `register_tenant_context_handler()` is never called outside tests, meaning RLS tenant isolation is non-functional in production. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:84-89` | Create a `LifespanContribution` (priority 75) that calls `register_tenant_context_handler()` on startup and `dispose_engine()` + `RedisFactory.close()` on shutdown. Register via `[project.entry-points."praecepta.lifespan"]`. |
| CF-03 | infra-taskiq | CRITICAL | TQ-7, XC-L1-02 | No `LifespanContribution` registered for broker lifecycle. `pyproject.toml` has no `[project.entry-points."praecepta.lifespan"]`. Broker `startup()` is never called (consumer groups not initialized) and `shutdown()` is never called (connections leaked, unacked messages lost). Resources are created at import time as module-level singletons. | `packages/infra-taskiq/pyproject.toml` (absent entry), `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:61-81` | Convert to factory functions. Create a `LifespanContribution` (priority 150) that calls `broker.startup()` on entry and `broker.shutdown()` on exit. Register via entry points. |
| CF-04 | cross-cutting | CRITICAL | XC-R1 | Total PostgreSQL connection count exceeds defaults. Single process with 4 projections: async pool (30) + sync pool (10) + event store (15) + projection runners (4x15=60) = 115 connections vs PostgreSQL default `max_connections=100`. With multiple workers, multiplied further. No aggregate budget check exists. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:115-116,184-185` | (1) Reduce projection runner pool defaults to `pool_size=1, max_overflow=2`. (2) Make persistence pool sizes configurable. (3) Add startup health check comparing budget to `SHOW max_connections`. |
| CF-05 | infra-fastapi | HIGH | FA-5 | CORS defaults allow all origins (`["*"]`). If downstream sets `allow_credentials=True` with wildcard origins, Starlette silently downgrades to no CORS (per spec). No validator prevents this misconfiguration. | `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:24-28` | Add `model_validator(mode="after")` on `CORSSettings` that raises if `allow_credentials=True` and `allow_origins == ["*"]`. |
| CF-06 | infra-auth | HIGH | AU-4, AU-14 | `OIDCTokenClient` creates a new `httpx.AsyncClient` per method call. Each instantiation performs a fresh TLS handshake and TCP setup. No connection pooling. Under token refresh storms this becomes N+1 resource multiplication. | `packages/infra-auth/src/praecepta/infra/auth/oidc_client.py:149,185` | Inject a shared `httpx.AsyncClient` via constructor (lifespan-scoped singleton). Register `aclose()` in a lifespan shutdown hook. |
| CF-07 | infra-persistence | HIGH | PE-8, PE-14 | Pool sizes are hardcoded (`pool_size=20, max_overflow=10` async; `pool_size=5, max_overflow=5` sync). Not configurable via `DatabaseSettings` or environment. Production tuning requires code changes. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:115-116,184-185` | Add `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle` fields to `DatabaseSettings`. |
| CF-08 | infra-persistence | HIGH | PE-4 | Engine and session factory are module-level global singletons. Makes testing difficult, prevents per-tenant connection routing, couples all callers to a single database. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:84-89` | Encapsulate in a `DatabaseManager` class that can be instantiated per configuration and injected via FastAPI dependency override. |
| CF-09 | infra-persistence | HIGH | XC-L1-04 | Redis client (`RedisFactory`) has no shutdown path. `close()` exists but is never invoked from any lifespan hook. The `@lru_cache` singleton persists for process lifetime; underlying connection pool is never closed. | `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:152-167` | Include `await get_redis_factory().close()` in the persistence lifespan shutdown path. |
| CF-10 | infra-persistence | HIGH | XC-L1-05 | Database must be reachable before event store (priority 100), but persistence has no startup hook. Lazy singleton means connection failures surface at first-request time, not startup. Pod passes readiness checks then fails on first request. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py` | Add startup health check in persistence lifespan that validates connectivity (`SELECT 1`). Fail fast at startup. |
| CF-11 | infra-observability | HIGH | OB-8 | No sampler configuration. `TracerProvider` constructed without `sampler`, defaulting to `ALWAYS_ON` (100% sampling). In production with OTLP export, every request generates a trace -- significant overhead and cost. | `packages/infra-observability/src/praecepta/infra/observability/tracing.py:276` | Add `sample_rate: float` to `TracingSettings` and pass `TraceIdRatioBasedSampler(sample_rate)` to `TracerProvider`. |
| CF-12 | infra-taskiq | HIGH | TQ-6, XC-C1 | No `BaseSettings` class. Uses raw `os.getenv("REDIS_URL")`. The only infra package without `pydantic_settings.BaseSettings`. Breaks monorepo convention, prevents type validation, `.env` file support, and prefixed env vars. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:48-57` | Create `TaskIQSettings(BaseSettings)` with `env_prefix="TASKIQ_"`. Fields: `redis_url`, `result_ttl`, `stream_prefix`. |
| CF-13 | infra-taskiq | HIGH | XC-C3, XC-R2 | Redis URL collision. Both taskiq and persistence read `REDIS_URL` defaulting to `redis://localhost:6379/0`. Task queue and persistence traffic compete on same Redis database with no separation. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:57` vs `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:78` | Use `TASKIQ_REDIS_URL` with fallback to `REDIS_URL`. Use separate Redis database numbers. Document separation strategy. |
| CF-14 | cross-cutting | HIGH | XC-R4 | No mechanism to limit total projection runners. Each projection spawns a new `EventSourcedProjectionRunner` with its own pool (up to 15 connections). Downstream registering many projections causes unbounded pool multiplication. | N/A (architectural) | Add configurable `max_projection_runners` setting. Reduce default pool to `pool_size=1, max_overflow=1` for sequential processing. |
| CF-15 | infra-fastapi | MEDIUM | FA-7, FA-11 | `unhandled_exception_handler` reads debug mode from `os.environ.get("DEBUG")` instead of `request.app.debug` (set from `AppSettings.debug` with `APP_` prefix). A stray `DEBUG=true` in production could leak exception details. | `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:513` | Use `request.app.debug` instead of raw `os.environ`. |
| CF-16 | infra-fastapi | MEDIUM | FA-15 | Health check returns trivial `{"status": "ok"}` with no actual probing. No database, event store, or Redis readiness checks. Kubernetes readiness probes are meaningless. | `packages/infra-fastapi/src/praecepta/infra/fastapi/_health.py:14-17` | Implement `/readyz` that aggregates health from registered providers via `praecepta.health_checks` entry points. |
| CF-17 | infra-fastapi | MEDIUM | FA-16, FA-18 | All three middleware use `BaseHTTPMiddleware`, which is deprecated in spirit by Starlette maintainers. Creates new anyio task per request, breaks `contextvars` in edge cases, poor streaming/WebSocket support. | `packages/infra-fastapi/src/praecepta/infra/fastapi/request_id.py:69`, `request_context.py:34`, `tenant_state.py:44` | Migrate to pure ASGI middleware (`async def __call__(self, scope, receive, send)`). |
| CF-18 | infra-fastapi | MEDIUM | FA-17 | Middleware priority bands (0-99 outermost, 200-299 context) implied by comments but not enforced programmatically. No validation rejects out-of-band priorities. | `packages/infra-fastapi/src/praecepta/infra/fastapi/request_id.py:156`, `request_context.py:91`, `tenant_state.py:143` | Add `field_validator` or range constants on `MiddlewareContribution.priority`. |
| CF-19 | infra-auth | MEDIUM | AU-10 | OIDC discovery document not fetched or validated. JWKS URI constructed by convention (appending `/.well-known/jwks.json`) rather than via `/.well-known/openid-configuration`. Issuer not cross-validated. HTTPS not enforced. | `packages/infra-auth/src/praecepta/infra/auth/jwks.py:67` | Fetch discovery document, validate issuer, extract `jwks_uri`, verify HTTPS. |
| CF-20 | infra-auth | MEDIUM | AU-16 | `AuthSettings.issuer` has no format validation. No HTTPS enforcement, no URL structure check, defaults to empty string. | `packages/infra-auth/src/praecepta/infra/auth/settings.py:55-58` | Add `@field_validator` enforcing HTTPS when `dev_bypass` is False. |
| CF-21 | infra-persistence | MEDIUM | PE-5 | No Alembic `env.py` or migration configuration despite Alembic being a declared dependency. `rls_helpers.py` uses `alembic.op` but no async migration wiring is provided. | N/A (missing file) | Provide reusable async `env.py` template or document that consumers must provide their own. |
| CF-22 | infra-persistence | MEDIUM | PE-6 | `RedisFactory._create_client()` uses `aioredis.from_url()` with implicit pool. Pool lifecycle hidden inside redis-py internals. Health checks and retry not configurable. | `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:130-138` | Explicitly create `ConnectionPool` and pass to `Redis(connection_pool=pool)` for full control. |
| CF-23 | infra-persistence | MEDIUM | PE-13 | `DatabaseSettings` does not validate connection string format. No `make_url()` check or `@model_validator`. Invalid configs propagate silently. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:42-80` | Add `@model_validator(mode='after')` calling `make_url()` to fail fast. |
| CF-24 | infra-persistence | MEDIUM | XC-C3 | Incomplete `__init__.py` exports. `RedisFactory`, `get_redis_factory`, `get_sync_session_factory`, `get_sync_engine` not in `__all__`. Public API surface ambiguous. | `packages/infra-persistence/src/praecepta/infra/persistence/__init__.py` | Add missing symbols to `__all__` or document that deep imports are intentional. |
| CF-25 | infra-observability | MEDIUM | OB-10 | Request ID integration is implicit. Observability package documents correlation with `RequestIdMiddleware` but relies on convention-gap dependency. `request_id` appears in logs only because `infra-fastapi` independently binds it. | `packages/infra-observability/src/praecepta/infra/observability/middleware.py:37-38,79-82` | Document implicit coupling. Add `request_id` to `unbind_contextvars` call or verify its presence. |
| CF-26 | infra-observability | MEDIUM | OB-11 | Middleware priority semantics confusing. `TraceContextMiddleware` (priority 20) has comment "Outermost band (0-99)" but runs inner to `RequestIdMiddleware` (priority 10). Comment does not match numeric ordering. | `packages/infra-observability/src/praecepta/infra/observability/middleware.py:93-96` | Set priority to 5 if trace context should be outermost, or update comment to clarify inner-to-RequestIdMiddleware ordering. |
| CF-27 | infra-taskiq | MEDIUM | TQ-8 | Broker, result backend, and scheduler are module-level singletons instantiated at import time. Importing triggers Redis URL resolution and object construction immediately. Can fail if environment not configured. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:61-81` | Convert to factory functions or lazy initialization via `functools.lru_cache`. |
| CF-28 | infra-taskiq | MEDIUM | TQ-9 | No error handling patterns. No custom exceptions, no retry configuration, no dead-letter queue setup. | `packages/infra-taskiq/src/praecepta/infra/taskiq/` (absent) | Add `RetryMiddleware` configuration. Define `TaskIQError` hierarchy. |
| CF-29 | cross-cutting | MEDIUM | XC-R5 | Resource defaults tuned for neither dev nor production. Async pool (20) oversized for dev; projection pools (5+10) oversized for sequential processing. No documented deployment profiles. | Multiple files | Make all pool sizes configurable. Document recommended settings for dev vs production. Provide example `.env` files. |
| CF-30 | cross-cutting | MEDIUM | XC-L1-06 | Implicit ordering dependency between persistence and event store not enforced. Event store (priority 100) depends on PostgreSQL, but no persistence lifespan ensures DB layer is ready. Constraint documented only in comments. | N/A (architectural) | Assign persistence lifespan priority 75. Add comment documenting ordering constraint. |
| CF-31 | cross-cutting | MEDIUM | XC-L1-08 | No lifespan hook for JWKS provider or OIDC client initialization. JWKS cache populated lazily on first JWT validation, causing cold-start latency. No fail-fast on OIDC misconfiguration. | N/A (absent hook) | Create auth lifespan hook (priority 80) that pre-warms JWKS cache and validates IdP reachability. |
| CF-32 | cross-cutting | MEDIUM | XC-E3 | No transient vs. permanent error classification across any infra package. Prevents intelligent retry logic at application layer. `infra-taskiq` has no error handling at all. | N/A (absent taxonomy) | Define `TransientError`/`PermanentError` taxonomy in foundation packages. Have infra packages wrap exceptions accordingly. |
| CF-33 | infra-fastapi | LOW | FA-18 | `BaseHTTPMiddleware` does not handle WebSocket connections. None of the middleware check `scope["type"]`. WebSocket routes would fail silently or raise. | `packages/infra-fastapi/src/praecepta/infra/fastapi/request_id.py:69`, `request_context.py:34`, `tenant_state.py:44` | Migrate to pure ASGI middleware (see CF-17) or add WebSocket scope checks. |
| CF-34 | infra-fastapi | LOW | FA-12 | `AppSettings.version` defaults to `"0.1.0"`, distinct from actual package version (`0.3.0`). No auto-population from package metadata. | `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:58` | Default to `importlib.metadata.version("praecepta-infra-fastapi")`. |
| CF-35 | infra-fastapi | LOW | FA-14 | `compose_lifespan` has no logging when a hook fails during startup. Exception propagates raw with no operational context about which hook failed. | `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py:38-49` | Wrap `stack.enter_async_context(ctx)` in try/except that logs which hook failed before re-raising. |
| CF-36 | infra-auth | LOW | XC-C6 | `dev_bypass.py` reads `ENVIRONMENT` directly via `os.environ.get()` instead of from `AuthSettings`. Creates second path for environment detection. | `packages/infra-auth/src/praecepta/infra/auth/dev_bypass.py:42` | Centralize environment detection in `AuthSettings` class method. |
| CF-37 | infra-persistence | LOW | PE-15 | `echo=False` hardcoded in both engines. No way to enable SQL logging in development without editing source. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:119,188` | Add `echo: bool` field to `DatabaseSettings`. |
| CF-38 | infra-persistence | LOW | PE-16 | `get_redis_factory()` uses `@lru_cache` which is not async-safe. Concurrent first calls could race on factory creation. Benign but impure. | `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:152-167` | Acceptable. Replace with `asyncio.Lock`-guarded singleton if needed. |
| CF-39 | infra-persistence | LOW | N/A | No test coverage for `redis_client.py`. `RedisFactory`, `get_redis_factory()`, and `close()` are untested. | N/A (missing test file) | Add `test_redis_client.py` with unit tests. |
| CF-40 | infra-observability | LOW | OB-4 | No explicit W3C TraceContext propagator configuration. Relies on SDK defaults, which could change in future releases. | `packages/infra-observability/src/praecepta/infra/observability/tracing.py:290-294` | Explicitly set `set_global_textmap(TraceContextTextMapPropagator())`. |
| CF-41 | cross-cutting | LOW | XC-R3 | Background thread count partially documented. No runtime logging of total thread count at startup. No centralized thread budget documentation. | N/A | Add startup log summarizing thread count. Expose via health endpoint. |
| CF-42 | cross-cutting | LOW | XC-L1-11 | Lifespan priority constants are magic numbers scattered across packages (50, 100, 200). No shared constants module. | N/A | Define priority band constants in `praecepta.foundation.application`. |

## Cross-Cutting Themes

### Resource Budget

The aggregate PostgreSQL connection consumption is the most significant cross-cutting concern. Three independent packages -- `infra-persistence` (async + sync engines), `infra-eventsourcing` (event store), and `infra-eventsourcing` (projection runners) -- each maintain their own connection pools with no awareness of one another. Under default settings, a single process running 4 projections consumes up to 115 connections, exceeding PostgreSQL's default `max_connections=100`. With 2 Uvicorn workers this rises to 230 connections.

The primary multiplier is the projection subscription runner: each projection spawns a full application instance with its own pool (`pool_size=5, max_overflow=10`). Since projections process events sequentially, a pool size of 1 with minimal overflow would suffice, immediately reducing the 4-projection budget from 115 to approximately 67 connections.

Configuration asymmetry compounds the problem. The eventsourcing package exposes pool configuration via `EventSourcingSettings` (`POSTGRES_POOL_SIZE`, `POSTGRES_MAX_OVERFLOW`), but the persistence package hardcodes its pool sizes with no settings surface. An operator can tune the event store pool but not the larger read-model pool.

Redis resources have a collision issue: both `infra-persistence` and `infra-taskiq` default to the same `REDIS_URL` (`redis://localhost:6379/0`) with no namespace separation, mixing cache keys with task queue keys.

### Lifecycle Coherence

Of six infrastructure packages, only two (`infra-observability` and `infra-eventsourcing`) participate in the lifespan protocol. Three packages (`infra-persistence`, `infra-auth`, `infra-taskiq`) manage resources requiring explicit initialization and/or cleanup but have no lifespan hooks.

The persistence gap is the most impactful. `dispose_engine()` exists but is orphaned -- no code path calls it. On each shutdown, 40 database connections and Redis connections are abandoned. More critically, `register_tenant_context_handler()` is only called in test fixtures, meaning RLS tenant isolation is non-functional in deployed applications.

The taskiq gap is the most severe from a correctness standpoint. Broker resources are created at import time, `startup()` is never called (consumer groups not initialized), and `shutdown()` is never called (connections leaked, unacknowledged messages lost).

The lifespan composition mechanism itself (in `infra-fastapi`) is well-designed: `compose_lifespan()` sorts by priority, uses `AsyncExitStack` for LIFO teardown, and correctly handles partial startup failures. The gap is simply that too few packages participate.

A recommended priority band allocation after remediation: observability (50), persistence (75), auth (80), event store (100), taskiq (150), projections (200). Shutdown reverses this order.

### Convention Compliance

The infrastructure packages exhibit two tiers of maturity. **Tier 1** (`infra-fastapi`, `infra-auth`, `infra-observability`, `infra-eventsourcing`) consistently follows established patterns: `BaseSettings` with `env_prefix`, `__all__` exports, entry-point registrations, PEP 420 compliance. Minor deviations (empty prefix in observability for OTel convention alignment, `os.environ` bridge in eventsourcing for upstream compatibility) are intentional and documented.

**Tier 2** (`infra-taskiq`) is a clear outlier. It lacks `BaseSettings`, has no entry-point registrations, no `LifespanContribution`, uses raw `os.getenv()`, and its module-level singletons are constructed at import time. It has not undergone the convention alignment pass applied to its siblings.

Direct `os.environ` usage falls into three categories: (1) a bug in `infra-fastapi` where `error_handlers.py` reads `DEBUG` instead of `APP_DEBUG`, (2) intentional bridges in `infra-eventsourcing` for upstream library compatibility, and (3) missing abstractions in `infra-taskiq` where no settings class exists.

PEP 420 implicit namespace compliance is perfect across all six packages. Deprecation handling in `infra-eventsourcing` is exemplary. The async/sync model split is consistently correct with no blocking calls in async contexts.

## Patterns Observed

Four anti-patterns identified during the projection remediation recur across the broader infrastructure layer:

1. **N+1 Resource Multiplication.** Each projection runner creates a full application instance with its own connection pool (CF-04, CF-14). The `OIDCTokenClient` creates a new `httpx.AsyncClient` per method call (CF-06). The underlying pattern is the same: resources that should be shared or bounded are instead multiplied per-operation or per-consumer.

2. **Convention-Gap Dependencies.** The observability package's `request_id` correlation depends on `infra-fastapi`'s `RequestIdMiddleware` independently binding the ID to `structlog.contextvars` (CF-25). This implicit coupling works but is fragile and undocumented. The middleware priority comment ("Outermost band") contradicts the actual numeric ordering (CF-26). These are the same class of "wiring by convention rather than contract" that caused issues in the original projection architecture.

3. **Orphaned Cleanup Functions.** `dispose_engine()` and `RedisFactory.close()` exist as cleanup functions that are never called from any lifecycle hook (CF-02, CF-09). This is the code-level manifestation of the lifecycle coherence gap -- the cleanup logic is implemented but the wiring to invoke it is missing.

4. **Configuration Bypass.** Direct `os.environ` reads in `error_handlers.py` (CF-15) and `broker.py` (CF-12) bypass the `BaseSettings` abstraction that every other package uses. This creates inconsistency in how configuration is validated, documented, and overridden, and in the `DEBUG` case, introduces a latent security risk.

## Risk Assessment

**Overall Risk Level: MEDIUM-HIGH.** The framework is architecturally sound but has significant gaps in lifecycle management and resource governance that must be addressed before production use.

**Most Critical Areas (must fix before any production deployment):**

1. **RLS tenant isolation is non-functional** (CF-02). `register_tenant_context_handler()` is never called outside tests. Depending on RLS policy design, this results in either data leakage (all rows visible) or data loss (no rows visible). This is the highest-impact finding in the entire audit.

2. **PostgreSQL connection exhaustion** (CF-04). Default settings exceed `max_connections=100` with just 4 projections. Rolling deployments compound the problem when orphaned connections (CF-02) persist alongside new connections.

3. **SQL identifier injection in RLS helpers** (CF-01). While developer-supplied, unquoted identifiers in DDL create a latent injection surface in the security boundary.

4. **TaskIQ broker never started or stopped** (CF-03). Any application relying on background task processing will have non-functional consumer groups and potential message loss.

**Should fix before next release (v0.4.0):**

- Make persistence pool sizes configurable (CF-07)
- Add persistence and taskiq lifespan hooks (CF-02, CF-03)
- Bring `infra-taskiq` to Tier 1 convention compliance (CF-12, CF-13, CF-27, CF-28)
- Fix `DEBUG` env var bypass (CF-15)
- Add trace sampler configuration (CF-11)
- Migrate middleware from `BaseHTTPMiddleware` to pure ASGI (CF-17)

**Acceptable to defer:**

- Error taxonomy (CF-32), health check aggregation (CF-16), centralized priority constants (CF-42), and documentation improvements can be addressed in subsequent releases without production risk.
