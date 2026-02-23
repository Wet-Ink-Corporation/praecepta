# Praecepta Infrastructure Audit — Migration Guide

**Date:** 2026-02-22
**Commit:** `c55b9bc` on `main`
**Scope:** 42 audit findings remediated across 74 files in 8 infrastructure packages

---

## Overview

This release remediates 42 findings from a comprehensive infrastructure audit covering all 5 Praecepta infrastructure packages, the foundation-application package, and both domain packages. The changes improve security, resource lifecycle management, and convention compliance.

**This is a breaking change release.** Downstream consumers should read the required actions below before upgrading.

---

## Breaking Changes

### 1. Middleware classes are now pure ASGI

**What changed:** `RequestIdMiddleware`, `RequestContextMiddleware`, `TenantStateMiddleware`, and `TraceContextMiddleware` no longer extend Starlette's `BaseHTTPMiddleware`. They are now pure ASGI middleware classes with `__init__(self, app)` and `async __call__(self, scope, receive, send)` signatures.

**Impact:** If you subclass or directly instantiate any of these middlewares, your code will break.

**Required action:**
- If you use `create_app()` (recommended), **no action needed** — the app factory handles middleware registration.
- If you manually call `app.add_middleware(RequestIdMiddleware)`, this still works unchanged.
- If you subclass any middleware, update your subclass to follow the pure ASGI pattern:
  ```python
  class MyMiddleware:
      def __init__(self, app):
          self.app = app

      async def __call__(self, scope, receive, send):
          if scope["type"] not in ("http", "websocket"):
              await self.app(scope, receive, send)
              return
          # your logic here
          await self.app(scope, receive, send)
  ```

### 2. `/healthz` endpoint returns richer JSON

**What changed:** The health endpoint now aggregates database and Redis health checks.

**Old response (HTTP 200):**
```json
{"status": "ok"}
```

**New response (HTTP 200 when healthy, HTTP 503 when degraded):**
```json
{
  "status": "ok",
  "checks": {
    "database": {"status": "ok"},
    "redis": {"status": "ok"}
  }
}
```

**Required action:**
- Update any health check consumers (load balancers, Kubernetes probes, monitoring) that parse the response body.
- If you only check the HTTP status code (200 = healthy), **no action needed**.
- If you check `response.json()["status"] == "ok"`, this still works.
- If you assert `response.json() == {"status": "ok"}`, update to check `response.json()["status"] == "ok"` instead.

### 3. `MiddlewareContribution` default priority changed

**What changed:** Default priority changed from `500` to `400`. Maximum allowed priority is now `499` (was unbounded). Priority range is enforced as `[0, 499]`.

**Required action:**
- If you have middleware with `priority=500` or higher, reduce it to `499` or below.
- If you rely on the default priority, note it is now `400` instead of `500`.
- Priority bands: `0-99` outermost, `100-199` security, `200-299` context, `300-399` policy, `400-499` application.

### 4. New lifespan hooks are auto-discovered

**What changed:** Three new lifespan hooks are now registered via entry points and auto-discovered by `create_app()`:

| Entry point name | Package | Priority | Requires |
|-----------------|---------|----------|----------|
| `auth` | infra-auth | 60 | JWKS endpoint (issuer URL) |
| `persistence` | infra-persistence | 75 | PostgreSQL + Redis |
| `taskiq` | infra-taskiq | 150 | Redis broker |

**Required action:**
- **Production applications** that have PostgreSQL, Redis, and an OIDC issuer: **no action needed** — these hooks will start/stop resources automatically.
- **Test fixtures** that create an app without external services: add the entry point names to your `exclude_names`:
  ```python
  app = create_app(
      exclude_names=frozenset({
          "auth",           # NEW — needs JWKS endpoint
          "persistence",    # NEW — needs PostgreSQL + Redis
          "taskiq",         # NEW — needs Redis broker
          # ... your existing exclusions
      })
  )
  ```
- **Dev/example apps** (like Dog School): the default exclusion list has been updated. If you override `exclude_names`, add the three new names.

---

## New Features

### DatabaseManager class (`infra-persistence`)

The database module now exposes a `DatabaseManager` class that encapsulates engine, session factory, and settings. The module-level functions (`get_engine()`, `get_session_factory()`, etc.) still work as before — they delegate to a default manager singleton.

```python
from praecepta.infra.persistence.database import get_database_manager

manager = get_database_manager()
engine = manager.get_engine()
await manager.dispose()  # Clean shutdown
```

### Configurable pool sizes (`infra-persistence`)

Database connection pool sizes are now configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_ASYNC_POOL_SIZE` | 10 | Async engine pool size |
| `DB_ASYNC_MAX_OVERFLOW` | 5 | Async engine max overflow |
| `DB_SYNC_POOL_SIZE` | 3 | Sync engine pool size |
| `DB_SYNC_MAX_OVERFLOW` | 2 | Sync engine max overflow |
| `DB_POOL_TIMEOUT` | 30 | Pool checkout timeout (seconds) |
| `DB_POOL_RECYCLE` | 3600 | Connection recycle interval (seconds) |
| `DB_ECHO` | false | SQL logging |

### TaskIQ settings (`infra-taskiq`)

TaskIQ now loads configuration from environment variables with `TASKIQ_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `TASKIQ_REDIS_URL` | `redis://localhost:6379/1` | Redis broker URL (database 1) |
| `TASKIQ_RESULT_TTL` | 3600 | Result TTL in seconds |
| `TASKIQ_STREAM_PREFIX` | `taskiq` | Redis stream key prefix |

Note: TaskIQ defaults to Redis database 1 to avoid collision with the persistence Redis on database 0.

### Trace sampling rate (`infra-observability`)

Configure trace sampling via environment variable:

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_TRACE_SAMPLE_RATE` | 1.0 | Sampling rate (0.0 = none, 1.0 = all) |

### Lifespan priority constants (`foundation-application`)

Standard priority constants are now exported for consistent lifespan ordering:

```python
from praecepta.foundation.application import (
    LIFESPAN_PRIORITY_OBSERVABILITY,   # 50
    LIFESPAN_PRIORITY_PERSISTENCE,     # 75
    LIFESPAN_PRIORITY_EVENTSTORE,      # 100
    LIFESPAN_PRIORITY_TASKIQ,          # 150
    LIFESPAN_PRIORITY_PROJECTIONS,     # 200
)
```

### OIDC discovery (`infra-auth`)

`JWKSProvider` now attempts OIDC discovery from `{issuer}/.well-known/openid-configuration` to resolve `jwks_uri`. It validates the issuer claim matches and falls back to the constructed URI (`{issuer}/.well-known/jwks.json`) if discovery fails.

### Shared httpx client (`infra-auth`)

`OIDCTokenClient` now accepts an optional shared `httpx.AsyncClient` and provides `aclose()` for cleanup:

```python
client = OIDCTokenClient(base_url, client_id, client_secret)
# ... use client ...
await client.aclose()  # Clean up owned httpx client
```

### TaskIQ error hierarchy (`infra-taskiq`)

New structured exception classes for dead-letter queue classification:

```python
from praecepta.infra.taskiq import (
    TaskIQError,                # Base (permanent)
    TaskIQBrokerError,          # Transient — retryable
    TaskIQSerializationError,   # Permanent — dead-letter
    TaskIQResultError,          # Transient — retryable
)
```

### Alembic async migration template (`infra-persistence`)

Reusable template for async Alembic migrations:

```python
from praecepta.infra.persistence.alembic_env_template import run_async_migrations
from praecepta.infra.persistence.database import get_database_manager
from myapp.models import Base

import asyncio
manager = get_database_manager()
asyncio.run(run_async_migrations(manager.get_engine(), Base.metadata))
```

### AppSettings version from package metadata (`infra-fastapi`)

`AppSettings.version` now defaults to the installed package version via `importlib.metadata` instead of a hardcoded `"0.1.0"`. Override with `APP_VERSION` env var if needed.

---

## Security Improvements

| Change | Description |
|--------|-------------|
| **SQL injection guard** | RLS helper functions (`create_rls_policy`, `drop_rls_policy`, etc.) now validate table/policy/type identifiers against `[a-z_][a-z0-9_]*` regex. Invalid identifiers raise `ValueError`. |
| **CORS credentials + wildcard** | `CORSSettings` now rejects `allow_credentials=True` with `allow_origins=["*"]` at startup. |
| **Auth issuer HTTPS** | `AuthSettings` validates that `AUTH_ISSUER` is an HTTPS URL when `AUTH_DEV_BYPASS` is not enabled. |
| **Debug mode** | Error handler no longer reads `DEBUG` from `os.environ`. Uses `request.app.debug` (the FastAPI app's debug flag). |
| **W3C TraceContext** | Explicit `W3CTraceContextTextMapPropagator` set on trace provider (no longer relying on SDK default). |

---

## What You Don't Need to Change

- **`create_app()` usage** — Works the same. New hooks auto-wire.
- **`get_engine()` / `get_session_factory()` / `get_db_session()`** — Still work as module-level functions.
- **`get_redis_factory()`** — Same API, now with explicit connection pool internally.
- **Projection base class** — `BaseProjection` API unchanged.
- **Entry-point registration** — Same `pyproject.toml` pattern.
- **Test markers** — `@pytest.mark.unit`, `@pytest.mark.integration` unchanged.

---

## Environment Variable Summary

New environment variables introduced in this release:

```bash
# Database pool sizing (infra-persistence)
DB_ASYNC_POOL_SIZE=10
DB_ASYNC_MAX_OVERFLOW=5
DB_SYNC_POOL_SIZE=3
DB_SYNC_MAX_OVERFLOW=2
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_ECHO=false

# TaskIQ (infra-taskiq)
TASKIQ_REDIS_URL=redis://localhost:6379/1
TASKIQ_RESULT_TTL=3600
TASKIQ_STREAM_PREFIX=taskiq

# Trace sampling (infra-observability)
OTEL_TRACE_SAMPLE_RATE=1.0

# Event sourcing (infra-eventsourcing)
ES_MAX_PROJECTION_RUNNERS=8
```

All have sensible defaults. No environment changes required unless you want to tune.

---

## Test Impact

- **923 tests pass** (905 unit + 18 integration)
- **New test files:** 8 created (`test_health.py`, `test_auth_lifespan.py`, `test_redis_client.py`, `test_errors.py`, `test_lifespan.py` for persistence/taskiq, `test_settings.py` for taskiq, `test_subscription_runner.py`)
- **Updated test files:** 17 modified to cover new behavior
- If your tests create an app without mocking external services, add `"auth"`, `"persistence"`, `"taskiq"` to your `exclude_names` fixture (see Breaking Change #4 above)

---

## Packages Affected

| Package | Changes |
|---------|---------|
| `praecepta-foundation-application` | Lifespan priority constants, middleware priority band enforcement |
| `praecepta-infra-persistence` | DatabaseManager, lifespan hook, pool settings, Redis pool, RLS guards, Alembic template, connection string validation |
| `praecepta-infra-auth` | Lifespan hook, OIDC discovery, shared httpx client, issuer HTTPS validation |
| `praecepta-infra-fastapi` | Pure ASGI middleware, aggregated health check, CORS validator, debug mode fix, version from metadata, lifespan error logging |
| `praecepta-infra-observability` | Trace sampler, W3C propagator, pure ASGI middleware, priority fix |
| `praecepta-infra-taskiq` | Settings, lifespan hook, factory functions, error hierarchy |
| `praecepta-infra-eventsourcing` | Max projection runners setting |
| `praecepta-domain-identity` | Projection base class updates (from eventsourcing changes) |
| `praecepta-domain-tenancy` | Projection base class updates (from eventsourcing changes) |
