# Resource Budget -- Cross-Cutting Audit

**Auditor:** T-01 (Cross-Cutting Theme Agent)
**Date:** 2026-02-22
**Scope:** All infrastructure packages (`infra-persistence`, `infra-eventsourcing`, `infra-auth`, `infra-taskiq`, `infra-observability`, `infra-fastapi`)

## Resource Inventory

### PostgreSQL Connections

| Source | Package | Pool Size | Max Overflow | Total Possible | Configurable |
|--------|---------|-----------|-------------|----------------|--------------|
| Async engine (query endpoints) | infra-persistence | 20 | 10 | 30 | No (hardcoded) |
| Sync engine (projections) | infra-persistence | 5 | 5 | 10 | No (hardcoded) |
| Event store (eventsourcing lib) | infra-eventsourcing | 5 | 10 | 15 | Yes (`POSTGRES_POOL_SIZE`, `POSTGRES_MAX_OVERFLOW`) |
| SubscriptionProjectionRunner (1 per projection) | infra-eventsourcing | 5 | 10 | 15 per runner | Yes (same `POSTGRES_*` env vars) |
| Alembic migration runner | infra-persistence (consumer-provided) | 1 | 0 | 1 | N/A (single connection) |

**Notes on SubscriptionProjectionRunner:**

Each `SubscriptionProjectionRunner` creates one `EventSourcedProjectionRunner` per projection class. Each runner internally instantiates one upstream application instance, which in turn creates its own PostgreSQL connection pool via the eventsourcing library. The pool parameters are governed by `EventSourcingSettings` (`POSTGRES_POOL_SIZE=5`, `POSTGRES_MAX_OVERFLOW=10`), so each projection runner can consume up to 15 connections.

With the current domain packages registering 4 projections (2 in `domain-tenancy`, 2 in `domain-identity`), this yields 4 runner instances.

### Redis Connections

| Source | Package | Pool Size | Configurable | Default URL |
|--------|---------|-----------|--------------|-------------|
| Persistence cache client | infra-persistence | 10 | Yes (`REDIS_POOL_SIZE`, bounded 1-100) | `REDIS_URL` or `redis://localhost:6379/0` |
| Task queue broker (RedisStreamBroker) | infra-taskiq | Unspecified (library default) | No | `REDIS_URL` or `redis://localhost:6379/0` |
| Task result backend (RedisAsyncResultBackend) | infra-taskiq | Unspecified (library default) | No | `REDIS_URL` or `redis://localhost:6379/0` |
| Schedule source (ListRedisScheduleSource) | infra-taskiq | Unspecified (library default) | No | `REDIS_URL` or `redis://localhost:6379/0` |

### HTTP Client Connections

| Source | Package | Pool Size | Notes |
|--------|---------|-----------|-------|
| OIDCTokenClient | infra-auth | 0 (per-call) | New `httpx.AsyncClient` per method call; no persistent pool |
| JWKSProvider (PyJWKClient) | infra-auth | 1 (urllib3 default) | Synchronous urllib3 under PyJWKClient; one cached keyset with TTL |

### Background Threads/Tasks

| Source | Package | Count | Notes |
|--------|---------|-------|-------|
| SubscriptionProjectionRunner threads | infra-eventsourcing | 1 per projection | Each `EventSourcedProjectionRunner` uses a dedicated LISTEN/NOTIFY subscription thread |
| ProjectionPoller thread (deprecated) | infra-eventsourcing | 1 (if used) | Single daemon thread for poll loop; deprecated in favor of subscription runner |
| TaskIQ workers | infra-taskiq | External process | Workers run as separate `taskiq worker` processes, not in-app threads |
| TaskIQ scheduler | infra-taskiq | External process | Runs as separate `taskiq scheduler` process (single instance only) |

### Total Budget Summary (Single Process, Default Configuration)

| Resource | Calculation | Total | Default Limit | Status |
|----------|-------------|-------|---------------|--------|
| PostgreSQL connections (no projections) | 30 (async) + 10 (sync) + 15 (event store) | 55 | 100 (PG default `max_connections`) | AMBER -- 55% of default limit |
| PostgreSQL connections (4 projections) | 55 + (4 x 15) | 115 | 100 (PG default `max_connections`) | RED -- exceeds default limit |
| PostgreSQL connections (4 projections, 2 workers) | 115 x 2 | 230 | 100 (PG default `max_connections`) | RED -- 2.3x default limit |
| Redis connections (persistence only) | 10 | 10 | 10000 (Redis default) | GREEN |
| Redis connections (persistence + taskiq) | 10 + ~30 (est. broker+backend+schedule) | ~40 | 10000 (Redis default) | GREEN |
| Background threads (4 projections) | 4 | 4 | N/A | GREEN |
| httpx clients (per auth call) | 0 persistent, 1 ephemeral per call | 0 persistent | N/A | GREEN (but wasteful) |

## Findings

| ID | Severity | Checklist | Packages Affected | Description | Recommendation |
|----|----------|-----------|-------------------|-------------|----------------|
| XC-R1 | HIGH | XC-R1 FAIL | infra-persistence, infra-eventsourcing | Total PostgreSQL connection count is not documented anywhere. With default settings, a single process running 4 projection subscriptions consumes up to 115 connections, exceeding the PostgreSQL default of `max_connections=100`. The async engine (30), sync engine (10), event store (15), and per-projection runners (4 x 15 = 60) are configured independently with no aggregation or budget check. | (1) Document the connection math in a central location (e.g., deployment guide or `DatabaseSettings` docstring). (2) Add a startup health check that queries `SHOW max_connections` and compares against the computed budget. (3) Reduce the eventsourcing pool defaults: `POSTGRES_POOL_SIZE=2` and `POSTGRES_MAX_OVERFLOW=3` for projection runners, since each runner processes events sequentially. |
| XC-R2 | MEDIUM | XC-R2 FAIL | infra-persistence, infra-taskiq | Total Redis connection count is not documented. More critically, both packages read from the same `REDIS_URL` environment variable (default `redis://localhost:6379/0`) with no namespace separation. The persistence pool is configurable (`REDIS_POOL_SIZE`), but the taskiq broker, result backend, and schedule source use library defaults with no configuration surface. | (1) Document the shared-Redis topology. (2) Use separate env vars (`TASKIQ_REDIS_URL` vs `REDIS_URL`) with fallback. (3) Consider using different Redis database numbers (e.g., persistence on `/0`, taskiq on `/1`) for logical isolation. (4) Expose taskiq Redis pool configuration via a `TaskIQSettings` class. |
| XC-R3 | LOW | XC-R3 PARTIAL | infra-eventsourcing | Background thread count is partially documented. The `SubscriptionProjectionRunner` docstring states "dedicated background thread per projection," which is accurate. However, there is no runtime logging or monitoring of total thread count at startup, and no centralized documentation of thread budget. | Add a log line at projection lifespan startup summarizing total thread count: "Starting N subscription threads for M projections." Consider exposing thread count via the health endpoint. |
| XC-R4 | HIGH | XC-R4 FAIL | infra-persistence, infra-eventsourcing | The `infra-persistence` async pool has `max_overflow=10` (bounded), which is correct. However, each `EventSourcedProjectionRunner` creates an independent application instance whose pool parameters are governed by `EventSourcingSettings`. There is no mechanism to limit the total number of runners (and thus pools). If a downstream consumer registers many projections, each one spawns a new pool with up to 15 connections, with no aggregate cap. The persistence `RedisFactory` uses `from_url()` which creates an implicit `ConnectionPool`; the pool's `max_connections` is set from settings (bounded 1-100), which is fine. The taskiq Redis connections have no explicit pool configuration, relying on library defaults (no documented max). | (1) Add a configurable `max_projection_runners` setting with a sensible default (e.g., 8) and reject additional projections beyond the limit. (2) Reduce default pool size for projection runner application instances (they process events sequentially, so `pool_size=1, max_overflow=1` is sufficient). (3) Expose taskiq Redis pool configuration. |
| XC-R5 | MEDIUM | XC-R5 FAIL | infra-persistence, infra-eventsourcing | Resource defaults are tuned for neither single-instance dev nor multi-instance production. The async pool (`pool_size=20`) is oversized for development and the per-projection pools (`pool_size=5, max_overflow=10`) are oversized for sequential event processing. In production with multiple Uvicorn workers (e.g., 4 workers), the total budget multiplies to 460 connections (115 x 4), which requires a PostgreSQL `max_connections` of at least 500, or use of PgBouncer. Neither scenario is documented. | (1) Make all pool sizes configurable via environment variables (infra-persistence F-02 already recommends this). (2) Document recommended settings for dev (small pools) vs production (right-sized pools + PgBouncer). (3) Provide example `.env` files for both deployment profiles. |
| XC-R6 | MEDIUM | XC-R4 | infra-eventsourcing | The deprecated `ProjectionPoller` (still exported and importable) uses `SingleThreadedRunner`, which creates N+1 application instances (1 upstream + N projections), each with its own connection pool. The deprecation warning is present but the class remains fully functional. If accidentally used alongside `SubscriptionProjectionRunner`, both would consume connection pools simultaneously with no conflict detection. | (1) Consider removing `ProjectionPoller` from `__all__` exports to discourage use. (2) Add a runtime guard in the projection lifespan that detects if a `ProjectionPoller` is already running. |
| XC-R7 | LOW | XC-R4 | infra-auth | `OIDCTokenClient` creates an unbounded number of `httpx.AsyncClient` instances (one per method call). Each instance opens a new TCP connection and performs a TLS handshake. While individually short-lived (closed by context manager), under a token refresh storm this becomes a resource multiplication issue. The `httpx.AsyncClient` default connection pool is 100 connections per host, but since each client is independent, there is no shared pool limit. | Move to a lifespan-scoped singleton `httpx.AsyncClient` with explicit `limits=httpx.Limits(max_connections=10)` to bound outbound connection count. |

## Analysis

### Connection Budget Exceeds PostgreSQL Defaults

The most significant cross-cutting resource concern is the aggregate PostgreSQL connection consumption. Three independent packages -- `infra-persistence` (async + sync engines), `infra-eventsourcing` (event store), and `infra-eventsourcing` (projection runners) -- each maintain their own connection pools with no awareness of the others. The total budget calculation reveals that even a single-process deployment with 4 projections requires 115 connections, which exceeds the PostgreSQL default of `max_connections=100`.

This is the classic "N independent pools" anti-pattern where each component is individually reasonable but the aggregate is not. The projection subscription runner is the primary multiplier: each projection class spawns a new `EventSourcedProjectionRunner`, which instantiates a full application with its own pool. For sequential event processing, a pool size of 5 with overflow of 10 is excessive -- a single connection with minimal overflow would suffice.

### Configuration Asymmetry

The eventsourcing package exposes pool configuration via `EventSourcingSettings` (`POSTGRES_POOL_SIZE`, `POSTGRES_MAX_OVERFLOW`), which is good practice. However, the persistence package hardcodes its pool sizes (`pool_size=20`, `max_overflow=10` for async; `pool_size=5`, `max_overflow=5` for sync) with no settings surface. This asymmetry means an operator can tune the event store pool but not the read model pool, which is counterproductive since the read model pool is typically the larger consumer.

### Redis Resource Collision

Both `infra-persistence` and `infra-taskiq` default to the same `REDIS_URL` (`redis://localhost:6379/0`). The persistence package uses a structured `RedisSettings` class with `REDIS_*` environment variables, while taskiq uses raw `os.getenv("REDIS_URL")`. This means they share the same Redis instance and database with no logical separation. While Redis handles multiplexing well, this creates operational confusion (task queue keys mixed with cache keys) and makes it impossible to independently scale or monitor the two workloads.

### Recommendations Priority

1. **Immediate (before production):** Reduce projection runner pool defaults to `pool_size=1, max_overflow=2`. This alone drops the 4-projection budget from 115 to 67 connections.
2. **Short-term:** Make `infra-persistence` pool sizes configurable via `DatabaseSettings`. Document the total connection budget.
3. **Medium-term:** Add a startup connection budget check that queries `SHOW max_connections` and warns if the computed pool budget exceeds 80%. Separate Redis URLs for taskiq vs persistence.
4. **Long-term:** Consider a centralized `ResourceBudget` configuration that allocates connection slots across packages, enforced at startup.
