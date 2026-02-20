# FastAPI Layer & Event Sourcing -- Convention & Standards

**Collector ID:** 3B
**Dimension:** Convention & Standards
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. RFC 7807 Error Handlers

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The error handler implementation is exemplary and fully conforms to RFC 7807 Problem Details for HTTP APIs. Every handler returns `application/problem+json` media type via the `PROBLEM_MEDIA_TYPE` constant (`error_handlers.py:44`). The `ProblemDetail` Pydantic model (`error_handlers.py:47-99`) implements all five standard RFC 7807 fields (`type`, `title`, `status`, `detail`, `instance`) plus three well-chosen extension fields (`error_code`, `context`, `correlation_id`).

All domain exceptions from `praecepta.foundation.domain.exceptions` are mapped to appropriate HTTP status codes. The `InvalidStateTransitionError` is handled implicitly because it inherits from `ConflictError` (`exceptions.py:201`), which is registered. The registration order is correct -- specific exceptions before base class fallback (`error_handlers.py:564-612`).

Security considerations are addressed through:
- Sensitive key filtering in context sanitization (`error_handlers.py:189-192`)
- Regex-based redaction of connection strings, passwords, tokens, and API keys (`error_handlers.py:103-124`)
- Production vs debug mode toggle for 500 error detail exposure (`error_handlers.py:513-531`)
- Correlation ID included only on 5xx responses for support ticket tracing

**Findings:**

| Exception | HTTP Status | Handler | Content-Type |
|-----------|------------|---------|--------------|
| `NotFoundError` | 404 | `not_found_handler` :223 | `application/problem+json` |
| `ValidationError` | 422 | `validation_error_handler` :245 | `application/problem+json` |
| `ConflictError` | 409 | `conflict_error_handler` :270 | `application/problem+json` |
| `FeatureDisabledError` | 403 | `feature_disabled_handler` :295 | `application/problem+json` |
| `ResourceLimitExceededError` | 429 | `resource_limit_handler` :323 | `application/problem+json` |
| `AuthenticationError` | 401 | `authentication_error_handler` :359 | `application/problem+json` |
| `AuthorizationError` | 403 | `authorization_error_handler` :388 | `application/problem+json` |
| `DomainError` (base) | 400 | `domain_error_handler` :413 | `application/problem+json` |
| `RequestValidationError` | 422 | `request_validation_handler` :441 | `application/problem+json` |
| `Exception` (catch-all) | 500 | `unhandled_exception_handler` :480 | `application/problem+json` |

Additional compliance: 401 responses include `WWW-Authenticate` header per RFC 6750 (`error_handlers.py:384`), and 429 responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` headers (`error_handlers.py:353-355`). Tests verify all mappings comprehensively in `packages/infra-fastapi/tests/test_error_handlers.py`.

Note: PADR-103 is referenced in the task but does not exist as a standalone document in the repo. The decisions page (`docs/docs/decisions.md`) lists only a subset. The implementation is nonetheless complete and well-documented inline.

---

## 2. Middleware Contribution Pattern

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The middleware contribution pattern is consistently implemented and well-documented. `MiddlewareContribution` is defined in the foundation layer (`packages/foundation-application/src/praecepta/foundation/application/contributions.py:14-27`) with three fields: `middleware_class`, `priority` (with documented bands), and `kwargs`.

All three built-in middleware components follow the pattern identically:

**Findings:**

| Middleware | Priority | Band | File:Line |
|-----------|----------|------|-----------|
| `RequestIdMiddleware` | 10 | Outermost (0-99) | `middleware/request_id.py:154-157` |
| `RequestContextMiddleware` | 200 | Context (200-299) | `middleware/request_context.py:89-92` |
| `TenantStateMiddleware` | 250 | Context (200-299) | `middleware/tenant_state.py:141-144` |

Each middleware module exports a module-level `contribution` variable of type `MiddlewareContribution`, registered as entry points in `packages/infra-fastapi/pyproject.toml:32-34`. The `app_factory.py:116-124` sorts contributions by priority ascending and adds them in reverse order (LIFO semantics for Starlette), which is correct.

The priority band system is documented in `docs/docs/architecture/entry-points.md:69-79` with five bands: Outermost (0-99), Security (100-199), Context (200-299), Policy (300-399), Default (500). All existing middleware correctly uses the specified bands.

Contributions that do not conform to `MiddlewareContribution` are logged as warnings (`app_factory.py:111-113`), providing fail-soft behavior.

---

## 3. FastAPI Dependency Injection

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Two FastAPI dependency factories are implemented as well-documented, typed, reusable patterns:

1. **`require_feature(feature_key)`** (`dependencies/feature_flags.py:62-105`): Creates a dependency that gates endpoint access on a feature flag. Uses `FeatureChecker` protocol (`feature_flags.py:31-44`) for type-safe abstraction. Correctly reads tenant context via `get_current_tenant_id()` and retrieves the checker from `request.app.state`.

2. **`check_resource_limit(resource)`** (`dependencies/resource_limits.py:57-145`): Creates a dependency that enforces resource limits. Returns a `ResourceLimitResult` dataclass with `limit` and `remaining` fields for response header population.

Both factories include important implementation notes about avoiding `from __future__ import annotations` due to FastAPI's runtime annotation evaluation requirements (`feature_flags.py:18-21`, `resource_limits.py:31-34`). Both set `__qualname__` for introspection (`feature_flags.py:103`, `resource_limits.py:142`).

**Findings:**

- The `_get_feature_checker` function (`feature_flags.py:47-59`) accesses `request.app.state.feature_checker` without validation that the attribute exists. If lifespan setup fails or the attribute is not set, this raises an unclear `AttributeError` rather than a descriptive error.
- The `check_resource_limit` factory's `usage_counter` and `limit_resolver` parameters default to `None` with fallback behavior (0 usage, INT_MAX limit). This makes the dependency effectively a no-op when not configured, which could mask misconfiguration.
- No `Depends()` examples showing composition of multiple dependencies in a single endpoint are provided in the codebase (only in docstrings).

---

## 4. Event Store Factory

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The `EventStoreFactory` class (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/event_store.py:57-246`) provides a clean abstraction over the eventsourcing library's infrastructure. Three construction paths are available:

1. `from_env()` (`event_store.py:98-140`): Attempts `DATABASE_URL` parsing first, falls back to individual `POSTGRES_*` variables.
2. `from_database_url()` (`event_store.py:142-174`): Explicit connection string with overrides.
3. Direct constructor with `EventSourcingSettings` instance.

The `postgres_parser.py` module provides robust URL parsing with a custom `DatabaseURLParseError` exception and a safe variant (`parse_database_url_safe`). Configuration is type-safe via `EventSourcingSettings` Pydantic model (`settings.py:17-202`) with comprehensive validation including port range, pool size bounds, and a production warning for `CREATE_TABLE=true`.

The singleton pattern via `@lru_cache(maxsize=1)` on `get_event_store()` (`event_store.py:222-245`) is clean and lazy. The architecture documentation clearly explains the two-path infrastructure model (`event_store.py:8-37`).

**Findings:**

- The `lru_cache`-based singleton on `get_event_store()` cannot be easily cleared for testing or reconfiguration. A dedicated singleton pattern with explicit reset capability would be more testable.
- `from_env()` at line 139 uses `EventSourcingSettings()` with `# type: ignore[call-arg]` because required fields (`postgres_dbname`, `postgres_user`, `postgres_password`) may not be present in environment. This defers the error to Pydantic validation, which is acceptable but not self-documenting.
- The `close()` method (`event_store.py:209-218`) does not clear the `lru_cache`, so after closing, `get_event_store()` returns the same (closed) factory instance.

---

## 5. Projection Runner/Poller

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The projection infrastructure demonstrates clear architectural evolution. The legacy `ProjectionRunner` (`projections/runner.py`) is properly deprecated with a `DeprecationWarning` (`runner.py:100-105`) directing users to `ProjectionPoller`. The replacement `ProjectionPoller` (`projections/poller.py`) implements a polling-based approach that correctly handles cross-process event consumption.

The `ProjectionPoller` implementation:
- Uses a background `daemon=True` thread (`poller.py:137-142`) for non-blocking poll cycles
- Catches all exceptions in the poll loop to prevent crash-on-error (`poller.py:157-158`)
- Checks `_stop_event` between projections for responsive shutdown (`poller.py:153-154`)
- Supports graceful shutdown with configurable timeout (`poller.py:173-179`) and logs warnings if the thread does not stop within the timeout
- Provides context manager protocol for clean lifecycle management (`poller.py:214-226`)

The `ProjectionPollingSettings` (`settings.py:205-237`) enforces sane bounds: `poll_interval` between 0.1-60s, `poll_timeout` between 1-120s, and a `poll_enabled` master switch.

Auto-discovery via `projection_lifespan_contribution` (`projection_lifespan.py:144-147`) at priority 200 (after event store at 100) correctly handles the dependency ordering. The lifespan hook discovers projections and applications from entry points, creates one poller per upstream application, and handles partial startup failures by stopping already-started pollers (`projection_lifespan.py:131-135`).

**Findings:**

| Aspect | Implementation | File:Line |
|--------|---------------|-----------|
| Deprecation of old runner | `DeprecationWarning` | `runner.py:100-105` |
| Error handling in poll loop | `except Exception` + `logger.exception` | `poller.py:157-158` |
| Graceful shutdown | `_stop_event.set()` + `join(timeout=...)` | `poller.py:171-179` |
| Inter-projection stop check | `if self._stop_event.is_set(): break` | `poller.py:153-154` |
| Lifespan priority ordering | 200 (after event store 100) | `projection_lifespan.py:147` |
| Auto-discovery validation | `issubclass(value, BaseProjection)` check | `projection_lifespan.py:46` |
| Tests | 10 test cases covering lifecycle, poll loop, error recovery | `tests/test_projection_poller.py` |

PADR-109 reference is addressed: projections use synchronous `def` for sequential event processing, consistent with the sync-first strategy documented in `docs/docs/decisions.md:74-81`.

---

## 6. Projection Rebuilder

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

The `ProjectionRebuilder` class (`projections/rebuilder.py:65-177`) implements the core rebuild workflow: clear read model, then reset tracking position. The design is documented with clear workflow steps, use cases, and warnings about destructive behavior.

The `clear_read_model()` abstract method on `BaseProjection` (`projections/base.py:131-151`) ensures all projections implement the required contract. The rebuilder gracefully degrades when the recorder lacks `delete_tracking_record` support (`rebuilder.py:168-176`).

However, several gaps exist:

**Findings:**

- No CLI command or admin endpoint exists for triggering rebuilds. The rebuilder is a Python API only, requiring custom integration code. The docstring mentions "future implementation notes" for blue-green rebuilds (`rebuilder.py:45-46`) but these are absent.
- No tests exist for `ProjectionRebuilder` -- there is no `test_rebuilder.py` in `packages/infra-eventsourcing/tests/`.
- The `upstream_app` parameter is typed as `Any` (`rebuilder.py:96`), losing type safety. A protocol or base class constraint would be better.
- The rebuilder does not coordinate with the `ProjectionPoller` for stop/start lifecycle. The docstring states "caller responsibility" (`rebuilder.py:37-38, 84-85`), which leaves the operational workflow undocumented.
- The `ProjectionRebuilder` is not exported from the package `__init__.py` (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/__init__.py`), though it is exported from the `projections/__init__.py` subpackage (`projections/__init__.py:9`).
- No documented guide for performing a rebuild operation exists. The `docs/docs/guides/build-projection.md` mentions `clear_read_model` but does not cover the `ProjectionRebuilder` class or the operational steps for a rebuild.

---

## 7. Config Cache Pattern

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The `HybridConfigCache` class (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/config_cache.py:17-138`) implements a well-designed two-level cache:

- **L1**: In-memory via `cachetools.TTLCache` with configurable maxsize (default 10,000) and TTL (default 5 minutes)
- **L2**: Redis with configurable TTL (default 1 hour), optional (disabled when `redis_client=None`)

Key features:
- Cache key format with tenant isolation: `tenant:{tenant_id}:config:{config_key}` (`config_cache.py:43-45`)
- L2-to-L1 promotion on L2 hit (`config_cache.py:72`)
- Explicit invalidation for single keys (`config_cache.py:98-112`) and bulk tenant invalidation via Redis SCAN (`config_cache.py:114-138`)
- All operations are async-compatible (`config_cache.py:47, 77, 98, 114`)

The cache integrates with `TenantConfigService` (`config_service.py:117-125`) via the `ConfigCache` protocol (`config_service.py:48-69`), following ports-and-adapters principles.

**Findings:**

- The `ConfigCache` protocol in `config_service.py:48-69` defines synchronous `get`/`set`/`delete` methods, but `HybridConfigCache` implements async `get`/`set`/`invalidate` methods. These protocols are not directly compatible -- the `TenantConfigService` uses the sync protocol while `HybridConfigCache` provides async. This is a structural mismatch that would cause runtime errors if directly connected.
- No explicit cache warming or preloading mechanism exists.
- The L1 TTL (5 minutes) and L2 TTL (1 hour) are reasonable defaults but the docstring (`config_cache.py:6`) mentions "Event-driven invalidation on config update events" which is not implemented in the cache itself -- it relies on callers to invoke `invalidate()`.
- The SCAN-based bulk invalidation (`config_cache.py:133-138`) could be slow for tenants with many config keys, though the `count=100` parameter limits per-round results.

---

## 8. Foundation Application Context

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The request context system is cleanly implemented across two layers:

**Foundation layer** (`packages/foundation-application/src/praecepta/foundation/application/context.py`):
- `RequestContext` frozen dataclass with `tenant_id`, `user_id`, `correlation_id` (`context.py:43-55`)
- `ContextVar`-based propagation with proper token-based cleanup (`context.py:59`)
- Clear accessor functions: `get_current_tenant_id()`, `get_current_user_id()`, `get_current_correlation_id()` (`context.py:87-120`)
- `NoRequestContextError` with descriptive message (`context.py:62-69`)
- Separate principal context (`context.py:167`) decoupled from `RequestContext` to avoid modifying the frozen dataclass

**FastAPI layer** (`packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/request_context.py`):
- `RequestContextMiddleware` populates context from HTTP headers (`request_context.py:46-85`)
- Proper cleanup in `finally` block via token reset (`request_context.py:83-85`)
- Correlation ID propagated back to response headers (`request_context.py:81`)
- Header constants defined as module-level constants (`request_context.py:29-31`)
- Nil UUID fallback for missing user ID (`request_context.py:67-69`)

The two-layer separation (foundation defines the context, infra populates it from HTTP) correctly follows the hexagonal architecture pattern. The dual context system (request + principal) allows independent lifecycle management by different middleware.

**Findings:**

| Component | Layer | File:Line | Status |
|-----------|-------|-----------|--------|
| `RequestContext` dataclass | Foundation | `context.py:43-55` | Frozen, slotted |
| `ContextVar` propagation | Foundation | `context.py:59` | Token-based reset |
| `NoRequestContextError` | Foundation | `context.py:62-69` | Descriptive message |
| `set_request_context()` | Foundation | `context.py:123-146` | Returns reset token |
| `clear_request_context()` | Foundation | `context.py:149-157` | Token-based reset |
| `RequestContextMiddleware` | Infra | `request_context.py:34-85` | Populates from headers |
| Principal context (separate) | Foundation | `context.py:167-221` | Independent lifecycle |

---

## 9. Config Service Pattern

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The `TenantConfigService` (`packages/foundation-application/src/praecepta/foundation/application/config_service.py:107-358`) implements a well-structured configuration resolution chain: cache -> tenant override (projection) -> system defaults.

Multi-tenancy support is built into every operation via `tenant_id` parameter. The service supports:
- Single config resolution (`get_config`, `config_service.py:149-196`)
- Bulk config resolution (`get_all_config`, `config_service.py:198-239`)
- Feature flag evaluation with boolean and percentage-based rollouts (`is_feature_enabled`, `config_service.py:241-302`)
- Resource limit resolution (`resolve_limit`, `config_service.py:304-330`)
- Policy resolution with three-level chain (`resolve_policy`, `config_service.py:332-358`)

The feature flag percentage evaluation uses deterministic SHA256 hashing (`config_service.py:72-104`) with documented monotonicity guarantees and feature independence. The fail-closed default (disabled on missing config) is the correct security posture (`config_service.py:264-265`).

**Findings:**

- The `ConfigRepository` protocol (`config_service.py:22-45`) includes a `upsert` method, mixing read and write concerns. A read-only query protocol would better enforce CQRS separation at the type level.
- The `set_config` method (`config_service.py:126-147`) performs write-through to the repository, which is a command-side operation on a service primarily designed for queries. This muddies the CQRS boundary.
- The `ConfigCache` protocol (`config_service.py:48-69`) is synchronous, while the actual `HybridConfigCache` implementation is async. This mismatch means they cannot be directly composed without an adapter.
- The `resolve_policy` method (`config_service.py:332-358`) uses a lazy import of `PolicyBindingService`, which works but obscures the dependency graph.

---

## 10. Resource Limits

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Resource limit enforcement is implemented at two levels:

**Foundation layer** (`packages/foundation-application/src/praecepta/foundation/application/resource_limits.py`):
- `ResourceLimitService` with injectable `resource_key_map` for mapping resource types to config keys (`resource_limits.py:39-128`)
- `ResourceLimitResult` frozen dataclass with `limit` and `remaining` (`resource_limits.py:25-36`)
- Resolution chain: tenant config -> system default -> INT_MAX (`resource_limits.py:89-95`)
- Raises `ResourceLimitExceededError` which maps to HTTP 429 via error handlers

**FastAPI layer** (`packages/infra-fastapi/src/praecepta/infra/fastapi/dependencies/resource_limits.py`):
- `check_resource_limit(resource)` dependency factory (`resource_limits.py:57-145`)
- Injectable `usage_counter` and `limit_resolver` callables
- Returns `ResourceLimitResult` for response header population
- Logging at warning (exceeded) and debug (checked) levels

The error handler adds proper rate-limiting headers (`error_handlers.py:353-355`): `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`.

**Findings:**

- The `Retry-After` header is hardcoded to 3600 seconds (`error_handlers.py:355`). This should ideally be configurable or calculated based on the resource type and limit reset window.
- There are two separate `ResourceLimitResult` classes: one in `foundation/application/resource_limits.py:25` and one in `infra/fastapi/dependencies/resource_limits.py:44`. They have identical structure but are different types. The foundation layer version includes an `increment` parameter in `remaining` calculation, while the FastAPI version always assumes increment=1. This duplication creates confusion.
- No payload size limits are enforced at the middleware level. Only logical resource counts (e.g., number of memory blocks) are checked -- there is no maximum request body size configuration in `AppSettings`.
- Rate limiting (request-per-second throttling) is not implemented. Only resource count limits (quota enforcement) exist.

---

## 11. Router Mount Convention

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** Medium

Currently only one router exists in the codebase: the health stub router at `packages/infra-fastapi/src/praecepta/infra/fastapi/_health.py`. It uses `APIRouter(tags=["health"])` and defines `/healthz` as a GET endpoint. This is registered via entry points in `pyproject.toml:29`.

The auto-discovery mechanism in `app_factory.py:146-154` simply calls `app.include_router(router)` without prefix or tag enforcement. Routers are included in discovery order with no sorting.

**Findings:**

- No URL prefix convention is documented or enforced. The `app_factory.py:153` calls `include_router(router)` directly without requiring a prefix. Domain packages (tenancy, identity) do not currently provide routers, so no examples of prefix conventions exist.
- No tag convention is enforced. The health router uses `tags=["health"]` but there is no documented tag taxonomy or requirement.
- The `_health.py` router is prefixed with underscore (`_health.py:1-17`), suggesting it is internal/temporary, and its docstring confirms it is a stub (`_health.py:3-5`).
- The `docs/docs/guides/add-api-endpoint.md` and `docs/docs/architecture/entry-points.md` document the entry-point registration pattern but do not specify URL prefix conventions, versioning patterns, or tag requirements.
- No API versioning strategy (e.g., `/api/v1/...`) is documented or implemented.
- Router-level dependencies (e.g., authentication requirements per-router) are not demonstrated or documented.

---

## 12. Development Constitution Article III

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** Medium

The Development Constitution is referenced in the CLAUDE.md and the task description but does not exist as a standalone document in the repository (`docs/docs/architecture/development-constitution.md` was not found). The quality standards are instead distributed across multiple documents:

- `CLAUDE.md`: Code style rules (Python 3.12+, line length 100, Ruff, mypy strict, namespace packages)
- `docs/docs/decisions.md`: Architectural decision records (PADRs)
- `docs/docs/architecture/entry-points.md`: Entry-point patterns
- `docs/docs/guides/`: Implementation guides

Evaluating the FastAPI and eventsourcing implementations against the implicit quality standards:

**Findings:**

| Standard | Status | Evidence |
|----------|--------|----------|
| Type safety (mypy strict) | Compliant | `type: ignore[arg-type]` used only where Starlette types are too strict (`error_handlers.py:571-612`), with explanatory comments |
| Docstrings | Excellent | Every public class, method, and function has Google-style docstrings with Args/Returns/Raises/Example sections |
| Error handling | Excellent | Comprehensive exception hierarchy with structured context; fail-soft for discovery, fail-closed for security |
| Layering | Compliant | Foundation types (`MiddlewareContribution`, `RequestContext`) have no infra dependencies; infra imports foundation |
| Testing | Strong | `test_error_handlers.py` (39 tests), `test_projection_poller.py` (11 tests), dedicated test files per module |
| PEP 420 namespaces | Compliant | No `__init__.py` in intermediate namespace directories |
| Security | Good | Sensitive data redaction, context sanitization, debug-mode toggle for error detail |
| Configuration | Good | Pydantic Settings with validation, env prefix conventions, `.env` file support |

Gaps relative to a formalized constitution:
- The Development Constitution document itself does not exist in the repository. Quality standards are implicit rather than codified.
- No formalized code review checklist or PR template references these standards.
- Some `type: ignore` comments lack issue tracker references or suppression justification beyond inline comments.
- The PADR numbering (103, 105, 109) referenced in the audit task does not correspond to standalone decision documents -- PADR-109 content appears inline in `decisions.md`, but PADR-103 and PADR-105 are not documented anywhere in the repo.

---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | RFC 7807 Error Handlers | 5/5 | Info |
| 2 | Middleware Contribution Pattern | 5/5 | Info |
| 3 | FastAPI Dependency Injection | 4/5 | Low |
| 4 | Event Store Factory | 4/5 | Low |
| 5 | Projection Runner/Poller | 5/5 | Info |
| 6 | Projection Rebuilder | 3/5 | Medium |
| 7 | Config Cache Pattern | 4/5 | Low |
| 8 | Foundation Application Context | 5/5 | Info |
| 9 | Config Service Pattern | 4/5 | Low |
| 10 | Resource Limits | 4/5 | Low |
| 11 | Router Mount Convention | 3/5 | Medium |
| 12 | Development Constitution Article III | 3/5 | Medium |

**Overall Average: 4.08/5**

**Key Strengths:**
- RFC 7807 error handling is production-grade with security-conscious sanitization
- Middleware contribution pattern is consistent, well-documented, and tooling-enforced via entry points
- Request context propagation cleanly separates foundation and infrastructure concerns
- Projection polling correctly handles cross-process event consumption with proper error recovery

**Priority Improvements:**
1. Add tests and operational documentation for `ProjectionRebuilder` (Item 6)
2. Establish and document router mount conventions (URL prefixes, tags, versioning) before domain packages add routers (Item 11)
3. Create the Development Constitution as a formal document, codifying the implicit quality standards currently scattered across CLAUDE.md and guide documents (Item 12)
4. Resolve the sync/async protocol mismatch between `ConfigCache` and `HybridConfigCache` (Item 7)
