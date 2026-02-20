# Architecture Audit: Entry-Point Auto-Discovery & App Factory

**Collector ID:** 1B
**Dimension:** 01-Architecture
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6

---

## Executive Summary

The entry-point auto-discovery system is well-designed and largely functional. The core `discover()` utility, contribution dataclasses, and app factory are all implemented with proper typing, error handling, and ordering semantics. Six of the seven PADR-122 entry-point groups have active declarations across packages. The main gaps are: (1) the `praecepta.subscriptions` group documented in PADR-122 has no implementations; (2) several packages that could contribute entry points do not; (3) the `discover()` return type uses `Any` for the value field, weakening type safety at the boundary; and (4) test coverage is solid for the happy path but lacks negative/failure-mode tests.

**Overall Maturity: 3.8 / 5.0 (Defined, approaching Managed)**

---

## Checklist Item Ratings

### 1. Discovery Module

**Rating: 5 / 5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The `discover()` function in `discovery.py` correctly wraps `importlib.metadata.entry_points()` and returns typed `DiscoveredContribution` instances.

**Findings:**

- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:11` -- Uses `from importlib.metadata import entry_points` (standard library, PEP 621 compliant).
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:51` -- Calls `entry_points(group=group)` with the `group` keyword filter, which is the correct Python 3.12+ API.
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:32-65` -- Generic `discover()` function supports any group string. It is not hardcoded to the 6 praecepta groups; any group can be discovered.
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:35` -- Supports `exclude_names` parameter for filtering specific entry points.
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:17-29` -- `DiscoveredContribution` is a frozen, slotted dataclass with `name`, `group`, and `value` fields.
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:64` -- Logs count of discovered contributions at INFO level per group.
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:60` -- Logs each successfully loaded entry point at DEBUG level.

**Assessment:** Fully implemented. Clean, generic, well-documented. The function is used by both the app factory (4 groups) and the projection lifespan (2 groups), covering all 6 active groups.

---

### 2. Contribution Types

**Rating: 4 / 5 -- Managed**
**Severity:** Medium | **Confidence:** High

Three contribution dataclasses are defined in `contributions.py`. They cover middleware, error handlers, and lifespan hooks. Routers, applications, and projections are handled as raw types (no contribution wrapper).

**Findings:**

- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:14-27` -- `MiddlewareContribution`: frozen, slotted dataclass with `middleware_class: type[Any]`, `priority: int = 500`, `kwargs: dict[str, Any]`. Well-documented priority bands (0-99 outermost, 100-199 security, 200-299 context, 300-399 policy).
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:30-41` -- `ErrorHandlerContribution`: frozen, slotted dataclass with `exception_class: type[BaseException]` and `handler: Any`. The handler type is `Any` rather than `Callable[[Request, Exception], Awaitable[Response]]`.
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:44-53` -- `LifespanContribution`: frozen, slotted dataclass with `hook: Any` and `priority: int = 500`. The hook type is `Any` rather than `Callable[[Any], AsyncContextManager[None]]`.
- No `RouterContribution`, `ApplicationContribution`, or `ProjectionContribution` dataclasses exist. Routers are passed as raw `APIRouter` instances; applications and projections as raw classes.

**Gap:** The `handler` field on `ErrorHandlerContribution` (line 40) and `hook` field on `LifespanContribution` (line 52) use `Any` instead of proper callable protocols. Comments document the intended type but the type system does not enforce it.

**Gap:** No contribution types for routers, applications, or projections. This is partially by design (PADR-122 lists these as raw types), but a `RouterContribution` with optional `prefix` and `tags` fields could enforce structure.

---

### 3. App Factory

**Rating: 5 / 5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The `create_app()` function in `app_factory.py` discovers and wires all four FastAPI-facing groups: routers, middleware, error handlers, and lifespan hooks.

**Findings:**

- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:30-33` -- Group constants defined: `GROUP_ROUTERS`, `GROUP_MIDDLEWARE`, `GROUP_ERROR_HANDLERS`, `GROUP_LIFESPAN`.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:36-156` -- `create_app()` accepts `settings`, `extra_*` lists for each contribution type, `exclude_groups`, and `exclude_names`. This provides full control over discovery behavior.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:68-78` -- Lifespan hooks: discovered, validated as `LifespanContribution` (or wrapped if bare async CM factory), appended to extras, then composed.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:103-124` -- Middleware: discovered, validated as `MiddlewareContribution`, sorted by priority ascending, registered in reverse (LIFO for Starlette).
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:126-144` -- Error handlers: discovered, validated as `ErrorHandlerContribution` or callable. Callables are invoked with `value(app)` to support the `register_exception_handlers` pattern.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:146-154` -- Routers: discovered and included directly via `app.include_router()`.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:93-101` -- CORS middleware always added via settings (not via entry points).

**Assessment:** Complete implementation. The factory wires all 4 groups it owns. The `praecepta.applications` and `praecepta.projections` groups are correctly delegated to `projection_lifespan.py` in infra-eventsourcing.

---

### 4. Middleware Ordering

**Rating: 5 / 5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Middleware contributions support explicit priority-based ordering with well-documented bands.

**Findings:**

- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:117` -- Sorted by `priority` ascending: `middleware_contribs.sort(key=lambda m: m.priority)`.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:118` -- Registered in reverse order (LIFO for Starlette's middleware stack semantics).
- Actual priority assignments across packages:
  - `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/request_id.py:156` -- `priority=10` (Outermost band: 0-99)
  - `packages/infra-observability/src/praecepta/infra/observability/middleware.py:95` -- `priority=20` (Outermost band: 0-99)
  - `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:300` -- `priority=100` (Security band: 100-199)
  - `packages/infra-auth/src/praecepta/infra/auth/middleware/jwt_auth.py:350` -- `priority=150` (Security band: 100-199)
  - `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/request_context.py:91` -- `priority=200` (Context band: 200-299)
  - `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/tenant_state.py:143` -- `priority=250` (Context band: 200-299)
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:93-101` -- Priority bands documented: Outermost (0-99), Security (100-199), Context (200-299), Policy (300-399), Default (500).

**Assessment:** All 6 declared middleware have non-conflicting priorities that respect the documented band conventions. The sort-then-reverse strategy correctly handles Starlette's LIFO middleware registration.

---

### 5. Lifespan Hooks

**Rating: 5 / 5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Lifespan contributions are properly composed using `AsyncExitStack` with priority ordering.

**Findings:**

- `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py:22-51` -- `compose_lifespan()` sorts hooks by priority ascending, creates an `AsyncExitStack`, and enters each hook's async context manager in order. Lower priority starts first and shuts down last (stack semantics).
- `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py:47-48` -- Each hook is called as `hook_contrib.hook(app)` and the result is entered via `stack.enter_async_context(ctx)`.
- Actual lifespan contributions:
  - `packages/infra-observability/src/praecepta/infra/observability/__init__.py:38-41` -- `priority=50` (logging/tracing setup)
  - `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/lifespan.py:109-112` -- `priority=100` (event store init)
  - `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:144-147` -- `priority=200` (projection pollers, after event store)
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:73-77` -- Bare async CM factories (not wrapped in `LifespanContribution`) are automatically wrapped with default priority 500.

**Assessment:** The lifespan composition is robust. Priority ordering is sensible: observability (50) starts first so logging is available, then event store (100), then projections (200) which depend on the store.

---

### 6. Projection Registration

**Rating: 4 / 5 -- Managed**
**Severity:** Low | **Confidence:** High

Projections are discovered via `praecepta.projections` entry points and registered into `ProjectionPoller` instances.

**Findings:**

- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:36-55` -- `_discover_projections()` uses `discover(GROUP_PROJECTIONS)` and validates each value is a `BaseProjection` subclass. Non-conforming entries are logged and skipped.
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:58-76` -- `_discover_applications()` discovers upstream application classes from `praecepta.applications` group.
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:117-130` -- Creates one `ProjectionPoller` per upstream application, each with all discovered projections. Pollers run background threads.
- `packages/domain-tenancy/pyproject.toml:25-27` -- Declares `tenant_config` and `tenant_list` projection entry points.
- `packages/domain-identity/pyproject.toml:26-28` -- Declares `user_profile` and `agent_api_key` projection entry points.

**Minor gap:** The projection discovery does not use `exclude_names`, so there is no way to exclude specific projections at the app factory level (unlike middleware, routers, and error handlers which respect `exclude_names` from the app factory). The projection lifespan is itself excludable as a lifespan hook, but individual projections within it are not.

---

### 7. Error Handler Registration

**Rating: 4 / 5 -- Managed**
**Severity:** Low | **Confidence:** High

Error handlers are discovered and registered via the `praecepta.error_handlers` entry point group.

**Findings:**

- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:126-144` -- Error handler discovery supports two patterns:
  1. `ErrorHandlerContribution` instances (registered individually)
  2. Callable `register(app)` functions (invoked directly)
- `packages/infra-fastapi/pyproject.toml:37` -- `rfc7807 = "praecepta.infra.fastapi.error_handlers:register_exception_handlers"` uses the callable pattern.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:535-612` -- `register_exception_handlers()` registers 10 exception handlers covering: `AuthenticationError` (401), `AuthorizationError` (403), `NotFoundError` (404), `ValidationError` (422), `ConflictError` (409), `FeatureDisabledError` (403), `ResourceLimitExceededError` (429), `DomainError` (400), `RequestValidationError` (422), and `Exception` (500).

**Observation:** Only `infra-fastapi` declares error handler entry points. This is appropriate since the RFC 7807 handlers cover all domain exception types defined in `foundation-domain`.

---

### 8. Router Mounting

**Rating: 3 / 5 -- Defined**
**Severity:** Medium | **Confidence:** High

Routers are discovered and mounted, but only a stub health router is currently declared.

**Findings:**

- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:146-154` -- Routers discovered from `praecepta.routers` group and included via `app.include_router(contrib.value)`.
- `packages/infra-fastapi/pyproject.toml:29` -- Only entry point: `_health_stub = "praecepta.infra.fastapi._health:router"`.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/_health.py:1-17` -- Stub health router at `/healthz` returning `{"status": "ok"}`.
- `packages/domain-tenancy/pyproject.toml` -- **No `praecepta.routers` entry point declared** despite being a domain package that would presumably expose tenant management APIs.
- `packages/domain-identity/pyproject.toml` -- **No `praecepta.routers` entry point declared** despite being a domain package that would expose identity/user APIs.

**Gap:** Domain packages (`domain-tenancy`, `domain-identity`) do not yet declare router entry points. No `APIRouter` usage found in either domain package. This means the auto-discovery system for routers is proven only with the stub health endpoint.

**Gap:** No `RouterContribution` wrapper means routers are mounted without any metadata (prefix, tags, dependencies). The `app.include_router(contrib.value)` call relies on the router itself having the correct prefix set.

---

### 9. Entry-Point Declarations

**Rating: 4 / 5 -- Managed**
**Severity:** Medium | **Confidence:** High

Six of 11 packages declare entry points. The remaining 5 are either foundation packages (which have nothing to contribute) or packages where declarations are not yet applicable.

**Findings -- Packages WITH entry-point declarations:**

| Package | Groups Declared | Reference |
|---------|----------------|-----------|
| `infra-fastapi` | `praecepta.routers`, `praecepta.middleware` (3), `praecepta.error_handlers` | `packages/infra-fastapi/pyproject.toml:28-37` |
| `infra-eventsourcing` | `praecepta.lifespan` (2) | `packages/infra-eventsourcing/pyproject.toml:27-29` |
| `infra-auth` | `praecepta.middleware` (2) | `packages/infra-auth/pyproject.toml:23-25` |
| `infra-observability` | `praecepta.middleware`, `praecepta.lifespan` | `packages/infra-observability/pyproject.toml:21-25` |
| `domain-tenancy` | `praecepta.applications`, `praecepta.projections` (2) | `packages/domain-tenancy/pyproject.toml:22-27` |
| `domain-identity` | `praecepta.applications` (2), `praecepta.projections` (2) | `packages/domain-identity/pyproject.toml:22-28` |

**Findings -- Packages WITHOUT entry-point declarations:**

| Package | Justification | Assessment |
|---------|--------------|------------|
| `foundation-domain` | Layer 0, pure primitives | Correct -- nothing to contribute |
| `foundation-application` | Layer 0, defines the discovery mechanism itself | Correct -- nothing to contribute |
| `infra-persistence` | Database infrastructure | Reasonable -- could contribute a lifespan hook for DB pool init, but may not be applicable yet |
| `infra-taskiq` | Background task processing | Reasonable -- could contribute a lifespan hook for broker startup |
| `integration-tenancy-identity` | Cross-domain integration | Expected to contribute `praecepta.subscriptions` per PADR-122 |

**Gap:** `infra-persistence` (`packages/infra-persistence/pyproject.toml`) and `infra-taskiq` (`packages/infra-taskiq/pyproject.toml`) have no entry points. These could contribute lifespan hooks for database pool and task broker initialization respectively.

**Gap:** `integration-tenancy-identity` has no entry points. PADR-122 documents a `praecepta.subscriptions` group (line 51: `"praecepta.subscriptions" -- Callable[[], None] (registration function)`) but no package declares entries in this group, and the app factory does not discover it.

---

### 10. Graceful Degradation

**Rating: 5 / 5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Missing or failing entry points are handled gracefully throughout the system.

**Findings:**

- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:57-62` -- Entry point load failures are caught by a broad `except Exception` block, logged via `logger.exception()`, and skipped. The contribution is simply not added to the results list.
- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:53-56` -- Excluded names are silently skipped with DEBUG logging.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:70-71` -- Group exclusion via `if GROUP_LIFESPAN not in _exclude_groups` prevents discovery for excluded groups.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:111-114` -- Non-`MiddlewareContribution` middleware entries generate a warning but do not crash.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:137-140` -- Non-conforming error handler entries generate a warning but do not crash.
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:96-99` -- No projections discovered: logs info and yields (no-op lifespan).
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:101-109` -- Projections found but no applications: logs warning and yields.
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:131-135` -- Poller start failure: stops already-started pollers and re-raises (fail-fast after cleanup).
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/lifespan.py:59-68` -- `EventSourcingSettings` load failure in env bridge: logs warning and returns without crashing.

**Assessment:** Excellent fail-soft behavior. Every boundary between discovery and consumption handles errors gracefully with appropriate logging.

---

### 11. Type Safety

**Rating: 3 / 5 -- Defined**
**Severity:** Medium | **Confidence:** High

Discovery functions return typed results, but the `value` field is `Any`, and contribution types use `Any` for callable fields.

**Findings:**

- `packages/foundation-application/src/praecepta/foundation/application/discovery.py:29` -- `DiscoveredContribution.value: Any` -- the loaded entry point value is untyped.
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:25` -- `MiddlewareContribution.middleware_class: type[Any]` -- middleware class is generic.
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:40` -- `ErrorHandlerContribution.handler: Any` -- handler callable is `Any` with only a comment noting the expected signature.
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:52` -- `LifespanContribution.hook: Any` -- hook callable is `Any` with only a comment noting the expected protocol.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:73` -- Runtime `isinstance(value, LifespanContribution)` check compensates for the untyped `value`.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:108` -- Runtime `isinstance(value, MiddlewareContribution)` check.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:132` -- Runtime `isinstance(value, ErrorHandlerContribution)` check.
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:46` -- Runtime `isinstance(value, type) and issubclass(value, BaseProjection)` check.
- `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py:24` -- `compose_lifespan()` return type is `object` rather than the actual async context manager factory type.

**Gap:** The `discover()` function could be generic (`discover[T]()`) to return typed `DiscoveredContribution[T]` instances. Currently, consumers must do runtime type checks on every `contrib.value`.

**Gap:** `ErrorHandlerContribution.handler` and `LifespanContribution.hook` should use `Protocol` types or `Callable` signatures rather than `Any`. The comments document intent but the type checker cannot verify conformance.

**Gap:** `compose_lifespan()` return type is `object` (line 24), should be the proper `Callable[[FastAPI], AsyncContextManager[None]]` or equivalent.

---

### 12. Test Coverage

**Rating: 4 / 5 -- Managed**
**Severity:** Low | **Confidence:** High

Good unit and integration test coverage for discovery and app factory happy paths. Some gaps in failure-mode testing.

**Findings:**

- `packages/foundation-application/tests/test_discovery.py:11-15` -- Tests `DiscoveredContribution` fields and immutability.
- `packages/foundation-application/tests/test_discovery.py:26-45` -- Tests `discover()` with empty group, real group, and exclusion.
- `packages/foundation-application/tests/test_contributions.py:14-75` -- Tests all 3 contribution dataclasses: default values, custom values, immutability.
- `packages/infra-fastapi/tests/test_app_factory.py:32-148` -- Tests `create_app()`:
  - Returns `FastAPI` instance (line 37)
  - Applies settings (line 42)
  - Default settings (line 51)
  - Extra routers mounted and reachable (line 57)
  - Extra error handlers registered and working (line 77)
  - Extra lifespan hooks execute (line 109)
  - Multiple lifespan hooks in priority order (line 126)
- `packages/infra-fastapi/tests/test_discovery_integration.py:12-49` -- Integration tests:
  - `discover()` finds health stub router (line 14)
  - `create_app()` auto-discovers `/healthz` endpoint (line 21)
  - Excluding routers group hides health endpoint (line 29)
  - Excluding specific name hides specific entry point (line 38)

**Gaps identified:**

- No test for a **failing entry point** (e.g., an entry point that raises `ImportError` on load) to verify graceful degradation.
- No test for **middleware priority ordering** via entry-point discovery (only tested via `extra_middleware`).
- No test for the **error handler callable pattern** (`register_exception_handlers` called with `value(app)`).
- No test for **projection discovery** end-to-end (would require integration environment).
- No test verifying that **non-conforming entry point values** (e.g., a string instead of `MiddlewareContribution`) are logged and skipped.

---

### 13. PADR-122 Alignment

**Rating: 4 / 5 -- Managed**
**Severity:** Medium | **Confidence:** High

Implementation closely follows PADR-122 with one notable omission.

**Findings -- Aligned:**

- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:38-39` -- Decision: "use Python's standard entry points mechanism." Implementation: `importlib.metadata.entry_points()` at `discovery.py:11`.
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:43-51` -- 7 entry point groups documented. 6 of 7 are implemented (all except `praecepta.subscriptions`).
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:66-74` -- `discover()` utility described. Matches `discovery.py:32-65`.
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:80-91` -- `MiddlewareContribution` and `LifespanContribution` dataclasses described. Match `contributions.py:14-53`.
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:93-101` -- Priority bands documented. All actual priorities conform to documented bands.
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:105-110` -- Consumer example `create_app(title="My App")` with zero manual wiring. Implementation matches at `app_factory.py:36-156`.
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:135` -- Mitigation: "create_app() logs every discovered contribution at INFO level." Confirmed at `discovery.py:64` and `app_factory.py:120-123`.

**Findings -- Gaps:**

- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:51` -- `praecepta.subscriptions` group documented as `Callable[[], None] (registration function)` consumed by "Integration packages." **Not implemented.** No package declares entries in this group. No consumer code exists.
- `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:43-44` -- PADR-122 shows `praecepta.routers` value type as `FastAPI APIRouter`. Domain packages (`domain-tenancy`, `domain-identity`) do not yet declare router entry points despite being the primary expected contributors.

---

## Summary Statistics

| # | Checklist Item | Rating | Severity | Confidence |
|---|---------------|--------|----------|------------|
| 1 | Discovery Module | 5 | Info | High |
| 2 | Contribution Types | 4 | Medium | High |
| 3 | App Factory | 5 | Info | High |
| 4 | Middleware Ordering | 5 | Info | High |
| 5 | Lifespan Hooks | 5 | Info | High |
| 6 | Projection Registration | 4 | Low | High |
| 7 | Error Handler Registration | 4 | Low | High |
| 8 | Router Mounting | 3 | Medium | High |
| 9 | Entry-Point Declarations | 4 | Medium | High |
| 10 | Graceful Degradation | 5 | Info | High |
| 11 | Type Safety | 3 | Medium | High |
| 12 | Test Coverage | 4 | Low | High |
| 13 | PADR-122 Alignment | 4 | Medium | High |

**Average Rating: 4.23 / 5.0**
**Items at Maturity 5 (Optimizing):** 5
**Items at Maturity 4 (Managed):** 6
**Items at Maturity 3 (Defined):** 2
**Items at Maturity 2 (Initial):** 0
**Items at Maturity 1 (Not Implemented):** 0

---

## Entry-Point Coverage Matrix

| Group | Declared By | Consumed By | Entry Points |
|-------|------------|-------------|--------------|
| `praecepta.routers` | infra-fastapi | app_factory.py | `_health_stub` |
| `praecepta.middleware` | infra-fastapi, infra-auth, infra-observability | app_factory.py | `request_id`, `request_context`, `tenant_state`, `api_key_auth`, `jwt_auth`, `trace_context` |
| `praecepta.error_handlers` | infra-fastapi | app_factory.py | `rfc7807` |
| `praecepta.lifespan` | infra-eventsourcing, infra-observability | app_factory.py | `event_store`, `projection_runner`, `observability` |
| `praecepta.applications` | domain-tenancy, domain-identity | projection_lifespan.py | `tenancy`, `identity_user`, `identity_agent` |
| `praecepta.projections` | domain-tenancy, domain-identity | projection_lifespan.py | `tenant_config`, `tenant_list`, `user_profile`, `agent_api_key` |
| `praecepta.subscriptions` | (none) | (none) | (none) |

**Total entry points declared: 20 across 6 active groups.**

---

## Middleware Priority Map

| Priority | Middleware | Package | Band |
|----------|-----------|---------|------|
| 10 | `RequestIdMiddleware` | infra-fastapi | Outermost (0-99) |
| 20 | `TraceContextMiddleware` | infra-observability | Outermost (0-99) |
| 100 | `APIKeyAuthMiddleware` | infra-auth | Security (100-199) |
| 150 | `JWTAuthMiddleware` | infra-auth | Security (100-199) |
| 200 | `RequestContextMiddleware` | infra-fastapi | Context (200-299) |
| 250 | `TenantStateMiddleware` | infra-fastapi | Context (200-299) |

No priority collisions detected. All bands correctly applied.

---

## Lifespan Priority Map

| Priority | Hook | Package |
|----------|------|---------|
| 50 | `_observability_lifespan` | infra-observability |
| 100 | `event_store_lifespan` | infra-eventsourcing |
| 200 | `projection_runner_lifespan` | infra-eventsourcing |

Ordering ensures: logging configured first, then event store, then projections (which depend on the store).

---

## Additional Observations

### Observation 1: Dual Error Handler Pattern

The `praecepta.error_handlers` group supports two patterns: `ErrorHandlerContribution` dataclasses and raw callable `register(app)` functions (`app_factory.py:132-140`). The current sole consumer (`rfc7807`) uses the callable pattern. This dual approach is pragmatic but could be confusing -- the callable pattern bypasses the contribution dataclass entirely.

**File:** `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:129-140`

### Observation 2: CORS Not Auto-Discovered

CORS middleware is always added via settings (`app_factory.py:94-101`), not via the entry-point system. This is an intentional design choice -- CORS is a cross-cutting concern configured per deployment, not per package. This is appropriate.

**File:** `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:93-101`

### Observation 3: Settings-Based Exclusion

`AppSettings` at `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:67-68` defines `exclude_groups` and `exclude_entry_points` fields that can be configured via environment variables (`APP_EXCLUDE_GROUPS`, `APP_EXCLUDE_ENTRY_POINTS`). This provides runtime control over discovery without code changes.

### Observation 4: Pre-Alpha Package Status

Several packages that would be expected to contribute entry points in a mature system (e.g., `infra-persistence` for DB lifecycle, `infra-taskiq` for broker lifecycle, domain packages for routers) have not yet reached that stage. The health stub router comment (`_health.py:5`: "will be replaced by a full health endpoint in Step 6") confirms the scaffolding-first approach.

### Observation 5: Projection Poller Architecture

The projection discovery in `projection_lifespan.py` creates one `ProjectionPoller` per upstream application, each with ALL discovered projections (`projection_lifespan.py:119-125`). This means every projection processes events from every application. This may be intentional (projections can filter events they care about) but could become a performance concern as the number of applications and projections grows.

**File:** `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:117-130`
