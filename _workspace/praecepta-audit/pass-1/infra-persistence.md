# infra-persistence — Library Usage Audit

**Upstream Libraries:** SQLAlchemy >=2.0, Alembic >=1.13, Redis >=5.0
**RAG Status:** AMBER
**Checklist:** 12/18 passed

## Findings

| ID | Severity | Checklist | Description | File:Line | Recommendation |
|----|----------|-----------|-------------|-----------|----------------|
| F-01 | CRITICAL | PE-7 | RLS helper functions use f-string interpolation for `table_name`, `policy_name`, and `cast_type` in DDL SQL. While these are developer-supplied values (not user input), there is no validation or quoting — a table name containing SQL metacharacters would produce malformed or injectable DDL. | `packages/infra-persistence/src/praecepta/infra/persistence/rls_helpers.py:18,29,51-55,69` | Use `sqlalchemy.sql.quoted_name()` or at minimum validate that identifiers match `^[a-z_][a-z0-9_]*$` before interpolation. |
| F-02 | HIGH | PE-8 | Pool sizes are hardcoded as integer literals (`pool_size=20`, `max_overflow=10` for async; `pool_size=5`, `max_overflow=5` for sync). They are not configurable via `DatabaseSettings` or environment variables. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:115-116,184-185` | Add `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle` fields to `DatabaseSettings` and thread them through to `create_async_engine()` / `create_engine()`. |
| F-03 | HIGH | PE-4 | Engine and session factory are module-level global singletons (`_engine`, `_session_factory`, `_sync_engine`, `_sync_session_factory`). While sessions themselves are request-scoped via `get_db_session()`, the global mutable state makes testing difficult, prevents per-tenant connection routing, and couples all callers to a single database. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:84-89` | Encapsulate engine + session factory in a class (e.g. `DatabaseManager`) that can be instantiated per configuration and injected via FastAPI dependency override. |
| F-04 | HIGH | PE-12 | Total connection budget is undocumented. Async pool (20 + 10 overflow = 30) plus sync pool (5 + 5 overflow = 10) = 40 connections per process. With multiple worker processes this can easily exceed PostgreSQL `max_connections` (default 100). No documentation warns about this. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:115-116,184-185` | Document the connection math in module docstring and `DatabaseSettings`. Consider adding a startup check that queries `SHOW max_connections` and logs a warning if the pool budget exceeds 80% of the limit. |
| F-05 | MEDIUM | PE-5 | No Alembic `env.py` or migration configuration exists in the package. Alembic is listed as a dependency and `rls_helpers.py` uses `alembic.op`, but there is no async engine wiring for Alembic's migration runner. Downstream consumers must provide their own `env.py`. | N/A (missing file) | Either provide a reusable async `env.py` template/helper that wires `create_async_engine()` into Alembic's `run_migrations_online()`, or document that consumers must provide their own. |
| F-06 | MEDIUM | PE-6 | `RedisFactory._create_client()` uses `aioredis.from_url()` which internally creates a `ConnectionPool`, but the pool is not explicitly constructed or exposed. This means pool lifecycle details (e.g. health checks, retry) are hidden inside redis-py internals, and the factory's `close()` relies on `aclose()` to clean up the implicit pool. | `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:130-138` | Consider explicitly creating `redis.asyncio.ConnectionPool` and passing it to `redis.asyncio.Redis(connection_pool=pool)` for full control over pool parameters, health checks, and shutdown ordering. |
| F-07 | MEDIUM | PE-13 | `DatabaseSettings` does not validate the connection string format. Individual fields (`host`, `port`, etc.) have basic types, but there is no `@field_validator` on the constructed URL (e.g. checking that the psycopg driver is loadable, that the host is not empty, or that the URL is well-formed). | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:42-80` | Add a `@model_validator(mode='after')` that calls `make_url()` on `database_url` to fail fast on invalid configurations. |
| F-08 | MEDIUM | PE-14 | Pool parameters have defaults in the engine creation code but are not documented in `DatabaseSettings`. Users must read source code to discover `pool_size=20`, `max_overflow=10`, `pool_recycle=3600`. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:113-120` | Move pool parameters into `DatabaseSettings` fields with `description=` docstrings so they appear in env-var documentation and `--help` output. |
| F-09 | LOW | PE-15 | `echo=False` is hardcoded in both engine factories. This is the correct default, but there is no way to enable SQL logging in development without editing source code. | `packages/infra-persistence/src/praecepta/infra/persistence/database.py:119,188` | Add an `echo: bool = Field(default=False, description="Enable SQLAlchemy SQL logging (development only)")` to `DatabaseSettings`. |
| F-10 | LOW | PE-16 | No evidence of session sharing between requests. `get_db_session()` yields a new session per call via `async with session_factory()`. However, the `get_redis_factory()` singleton uses `@lru_cache` which is not async-safe — concurrent first calls could race on factory creation (benign but impure). | `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:152-167` | Acceptable for current usage. If needed, replace `@lru_cache` with an explicit singleton pattern guarded by `asyncio.Lock`. |
| F-11 | LOW | N/A | `RedisFactory` and `get_redis_factory` are not exported from `__init__.py`, nor is `get_sync_session_factory`. Downstream packages use direct deep imports (e.g. `from praecepta.infra.persistence.database import get_sync_session_factory`). This is not incorrect but makes the public API surface unclear. | `packages/infra-persistence/src/praecepta/infra/persistence/__init__.py` | Add `RedisFactory`, `get_redis_factory`, `get_sync_session_factory`, and `get_sync_engine` to `__all__` exports, or document that deep imports are the intended pattern. |
| F-12 | LOW | N/A | No test coverage for `redis_client.py`. The `RedisFactory` class, `get_redis_factory()`, and the `close()` shutdown path are untested. | N/A (missing test file) | Add `test_redis_client.py` with unit tests covering factory creation, `from_url`, `from_env`, and the `close()` cleanup path. |

## Checklist Detail

| ID | Status | Notes |
|----|--------|-------|
| PE-1 | PASS | No `session.query()` usage anywhere. Code uses `text()` for parameterized SQL and `select()` style is implied by the 2.0 async session pattern (`Session.execute()`). |
| PE-2 | PASS | `create_async_engine()` is used with `pool_size`, `max_overflow`, `pool_pre_ping`, `pool_recycle`, and `echo` parameters. |
| PE-3 | PASS | `async_sessionmaker` is used for async sessions; `sessionmaker` is correctly paired with `create_engine` (sync) for projection use. |
| PE-4 | PARTIAL | Sessions are request-scoped via `get_db_session()` dependency. However, engine/factory singletons are module-level globals, making testing and multi-config scenarios difficult (F-03). |
| PE-5 | FAIL | No Alembic env.py or migration runner exists. `rls_helpers.py` provides DDL helpers for use inside migrations but no async migration wiring is provided (F-05). |
| PE-6 | PARTIAL | `redis.asyncio.from_url()` is used with `max_connections`, which internally creates a pool. However, the pool is not explicitly constructed, limiting control (F-06). |
| PE-7 | FAIL | `rls_helpers.py` uses f-string interpolation for SQL identifiers (`table_name`, `policy_name`) without validation or quoting (F-01). `tenant_context.py` correctly uses parameterized `set_config()` — but the DDL helpers do not. |
| PE-8 | FAIL | Pool sizes are hardcoded integer literals, not configurable via settings or environment (F-02). |
| PE-9 | PARTIAL | `max_overflow=10` (async) and `max_overflow=5` (sync) are reasonable defaults, but without configurability they cannot be tuned per deployment (F-02). |
| PE-10 | PASS | `dispose_engine()` disposes both async and sync engines and nulls the globals. |
| PE-11 | PASS | `RedisFactory.close()` calls `aclose()` on the client and nulls the reference. |
| PE-12 | FAIL | Connection budget (40 connections/process) is undocumented and has no runtime validation against PostgreSQL limits (F-04). |
| PE-13 | FAIL | No URL format validation beyond Pydantic field types. No `model_validator` or `make_url()` check (F-07). |
| PE-14 | FAIL | Pool parameters have undocumented hardcoded defaults, not exposed as settings fields (F-08). |
| PE-15 | PARTIAL | `echo=False` is correctly defaulted but not configurable without code changes (F-09). |
| PE-16 | PASS | No session sharing detected. Each request gets a fresh session via the async generator dependency. |
| PE-17 | PASS | `get_db_session()` uses `async with session_factory()` which handles commit/rollback at context exit, plus explicit `session.close()` in `finally`. `tenant_context.py` uses `SET LOCAL` which is transaction-scoped. |
| PE-18 | PASS | No nested transactions / savepoints used. Tenant context handler fires on `after_begin` including savepoints, which is correct — `SET LOCAL` is idempotent. |

## Narrative

The `infra-persistence` package demonstrates generally correct SQLAlchemy 2.0 usage. The async/sync engine split is well-reasoned (async for query endpoints, sync for projections), and the tenant context propagation via `SET LOCAL` / `set_config()` with parameterized queries is a strong security pattern.

The most significant concern is the **SQL injection surface in `rls_helpers.py`** (F-01). While table and policy names are developer-supplied (not user input), they flow through f-strings into `op.execute()` without any identifier quoting. In a multi-team monorepo this is a latent vulnerability — a migration author could inadvertently pass unsanitized input. This is classified CRITICAL because it affects the RLS security boundary.

The second cluster of issues relates to **configuration rigidity** (F-02, F-04, F-07, F-08, F-09). Pool sizes, overflow limits, echo flags, and other tuning parameters are hardcoded rather than exposed through `DatabaseSettings`. This means production tuning requires code changes and redeployment rather than environment variable adjustment — a significant operational friction point.

The **absence of Alembic migration wiring** (F-05) is notable given that Alembic is a declared dependency. The package provides DDL helpers for use *inside* migrations but does not provide the `env.py` or runner infrastructure needed to execute those migrations with async engines. Downstream consumers must solve this independently.

The anti-patterns from the projection remediation checklist are **not present** in this package. There is no polling-where-subscriptions-exist pattern, no N+1 resource multiplication, and no bypassing of purpose-built abstractions. The module-level singleton pattern (F-03) is a mild convention gap but is standard in FastAPI applications.

**Overall assessment:** The package is functional and follows modern SQLAlchemy patterns, but lacks the configuration flexibility and defensive validation expected of a shared infrastructure package in a multi-tenant system. The RLS identifier injection risk should be addressed before production use.
