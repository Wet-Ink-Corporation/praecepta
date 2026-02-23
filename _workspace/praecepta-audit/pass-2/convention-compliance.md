# Convention Compliance -- Cross-Cutting Audit

**Auditor:** T-03 (Convention Compliance)
**Date:** 2026-02-22
**Packages in scope:** infra-fastapi, infra-auth, infra-persistence, infra-observability, infra-taskiq, infra-eventsourcing

## Convention Matrix

### Settings Pattern (XC-C1)

| Package | Uses BaseSettings | env_prefix | Validates | Notes |
|---------|-------------------|------------|-----------|-------|
| infra-fastapi | Yes (`AppSettings`, `CORSSettings`) | `APP_`, `CORS_` | Yes -- field validators, extra=ignore | Exemplary implementation |
| infra-auth | Yes (`AuthSettings`) | `AUTH_` | Partial -- `jwks_cache_ttl` has bounds; `issuer` has no format validation (P1-F-04) | Missing HTTPS enforcement on issuer |
| infra-persistence | Yes (`DatabaseSettings`, `RedisSettings`) | `DATABASE_`, none (RedisSettings) | Partial -- no URL format validator, no pool param exposure | `RedisSettings` has no `env_prefix`; fields named `redis_*` so env vars are e.g. `REDIS_HOST` by convention |
| infra-observability | Yes (`LoggingSettings`, `TracingSettings`) | `""` (empty) | Yes -- log level validation, environment checks | Empty prefix is intentional (matches OTel env var conventions: `OTEL_SERVICE_NAME`, `LOG_LEVEL`) |
| infra-eventsourcing | Yes (`EventSourcingSettings`, `ProjectionPollingSettings`) | none / `PROJECTION_` | Partial -- production CREATE_TABLE check uses `os.getenv` directly | `EventSourcingSettings` has no prefix; matches upstream `eventsourcing` lib env var names |
| infra-taskiq | **No** | N/A | N/A | Uses raw `os.getenv("REDIS_URL")` -- the only infra package without `BaseSettings` |

### Entry-Point Registration

| Package | Applications | Projections | Middleware | Lifespan | Routers | Error Handlers |
|---------|-------------|-------------|------------|----------|---------|----------------|
| infra-fastapi | -- | -- | request_id, request_context, tenant_state | -- | _health_stub | rfc7807 |
| infra-auth | -- | -- | api_key_auth, jwt_auth | -- | -- | -- |
| infra-persistence | -- | -- | -- | **None** | -- | -- |
| infra-observability | -- | -- | trace_context | observability | -- | -- |
| infra-eventsourcing | -- | -- | -- | event_store, projection_runner | -- | -- |
| infra-taskiq | **None** | **None** | **None** | **None** | **None** | **None** |

### Public API Exports (XC-C3)

| Package | Has `__all__` | Exports documented | Notes |
|---------|------------|-------------------|-------|
| infra-fastapi | Yes (14 symbols) | Yes | Comprehensive; re-exports foundation context utilities |
| infra-auth | Yes (16 symbols) | Yes | Includes `DEV_BYPASS_CLAIMS` constant |
| infra-persistence | Yes (10 symbols) | Partial | Missing: `RedisFactory`, `get_redis_factory`, `get_sync_session_factory`, `get_sync_engine` (P1-F-11) |
| infra-observability | Yes (9 symbols) | Yes | Includes `lifespan_contribution` |
| infra-eventsourcing | Yes (10 symbols) | Yes | Deprecated items marked with `# deprecated` comments |
| infra-taskiq | Yes (3 symbols) | Minimal | Exports only `broker`, `result_backend`, `scheduler` singletons |

### PEP 420 Implicit Namespace Compliance (XC-C4)

| Package | `praecepta/__init__.py` absent | `praecepta/infra/__init__.py` absent | Leaf `__init__.py` present | Status |
|---------|-------------------------------|-------------------------------------|---------------------------|--------|
| infra-fastapi | Yes | Yes | Yes | PASS |
| infra-auth | Yes | Yes | Yes | PASS |
| infra-persistence | Yes | Yes | Yes | PASS |
| infra-observability | Yes | Yes | Yes | PASS |
| infra-eventsourcing | Yes | Yes | Yes | PASS |
| infra-taskiq | Yes | Yes | Yes | PASS |

### Deprecation Handling (XC-C5)

| Package | Deprecated symbols | Has DeprecationWarning | Has migration guidance | Status |
|---------|-------------------|----------------------|----------------------|--------|
| infra-eventsourcing | `ProjectionPoller`, `ProjectionPollingSettings`, `ProjectionRunner` | Yes (in `__init__` on construct) | Yes -- warns to use `SubscriptionProjectionRunner` instead | PASS |
| All others | None identified | N/A | N/A | PASS (no deprecated code) |

### Direct `os.environ` Usage (XC-C6)

| Package | File | Usage | Severity | Notes |
|---------|------|-------|----------|-------|
| infra-fastapi | `error_handlers.py:513` | `os.environ.get("DEBUG")` | MEDIUM | Bypasses `AppSettings.debug` (APP_DEBUG). Security risk: wrong prefix could leak stack traces. |
| infra-auth | `dev_bypass.py:42` | `os.environ.get("ENVIRONMENT")` | LOW | Production lockout check. Could use `AuthSettings` instead, but the standalone check is defensive. |
| infra-persistence | `redis_client.py:78` | `os.getenv("REDIS_URL")` | LOW | Used in `RedisFactory.from_env()` as a convenience shortcut before falling back to `RedisSettings`. |
| infra-eventsourcing | `lifespan.py:52-73` | Writes to `os.environ` | MEDIUM | Bridges settings to env vars for upstream `eventsourcing` library which reads `os.environ` directly. This is a documented, intentional workaround for a third-party constraint. |
| infra-eventsourcing | `event_store.py:120-134` | `os.getenv("DATABASE_URL")` etc. | MEDIUM | Same bridge pattern -- reads env vars for upstream library compatibility. |
| infra-eventsourcing | `settings.py:155` | `os.getenv("ENVIRONMENT")` | LOW | Inside a field validator for production safety check. |
| infra-taskiq | `broker.py:57` | `os.getenv("REDIS_URL")` | HIGH | Entire config via raw `os.getenv`. No `BaseSettings` at all. |

### Async/Sync Model (XC-A1 through XC-A4)

| Package | Commands (sync) | Queries (async) | Projections (sync) | Violations |
|---------|----------------|-----------------|-------------------|------------|
| infra-fastapi | N/A (framework layer) | N/A | N/A | None |
| infra-auth | N/A | Async (`httpx.AsyncClient` for OIDC, async middleware) | N/A | None -- but per-call AsyncClient has no pooling |
| infra-persistence | Sync engine for projections (`create_engine`) | Async engine for queries (`create_async_engine`) | Sync session factory available | None -- clean split |
| infra-observability | N/A | Async middleware | N/A | None |
| infra-eventsourcing | Sync event store operations | N/A | Sync projection handlers (BaseProjection) | None -- projections correctly sync |
| infra-taskiq | N/A | Async broker operations | N/A | None |

**XC-A4 (Blocking calls in async):** One instance found in domain-identity (`time.sleep(0.05)` in `user_provisioning.py:113`) but this is in a domain package, not infra. No blocking sync calls found in async contexts within infra packages.

### Error Propagation (XC-E1 through XC-E3)

| Checklist | Status | Evidence |
|-----------|--------|----------|
| XC-E1: Infrastructure errors wrapped | Partial | `infra-fastapi` error handlers map domain exceptions (`AuthenticationError`, `AuthorizationError`, `ResourceNotFoundError`, etc.) to HTTP status codes. However, `infra-persistence` does not wrap `SQLAlchemyError`; raw DB exceptions could propagate if callers do not catch them. |
| XC-E2: RFC 7807 Problem Details | Yes (infra-fastapi only) | `ProblemDetail` model in `error_handlers.py` produces RFC 7807 responses. Registered via `praecepta.error_handlers` entry point. Other packages do not produce HTTP responses directly. |
| XC-E3: Transient vs permanent errors | Not implemented | No package distinguishes transient errors (connection timeout, Redis unavailable) from permanent errors (invalid query, missing table). No retry classification exists. `infra-taskiq` has no error handling at all (P1-F-09). |

## Findings

| ID | Severity | Packages Affected | Checklist | Description | Recommendation |
|----|----------|-------------------|-----------|-------------|----------------|
| CC-01 | HIGH | infra-taskiq | XC-C1 | **No BaseSettings class.** The only infra package using raw `os.getenv()` for all configuration. Breaks the monorepo convention that every configurable package uses `pydantic_settings.BaseSettings` with `env_prefix`. Prevents type validation, `.env` file support, and centralized config documentation. | Create `TaskIQSettings(BaseSettings)` with `env_prefix="TASKIQ_"`. Add fields for `redis_url`, `result_ttl`, `stream_prefix`. Add `pydantic-settings` to dependencies. |
| CC-02 | HIGH | infra-taskiq | XC-C2 | **No LifespanContribution.** The only infra package with lifecycle requirements (broker startup/shutdown) that does not register a `LifespanContribution`. Broker connections are never properly initialized or cleaned up. | Create an `@asynccontextmanager` lifespan that calls `broker.startup()` / `broker.shutdown()`. Register via `[project.entry-points."praecepta.lifespan"]`. |
| CC-03 | HIGH | infra-taskiq | XC-C6 | **Redis URL collision.** Uses bare `REDIS_URL` env var, identical to infra-persistence's `RedisFactory.from_env()`. Both default to `redis://localhost:6379/0`. In production, task queue and persistence traffic compete on the same Redis database with no separation. | Use `TASKIQ_REDIS_URL` with fallback to `REDIS_URL`. Document the resource separation strategy. |
| CC-04 | MEDIUM | infra-fastapi | XC-C6 | **Debug mode reads `os.environ` directly.** `error_handlers.py:513` reads `os.environ.get("DEBUG")` instead of `request.app.debug` (which is set from `AppSettings.debug` using `APP_DEBUG` prefix). A stray `DEBUG=true` in the environment could leak stack traces in production without the `APP_` prefix guard. | Replace with `request.app.debug` which is already wired from `AppSettings`. |
| CC-05 | MEDIUM | infra-persistence | XC-C3 | **Incomplete public API exports.** `RedisFactory`, `get_redis_factory`, `get_sync_session_factory`, and `get_sync_engine` are not exported from `__init__.py`. Downstream packages must use deep imports. The public API surface is ambiguous. | Add the missing symbols to `__all__` or document that deep imports are intentional. |
| CC-06 | MEDIUM | infra-persistence | XC-C1 | **RedisSettings has no env_prefix.** Unlike every other settings class which uses a prefix (`APP_`, `AUTH_`, `DATABASE_`, `CORS_`, `PROJECTION_`), `RedisSettings` relies on field names (`redis_host`, etc.) to produce env var names like `REDIS_HOST`. While functional, this deviates from the `env_prefix` convention and fields could collide with unrelated `REDIS_*` vars if another package introduces similarly named fields. | Add `env_prefix="REDIS_"` and rename fields to `host`, `port`, etc. to produce identical env var names, aligning with the prefix convention. |
| CC-07 | MEDIUM | infra-eventsourcing | XC-C6 | **Deliberate `os.environ` bridging.** The lifespan hook writes settings to `os.environ` because the upstream `eventsourcing` library reads env vars directly. While documented and intentional, this creates a process-global side effect that complicates testing and prevents per-tenant DB routing. | Acceptable workaround for upstream constraint. Document the pattern prominently. Consider proposing upstream support for programmatic configuration. |
| CC-08 | MEDIUM | infra-taskiq | XC-C3 | **Minimal public API.** Exports only pre-built singleton instances (`broker`, `result_backend`, `scheduler`). No factory functions, no settings class, no exception types. This is the thinnest `__init__.py` of any infra package. | Export factory functions and settings class (once created per CC-01). |
| CC-09 | MEDIUM | All except infra-eventsourcing | XC-E3 | **No transient vs. permanent error classification.** No package distinguishes retriable errors (connection timeout, Redis unavailable) from permanent errors (invalid SQL, missing table). This prevents intelligent retry logic at the application layer. | Define a `TransientError` / `PermanentError` taxonomy in `foundation-domain` or `foundation-application`. Have infrastructure packages wrap their exceptions accordingly. |
| CC-10 | LOW | infra-auth | XC-C6 | **`dev_bypass.py` reads `ENVIRONMENT` directly.** The production lockout check uses `os.environ.get("ENVIRONMENT")` instead of reading from `AuthSettings`. While defensible (the check must work even if settings fail to load), it creates a second path for environment detection. | Consider making the `ENVIRONMENT` check a class method on `AuthSettings` or a shared utility, so the detection logic is centralized. |
| CC-11 | LOW | infra-observability | XC-C1 | **Empty env_prefix by design.** `LoggingSettings` and `TracingSettings` use `env_prefix=""` to match OpenTelemetry and logging ecosystem conventions (`OTEL_SERVICE_NAME`, `LOG_LEVEL`). This is intentional but deviates from the `PREFIX_FIELD` pattern used by other packages. | Acceptable deviation. Add a comment in each settings class explaining why the prefix is empty (upstream convention alignment). |
| CC-12 | LOW | infra-eventsourcing | XC-C1 | **EventSourcingSettings has no env_prefix.** Uses raw `POSTGRES_*` names to match the upstream `eventsourcing` library's expected environment variables. This is an intentional compatibility choice, not an oversight. | Acceptable. Already documented via the `to_env_dict()` bridge pattern. |
| CC-13 | LOW | infra-persistence | XC-C2 | **No LifespanContribution.** The persistence package manages engine lifecycle via `dispose_engine()` but does not register a lifespan hook to call it automatically. Shutdown depends on the caller remembering to call `dispose_engine()`. | Consider adding a lifespan contribution that disposes engines and closes Redis on shutdown. |

## Analysis

### Convention Adherence Summary

The infrastructure packages exhibit two tiers of convention maturity:

**Tier 1 (High compliance):** `infra-fastapi`, `infra-auth`, `infra-observability`, `infra-eventsourcing`
These packages consistently follow the established patterns: `BaseSettings` with `env_prefix`, `__all__` exports, entry-point registrations for middleware/lifespan, and PEP 420 namespace compliance. Minor deviations (empty prefix in observability, `os.environ` bridge in eventsourcing) are intentional and documented.

**Tier 2 (Low compliance):** `infra-taskiq`
This package is a clear outlier. It lacks `BaseSettings`, has no entry-point registrations of any kind, no `LifespanContribution`, uses raw `os.getenv()`, and its module-level singletons are constructed at import time. It appears to be in early scaffold state and has not undergone the same convention alignment pass as its siblings.

### Cross-Cutting Patterns

1. **Settings convention is strong but not uniform.** Five of six infra packages use `BaseSettings`. The prefix convention varies: some use package-specific prefixes (`APP_`, `AUTH_`, `DATABASE_`, `CORS_`, `PROJECTION_`), while observability and eventsourcing intentionally omit prefixes to match upstream library conventions. This is a reasonable pragmatic choice but should be documented in a central conventions guide.

2. **`os.environ` usage has three distinct categories:**
   - **Bug:** `infra-fastapi` `error_handlers.py` reads `DEBUG` instead of `APP_DEBUG` (CC-04). This is a genuine bypass of the settings abstraction.
   - **Intentional bridge:** `infra-eventsourcing` writes to `os.environ` for upstream library compatibility (CC-07). Documented and necessary.
   - **Missing abstraction:** `infra-taskiq` uses `os.getenv` because no settings class exists (CC-01). This is a gap, not a design choice.

3. **Lifecycle management has a clear gap.** Packages with lifecycle requirements (`infra-observability`, `infra-eventsourcing`) register `LifespanContribution` hooks. `infra-taskiq` does not, despite requiring broker startup/shutdown. `infra-persistence` has a weaker case (engine disposal on shutdown) but would also benefit from a lifespan hook.

4. **PEP 420 compliance is perfect.** No intermediate `__init__.py` files exist in any infra package. All six packages correctly use implicit namespace packages.

5. **Deprecation handling is exemplary in the one package that needs it.** `infra-eventsourcing` provides `DeprecationWarning` with specific migration guidance for `ProjectionPoller` and `ProjectionRunner`. Tests verify the warnings fire correctly.

6. **Error taxonomy is absent.** No infrastructure package classifies errors as transient vs. permanent. The `infra-fastapi` error handlers map domain exceptions to HTTP status codes, but there is no shared mechanism for retry classification. This will become important as the framework matures toward production use.

7. **Async/sync model is consistently correct.** The split between sync (commands, projections, event store) and async (queries, HTTP middleware, OIDC calls) is clean and consistent across all packages. No blocking calls were found in async contexts within the infrastructure layer.

### Priority Recommendations

1. **Immediate (before next release):** Bring `infra-taskiq` up to Tier 1 compliance (CC-01, CC-02, CC-03). This is the single largest convention gap.
2. **Short-term:** Fix the `DEBUG` env var bypass in `infra-fastapi` (CC-04). This is a latent security risk.
3. **Medium-term:** Complete `infra-persistence` public API exports (CC-05) and consider adding a `LifespanContribution` (CC-13).
4. **Long-term:** Design a transient/permanent error taxonomy (CC-09) for intelligent retry behavior across the stack.
