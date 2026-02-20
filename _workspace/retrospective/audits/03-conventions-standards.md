# Dimension 3: Convention & Standards

**RAG Status:** AMBER
**Average Maturity:** 3.96/5
**Date:** 2026-02-18

## Executive Summary

The Praecepta monorepo demonstrates strong convention adherence across its infrastructure and application layers, with 18 of 24 audited areas rated 4/5 or above (75%). The codebase excels in security-sensitive areas: RFC 7807 error handling is production-grade with comprehensive sanitization, the middleware contribution pattern is consistently applied with documented priority bands, request context propagation cleanly separates foundation and infrastructure concerns, and the development authentication bypass has multiple layers of production safety. These areas represent genuine engineering maturity rather than mere scaffolding.

However, one High-severity finding prevents a GREEN rating: the TaskIQ integration package (rated 2/5) bypasses every convention established by the other infrastructure packages -- no Pydantic settings, no retry policies, no lifespan integration, and module-level instantiation with hardcoded defaults. Additionally, seven Medium-severity findings span missing repository/unit-of-work abstractions in the persistence layer, untested projection rebuild infrastructure, undocumented router mount conventions, and the absence of the referenced Development Constitution document. The combined average maturity of 3.96/5 falls just below the 4.0 threshold for GREEN status.

Cross-cutting analysis reveals two systemic themes: (1) the codebase has strong implicit conventions that are enforced by tooling (import-linter, entry points, Pydantic validation) but lacks the formal documentation (Development Constitution, PADRs) needed to communicate those conventions to new contributors; and (2) a sync/async protocol mismatch pattern appears in multiple locations where foundation-layer protocols define synchronous interfaces but infrastructure implementations provide async variants.

## Consolidated Checklist

| # | Area | Item | Rating | Severity | Source |
|---|------|------|--------|----------|--------|
| 1 | Settings | Pydantic Settings Pattern (BaseSettings, SettingsConfigDict, env_prefix, lru_cache singletons) | 4/5 | Medium | 3A |
| 2 | Middleware | Auth Middleware Sequencing (priority bands, LIFO ordering, first-match-wins) | 5/5 | Low | 3A |
| 3 | Auth | JWT/JWKS Implementation (RS256, required claims, PyJWKClient caching, RFC 6750) | 4/5 | Low | 3A |
| 4 | Auth | Dev Bypass Safety (production lockout, explicit opt-in, ERROR logging) | 5/5 | Info | 3A |
| 5 | Persistence | Persistence Patterns (session factory, RLS helpers, tenant context) | 3/5 | Medium | 3A |
| 6 | Observability | Observability Integration (structlog, OTel tracing, trace-log correlation) | 4/5 | Low | 3A |
| 7 | TaskIQ | TaskIQ Configuration (broker, result backend, scheduler) | 2/5 | High | 3A |
| 8 | Event Sourcing | Event Sourcing Settings (Pydantic model, env bridging, projection polling settings) | 4/5 | Low | 3A |
| 9 | Error Handling | Error Handling in Adapters (domain exception to HTTP translation, dual error paths) | 4/5 | Low | 3A |
| 10 | Config | Configuration Validation (startup validation, bounds, custom validators) | 4/5 | Medium | 3A |
| 11 | Governance | Development Constitution Compliance (4-layer hierarchy, PEP 420, import-linter) | 3/5 | Medium | 3A |
| 12 | DI | Dependency Injection Patterns (FastAPI Depends, constructor injection, entry points) | 4/5 | Low | 3A |
| 13 | Error Handling | RFC 7807 Error Handlers (ProblemDetail model, security sanitization, handler registration) | 5/5 | Info | 3B |
| 14 | Middleware | Middleware Contribution Pattern (MiddlewareContribution, priority bands, entry-point discovery) | 5/5 | Info | 3B |
| 15 | DI | FastAPI Dependency Injection (require_feature, check_resource_limit factories) | 4/5 | Low | 3B |
| 16 | Event Sourcing | Event Store Factory (construction paths, singleton, URL parsing) | 4/5 | Low | 3B |
| 17 | Event Sourcing | Projection Runner/Poller (polling, graceful shutdown, auto-discovery lifespan) | 5/5 | Info | 3B |
| 18 | Event Sourcing | Projection Rebuilder (clear/reset workflow, abstract contract) | 3/5 | Medium | 3B |
| 19 | Caching | Config Cache Pattern (L1/L2, tenant isolation, invalidation) | 4/5 | Low | 3B |
| 20 | Context | Foundation Application Context (RequestContext, ContextVar, principal context) | 5/5 | Info | 3B |
| 21 | Config | Config Service Pattern (resolution chain, feature flags, resource limits) | 4/5 | Low | 3B |
| 22 | Resource Limits | Resource Limits (foundation service, FastAPI dependency, rate-limit headers) | 4/5 | Low | 3B |
| 23 | Routing | Router Mount Convention (health stub, auto-discovery, prefix/tag policy) | 3/5 | Medium | 3B |
| 24 | Governance | Development Constitution Article III (quality standards, type safety, docstrings) | 3/5 | Medium | 3B |

## Critical & High Findings

### High Severity

**H1. TaskIQ Configuration Bypasses All Infrastructure Conventions** (Item 7, Source 3A)

The `infra-taskiq` package is the only infrastructure package that does not follow the established Pydantic settings pattern. It uses raw `os.getenv("REDIS_URL", "redis://localhost:6379/0")` at `broker.py:57` with no validation, no type safety, and no `.env` file support. Additional gaps:

- `broker.py:48-57`: No `BaseSettings` class; every other infra package uses one.
- `broker.py:61-81`: Broker, result backend, and scheduler are instantiated at module import time, before environment is fully configured. This can cause failures if the lifespan bridge has not yet populated `REDIS_URL`.
- No retry policies or dead-letter queue configuration. Failed tasks are silently lost.
- No serialization configuration -- uses pickle defaults, which is a security concern for untrusted payloads.
- No `LifespanContribution` for startup/shutdown. The broker connection is never explicitly closed.
- `broker.py:63`: Result TTL (`result_ex_time=3600`) is hardcoded and not configurable.

## Medium Findings

**M1. Missing Repository and Unit-of-Work Abstractions** (Item 5, Source 3A)

The persistence package provides session factories and RLS helpers but no abstract repository or unit-of-work patterns. Domain packages directly consume SQLAlchemy `AsyncSession` via `DbSession`, creating tight coupling. Module-level mutable globals at `database.py:84-89` (`_engine`, `_session_factory`, etc.) complicate testing.

- `database.py:84-89`: Global mutable state for engine/session singletons requires manual reset in tests.
- `rls_helpers.py:18-20`: Table names are f-string interpolated into raw SQL. While only used in Alembic migrations (controlled context), the functions accept unvalidated string input.
- `tenant_context.py:60`: Uses `type: ignore[attr-defined]` comment, indicating a type system gap.

**M2. Projection Rebuilder Lacks Tests and Operational Documentation** (Item 18, Source 3B)

The `ProjectionRebuilder` class (`rebuilder.py:65-177`) implements the core rebuild workflow but has significant gaps:

- No test file (`test_rebuilder.py`) exists in `packages/infra-eventsourcing/tests/`.
- `rebuilder.py:96`: The `upstream_app` parameter is typed as `Any`, losing type safety.
- No CLI command or admin endpoint exists for triggering rebuilds.
- No coordination with `ProjectionPoller` for stop/start lifecycle -- callers must manage this manually (`rebuilder.py:37-38, 84-85`).
- Not exported from the main package `__init__.py`.

**M3. Router Mount Convention Undefined** (Item 23, Source 3B)

Only one router exists (health stub at `_health.py:1-17`), and no conventions are documented or enforced:

- `app_factory.py:153`: Calls `include_router(router)` without requiring a prefix.
- No URL prefix convention, tag taxonomy, or API versioning strategy (e.g., `/api/v1/...`).
- Router-level dependencies (e.g., per-router authentication) are not demonstrated.
- `docs/docs/guides/add-api-endpoint.md` documents entry-point registration but not URL conventions.

**M4. Development Constitution Document Missing** (Items 11 and 24, Sources 3A and 3B)

The Development Constitution (`docs/docs/architecture/development-constitution.md`) does not exist in the repository. Quality standards are distributed across `CLAUDE.md`, `docs/docs/decisions.md`, `docs/docs/architecture/entry-points.md`, and implementation guides. Additionally:

- None of the PADRs referenced in audit criteria (PADR-103, PADR-105, PADR-106, PADR-109, PADR-110, PADR-116, PADR-120) exist as standalone documents. PADR-109 content appears inline in `decisions.md`, but others are undocumented.
- The accepted exception for domain packages depending on `infra-eventsourcing` (documented in `CLAUDE.md`) is not formally captured in a PADR.
- Some `type: ignore` comments lack issue tracker references or suppression justification beyond inline comments.

**M5. Pydantic Settings Inconsistencies** (Items 1 and 10, Source 3A)

While 5 of 6 infrastructure packages follow the Pydantic settings pattern, notable inconsistencies remain:

- `packages/infra-persistence/src/praecepta/infra/persistence/redis_settings.py:16-49`: No `env_prefix`; fields manually prefixed with `redis_` instead of using `env_prefix="REDIS_"`.
- `packages/infra-persistence/src/praecepta/infra/persistence/database.py:98`: `DatabaseSettings` re-instantiated on every call to `_get_database_url()` rather than cached via `lru_cache`.
- `packages/infra-auth/src/praecepta/infra/auth/settings.py:93-116`: `validate_oauth_config()` is a method that must be explicitly called; it is not triggered by Pydantic's validation pipeline, meaning partial OAuth configuration raises no error until manual invocation.

**M6. Sync/Async Protocol Mismatch in Config Cache** (Item 19, Source 3B)

The `ConfigCache` protocol in `config_service.py:48-69` defines synchronous `get`/`set`/`delete` methods, but `HybridConfigCache` (`config_cache.py:17-138`) implements async `get`/`set`/`invalidate` methods. These protocols are not directly compatible and would cause runtime errors if directly connected without an adapter.

**M7. Duplicate ResourceLimitResult Types** (Item 22, Source 3B)

Two separate `ResourceLimitResult` classes exist: one in `foundation/application/resource_limits.py:25` and one in `infra/fastapi/dependencies/resource_limits.py:44`. They have identical structure but are different types. The foundation version includes an `increment` parameter in `remaining` calculation, while the FastAPI version always assumes increment=1.

## Low & Info Findings

**Low Severity (9 items):**

- JWT JWKS URI constructed via string concatenation (`jwks.py:67`) rather than OIDC discovery, though the docstring mentions OIDC discovery (Items 3, Source 3A).
- Health check endpoint is a stub returning only `{"status": "ok"}` with no dependency health checks (`_health.py:11-17`); docstring acknowledges this is planned for Step 6 (Item 6, Source 3A).
- `infra-auth` uses stdlib `logging.getLogger(__name__)` rather than structlog's `get_logger()` (Item 6, Source 3A).
- JWT middleware returns `JSONResponse` directly rather than raising domain exceptions due to ASGI stack limitations (`jwt_auth.py:14-16`), creating dual error paths with similar but not identical response structures (Item 9, Source 3A).
- `api_key_auth.py:156` accesses `request.app.state.agent_api_key_repo` at runtime rather than via constructor injection (Item 12, Source 3A).
- `feature_flags.py:47-59`: `_get_feature_checker` accesses `request.app.state.feature_checker` without validation that the attribute exists (Item 15, Source 3B).
- `event_store.py:222-245`: `lru_cache`-based singleton on `get_event_store()` cannot be cleared for testing (Item 16, Source 3B).
- `event_store.py:209-218`: `close()` method does not clear the `lru_cache`, so `get_event_store()` returns a closed instance (Item 16, Source 3B).
- `error_handlers.py:355`: `Retry-After` header hardcoded to 3600 seconds (Item 22, Source 3B).

**Info Severity (5 items):**

- Dev bypass environment check uses `os.environ.get()` rather than centralized settings -- arguably correct for production safety (Item 4, Source 3A).
- RFC 7807 error handling is fully compliant with comprehensive security sanitization and header compliance (Items 13, Source 3B).
- Middleware contribution pattern is consistently implemented with fail-soft behavior for non-conforming contributions (Item 14, Source 3B).
- Projection poller correctly implements cross-process event consumption with proper error recovery and responsive shutdown (Item 17, Source 3B).
- Foundation application context cleanly separates request and principal contexts with proper ContextVar lifecycle management (Item 20, Source 3B).

## Cross-Cutting Themes

**Theme 1: Strong Implicit Conventions, Weak Formal Documentation**

The codebase consistently applies well-chosen patterns (Pydantic settings, entry-point auto-discovery, priority-based middleware, error handler registration), but the governing documents that codify these conventions are absent. The Development Constitution does not exist. None of the referenced PADRs exist as standalone documents. Conventions are enforced by tooling (import-linter, Pydantic validation) and by example (consistent patterns across packages), but not by formal policy. This creates an onboarding risk -- the TaskIQ package's deviation from conventions (Item 7) may be a symptom of insufficient documentation.

**Theme 2: Sync/Async Interface Mismatches**

Multiple locations exhibit a pattern where foundation-layer protocols define synchronous interfaces while infrastructure implementations provide async variants. The `ConfigCache` protocol vs `HybridConfigCache` (Item 19) is the clearest example, but the pattern also appears in `ConfigRepository.upsert` (sync) vs async service usage, and in the dual session factory approach (async for requests, sync for projections at `database.py:171-208`). This creates friction at the boundary between layers.

**Theme 3: Module-Level Singleton Anti-Pattern**

Several infrastructure packages use module-level mutable globals or import-time instantiation for singletons: `database.py:84-89` (engine/session factories), `broker.py:61-81` (TaskIQ broker/backend/scheduler), and `event_store.py:222-245` (`lru_cache` singleton). While pragmatic, this pattern complicates testing, prevents clean reconfiguration, and creates hidden temporal coupling with the lifespan system.

**Theme 4: Security-First Error Handling**

Across both collectors, the error handling consistently demonstrates security awareness: sensitive data redaction in logs and error responses (`error_handlers.py:103-124`, `logging.py:147-197`), `repr=False` on password fields, production/debug mode toggle for error detail exposure, and RFC 6750 `WWW-Authenticate` headers on 401 responses. This is a genuine strength that indicates mature engineering judgment in the security domain.

## Strengths

1. **RFC 7807 Error Handling (5/5)**: The `ProblemDetail` model, handler registration, and security sanitization represent production-grade implementation. All domain exceptions are mapped, rate-limit headers are included on 429s, `WWW-Authenticate` on 401s, and sensitive data is redacted via both exact-match and regex patterns.

2. **Middleware Contribution Pattern (5/5)**: The `MiddlewareContribution` system with documented priority bands, LIFO sorting in the app factory, and entry-point auto-discovery provides a clean, extensible, and consistent pattern. The first-match-wins coordination between API key and JWT middleware is well-designed.

3. **Development Bypass Safety (5/5)**: Multiple layers of protection -- production lockout regardless of `AUTH_DEV_BYPASS` value, explicit opt-in, ERROR-level logging of production bypass attempts, and synthetic non-production claims -- demonstrate defense-in-depth thinking.

4. **Projection Polling Infrastructure (5/5)**: The `ProjectionPoller` correctly handles cross-process event consumption with daemon threads, responsive shutdown via stop events, exception resilience in the poll loop, and proper lifespan ordering (priority 200 after event store at 100). The deprecation path from `ProjectionRunner` is clean.

5. **Foundation Application Context (5/5)**: Clean two-layer separation where the foundation defines `RequestContext` with `ContextVar`-based propagation and the infra layer populates it from HTTP headers. Token-based cleanup in `finally` blocks, separate principal context for independent lifecycle, and `NoRequestContextError` with descriptive messages.

## Recommendations

**P1 -- Address Before Next Release:**

1. **Create Pydantic settings for TaskIQ** (Item 7): Introduce a `TaskIQSettings(BaseSettings)` class with `env_prefix="TASKIQ_"`, validated Redis URL, configurable result TTL, and retry policy settings. Add a `LifespanContribution` for broker startup/shutdown. Replace module-level instantiation with a factory pattern.

2. **Resolve sync/async ConfigCache protocol mismatch** (Item 19): Either make the `ConfigCache` protocol async-compatible or introduce an async adapter. The current state would cause runtime errors if the `HybridConfigCache` were directly used with `TenantConfigService`.

3. **Add tests for ProjectionRebuilder** (Item 18): This is a destructive operation (clears read models) with zero test coverage. Type the `upstream_app` parameter properly and add at minimum: unit tests for the clear/reset workflow, error handling when recorder lacks `delete_tracking_record`, and integration test for the full rebuild cycle.

**P2 -- Address in Next Sprint:**

4. **Establish router mount conventions** (Item 23): Before domain packages add routers, document and enforce URL prefix patterns (`/api/v1/{domain}/...`), tag requirements, API versioning strategy, and per-router authentication dependencies. Consider adding prefix/tag validation in the app factory's router discovery loop.

5. **Create the Development Constitution document** (Item 24): Consolidate the quality standards currently scattered across `CLAUDE.md`, `decisions.md`, and guide documents into a single `development-constitution.md`. Include the existing patterns as formal requirements (Pydantic settings, entry-point discovery, error handler registration, PEP 420 namespaces).

6. **Eliminate duplicate ResourceLimitResult** (Item 22): The foundation and FastAPI layers should share a single type. Import the foundation version in the FastAPI layer rather than redeclaring it.

7. **Cache DatabaseSettings via lru_cache** (Item 1): Add an `@lru_cache` singleton wrapper for `DatabaseSettings` consistent with the pattern used by `AuthSettings`, `LoggingSettings`, and `TracingSettings`. The current re-instantiation at `database.py:98` on every `_get_database_url()` call is wasteful.

**P3 -- Address When Convenient:**

8. **Create missing PADR documents** (Item 11): Document the architectural decisions currently captured only in code. Priority PADRs: PADR-103 (error handling strategy), PADR-106 (middleware ordering), PADR-120 (entry-point discovery). These decisions are sound but not formally recorded.

9. **Standardize RedisSettings env_prefix** (Item 1): Add `env_prefix="REDIS_"` to `RedisSettings` and remove the manual `redis_` field name prefixes, aligning with the convention used by all other settings classes.

10. **Replace module-level engine globals with a factory** (Item 5): Introduce a `DatabaseFactory` or provider pattern for `database.py:84-89` to improve testability and eliminate mutable module-level state. This would also resolve the `type: ignore[attr-defined]` in `tenant_context.py:60`.

11. **Implement health check dependency probes** (Item 6): Upgrade the stub `/healthz` endpoint to check database, Redis, and event store connectivity. Add a `/readyz` readiness probe. The current stub at `_health.py:11-17` is acknowledged as temporary.

---

## RAG Calculation

| Metric | Value | Threshold (GREEN) | Threshold (AMBER) | Result |
|--------|-------|-------------------|-------------------|--------|
| Critical findings | 0 | 0 | 0 | Pass (both) |
| High findings | 1 | 0 | <=2 | Fail GREEN, Pass AMBER |
| Average maturity | 3.96/5 | >= 4.0 | >= 3.0 | Fail GREEN, Pass AMBER |
| Checklist items at 4+ | 18/24 (75%) | >= 80% | N/A | Fail GREEN |
| Checklist items at 3+ | 23/24 (95.8%) | N/A | >= 60% | Pass AMBER |

**3A Average:** (4+5+4+5+3+4+2+4+4+4+3+4) / 12 = 46/12 = 3.83/5
**3B Average:** (5+5+4+4+5+3+4+5+4+4+3+3) / 12 = 49/12 = 4.08/5
**Combined Average:** (46+49) / 24 = 95/24 = **3.96/5**

**Final RAG: AMBER** -- 1 High finding, average maturity 3.96 (below 4.0 GREEN threshold), and 75% at 4+ (below 80% GREEN threshold). All AMBER thresholds are met.
