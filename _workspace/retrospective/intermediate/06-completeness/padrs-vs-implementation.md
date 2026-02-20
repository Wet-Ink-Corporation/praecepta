# PADRs vs Implementation -- Completeness & Gaps

**Collector ID:** 6A
**Dimension:** Completeness & Gaps
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. PADR Coverage Inventory

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

There are **25 PADRs** (4 strategic + 21 pattern) in the `_kb/decisions/` directory (PADR-001 through PADR-122, with PADR-003 and PADR-117 intentionally skipped during renumbering). The public documentation index at `docs/docs/decisions.md:106` states "The complete set of 25 PADRs (4 strategic + 21 pattern)."

However, there is a significant **status inconsistency** between the index and the PADR files themselves. The `_kb/decisions/_index.md:10-41` lists ALL 25 PADRs as "Accepted," but the actual PADR files show a different picture:

**Findings:**

| Status | Count | PADRs |
|--------|-------|-------|
| Accepted | 6 | 005, 107, 108, 109, 110, 122 |
| Proposed | 8 | 111, 112, 113, 114, 115, 116, 118, 119, 120, 121 |
| Draft | 7 | 001, 002, 004, 101, 102, 103, 104, 105, 106 |

- `_kb/decisions/_index.md:12` says PADR-001 is "Accepted" but `_kb/decisions/strategic/PADR-001-event-sourcing.md:4` says "Draft"
- `_kb/decisions/_index.md:13` says PADR-002 is "Accepted" but `_kb/decisions/strategic/PADR-002-modular-monolith.md:4` says "Draft"
- `_kb/decisions/_index.md:21` says PADR-101 is "Accepted" but `_kb/decisions/patterns/PADR-101-vertical-slices.md:4` says "Draft"
- `_kb/decisions/_index.md:37` says PADR-116 is "Accepted" but `_kb/decisions/patterns/PADR-116-jwt-auth-jwks.md:4` says "Proposed"
- This pattern repeats for 19 of 25 PADRs

This creates confusion about which decisions are actually ratified versus still under discussion. Note that many of these "Draft" and "Proposed" PADRs have full implementations in the codebase, suggesting the statuses were never updated after implementation.

---

## 2. Foundation Layer PADRs (001, 108, 111, 113, 114)

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The foundation layer PADRs are well-implemented:

**PADR-001 (Event Sourcing):** Fully implemented. The `eventsourcing` library (v9.5+) is the backbone. `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26` defines `BaseAggregate(Aggregate)` extending the library. Both `Tenant` (`packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:30`) and `User` (`packages/domain-identity/src/praecepta/domain/identity/user.py:17`) aggregates correctly use `@event` decorators. PostgreSQL event store is configured via `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/event_store.py:57`.

**PADR-108 (Domain Service Protocols):** Pattern is documented but the specific examples cited (CycleDetectionService, TagInheritanceService, ACLInheritanceService) reference the source project (`{Project}`), not praecepta. The Protocol-based pattern is not visibly used in the current praecepta codebase -- no Protocol-based readers were found in foundation or domain packages. However, this is expected given the framework extracts foundational primitives, not domain-specific services.

**PADR-111 (ClassVar Aggregate Type Discrimination):** Not directly implemented in praecepta. The PADR describes a pattern from the source project using `ClassVar[str]` for `BLOCK_TYPE` discrimination on `Order` subtypes. No such aggregate subtype hierarchy exists in praecepta's current domain packages. The pattern is documented for future consumers.

**PADR-113 (Two-Tier Validation):** Implemented. Value objects in `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:49-102` perform Tier 1 format validation in `__post_init__()` (e.g., `TenantSlug`, `TenantName`). The `ValidationResult` dataclass mentioned in the PADR is not present in the codebase (no `ValidationResult` type found), but the structural validation pattern is consistently applied via frozen dataclass value objects.

**PADR-114 (Aggregate Lifecycle State Machine):** Fully implemented. `Tenant` aggregate at `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:30-399` exactly follows the convention: `request_*()` public methods with idempotency checks, `_apply_*()` private methods with `@event()` decorators, `InvalidStateTransitionError` for invalid transitions, and terminal state handling for `DECOMMISSIONED`.

**Findings:**

| PADR | Implementation Status | Key File |
|------|----------------------|----------|
| 001 | Fully implemented | `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26` |
| 108 | Not applicable (source-project pattern) | N/A in praecepta |
| 111 | Not applicable (source-project pattern) | N/A in praecepta |
| 113 | Partially implemented (no ValidationResult) | `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:49` |
| 114 | Fully implemented | `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:30` |

---

## 3. Infrastructure Layer PADRs (103, 104, 105, 106, 110)

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

**PADR-103 (Error Handling):** Fully implemented. RFC 7807 Problem Details are implemented in `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:47-612`. The `ProblemDetail` Pydantic model includes all RFC 7807 fields (type, title, status, detail, instance) plus extensions (error_code, context, correlation_id). The domain exception hierarchy at `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:33-355` provides typed exceptions (NotFoundError -> 404, ValidationError -> 422, ConflictError -> 409, AuthenticationError -> 401, AuthorizationError -> 403, FeatureDisabledError -> 403, ResourceLimitExceededError -> 429). Error handlers are auto-registered via entry points at `packages/infra-fastapi/pyproject.toml:36-37`.

**PADR-104 (Testing Strategy):** Defined but only partially implemented. The PADR specifies unit/integration/slow markers and async strict mode. The `pyproject.toml` configures pytest markers (`unit`, `integration`, `slow`) and `asyncio_mode = "strict"`. Test files exist for most packages (65+ test files found across `packages/*/tests/`). However, the test structure does not follow the "vertical slice" testing pattern described in the PADR -- tests are organized by package, not by feature slice.

**PADR-105 (Observability):** Implemented. Structured logging via structlog at `packages/infra-observability/src/praecepta/infra/observability/logging.py:213-263`. OpenTelemetry tracing middleware at `packages/infra-observability/src/praecepta/infra/observability/middleware.py:29-96`. TraceContextMiddleware binds trace_id/span_id to structlog context. Sensitive data redaction is implemented via `SensitiveDataProcessor` at `packages/infra-observability/src/praecepta/infra/observability/logging.py:147-197`.

**PADR-106 (Configuration - Pydantic Settings):** Fully implemented. Settings classes use `pydantic_settings.BaseSettings` with env prefix conventions throughout: `AuthSettings` (`AUTH_` prefix, `packages/infra-auth/src/praecepta/infra/auth/settings.py:25`), `EventSourcingSettings` (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/settings.py:17`), `AppSettings` (`APP_` prefix, `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:46`), `CORSSettings` (`CORS_` prefix), `LoggingSettings`. All use `model_config = SettingsConfigDict(...)` pattern consistently. Singleton caching via `@lru_cache(maxsize=1)` is used for `get_auth_settings()`, `get_logging_settings()`.

**PADR-110 (Application Lifecycle):** Implemented. Application singletons are managed via entry-point discovery (`praecepta.applications` group). `packages/domain-tenancy/pyproject.toml:22-23` declares `tenancy = "praecepta.domain.tenancy.tenant_app:TenantApplication"`. Lifespan hooks compose via `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py`. Event store lifespan at priority 100, projection runner at priority 200 (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:144-147`).

**Findings:**

| PADR | Implementation Status | Key File |
|------|----------------------|----------|
| 103 | Fully implemented | `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:47` |
| 104 | Partially implemented (markers yes, vertical slice tests no) | `pyproject.toml` markers + `packages/*/tests/` |
| 105 | Fully implemented | `packages/infra-observability/src/praecepta/infra/observability/logging.py:213` |
| 106 | Fully implemented | Multiple settings classes across packages |
| 110 | Fully implemented | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:144` |

---

## 4. Auth & Security PADRs (116, 117, 120)

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Note: PADR-117 was intentionally skipped during renumbering (`_kb/decisions/_index.md:6`).

**PADR-116 (JWT Auth with JWKS):** Fully implemented. `JWKSProvider` at `packages/infra-auth/src/praecepta/infra/auth/jwks.py:25-122` wraps PyJWKClient with caching and rotation support. `JWTAuthMiddleware` at `packages/infra-auth/src/praecepta/infra/auth/middleware/jwt_auth.py:60-345` validates RS256 tokens, checks exp/iss/aud/sub claims, returns RFC 6750 WWW-Authenticate headers on 401. Dev bypass with production lockout is implemented at `packages/infra-auth/src/praecepta/infra/auth/dev_bypass.py:23-63`. The `Principal` value object at `packages/foundation-domain/src/praecepta/foundation/domain/principal.py:24-45` stores extracted claims as a frozen dataclass.

**PADR-120 (Multi-Auth Middleware Sequencing):** Fully implemented. `APIKeyAuthMiddleware` at `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:55-295` runs at priority 100, `JWTAuthMiddleware` at priority 150 (`packages/infra-auth/src/praecepta/infra/auth/middleware/jwt_auth.py:348-351`). Both check `get_optional_principal()` at dispatch start for first-match-wins semantics. The PADR specifies LIFO registration with `app.add_middleware()`, but the implementation uses the auto-discovery priority system from PADR-122 instead. This is a beneficial evolution: `app_factory.py:117-118` sorts by priority ascending then adds in reverse (LIFO), achieving the same effect declaratively.

**Findings:**

| PADR | Implementation Status | Key File |
|------|----------------------|----------|
| 116 | Fully implemented | `packages/infra-auth/src/praecepta/infra/auth/middleware/jwt_auth.py:60` |
| 117 | Skipped (intentional) | N/A |
| 120 | Implemented (evolved to priority-based) | `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:298-301` |

---

## 5. Domain Layer PADRs (109, 112, 118, 119, 121)

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

**PADR-109 (Sync-First Event Sourcing):** Implemented. The decision specifies sync `def` for command endpoints and async `async def` for query endpoints. Since praecepta is a framework (not a consumer application), there are no command/query endpoints to verify directly. However, the projection infrastructure follows the sync pattern: `BaseProjection` uses sync processing, `ProjectionPoller` at `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:80-147` uses synchronous `pull_and_process()` calls from a background thread.

**PADR-112 (Module-Level Registry):** Pattern is available for consumers but not directly exercised in praecepta. The PADR describes using module-level constants and pure functions instead of class-based singletons for domain registries. The source-project examples (TagRegistry, namespace mappings) are not present. However, the pattern is visible in how praecepta uses module-level constants (e.g., `SENSITIVE_FIELDS` frozenset at `packages/infra-observability/src/praecepta/infra/observability/logging.py:37-50`).

**PADR-118 (JIT User Provisioning):** Fully implemented. `UserProvisioningService` at `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:31-145` follows the exact flow specified: fast-path lookup via `OidcSubRegistry`, reserve/create/confirm slow-path, race condition retry with exponential backoff (`time.sleep(0.05 * (attempt + 1))`), and compensating release on failure. The `OidcSubRegistry` exists at `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py`.

**PADR-119 (Separate User Application):** Implemented. `UserApplication` at `packages/domain-identity/src/praecepta/domain/identity/user_app.py` and `AgentApplication` at `packages/domain-identity/src/praecepta/domain/identity/agent_app.py` are separate application classes, registered independently in `packages/domain-identity/pyproject.toml:22-24`. This matches the PADR's decision to separate User and Agent into distinct application services.

**PADR-121 (Projection-Based Authentication):** Implemented. `AgentAPIKeyProjection` is registered at `packages/domain-identity/pyproject.toml:27-28`. `APIKeyAuthMiddleware` at `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:156-159` uses `repo.lookup_by_key_id(key_id)` for projection-based O(1) lookup, not aggregate hydration. The `agent_api_key_repository.py` at `packages/domain-identity/src/praecepta/domain/identity/infrastructure/agent_api_key_repository.py` provides the projection lookup.

**Findings:**

| PADR | Implementation Status | Key File |
|------|----------------------|----------|
| 109 | Implemented (framework-level sync projections) | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:80` |
| 112 | Pattern available, not exercised in framework | N/A |
| 118 | Fully implemented | `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:31` |
| 119 | Fully implemented | `packages/domain-identity/pyproject.toml:22-24` |
| 121 | Fully implemented | `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:156` |

---

## 6. Architecture PADRs (102, 107, 122)

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

**PADR-102 (Hexagonal Ports and Adapters):** Enforced at the architectural level. The 4-layer dependency hierarchy (Foundation < Infrastructure < Domain < Integration) is enforced by `import-linter` contracts at `pyproject.toml:184-215`. Two contracts: (1) Foundation packages cannot import infrastructure frameworks (fastapi, sqlalchemy, httpx, structlog, opentelemetry, taskiq, redis), and (2) Layer ordering via `importlinter` layers contract. PEP 420 implicit namespace packages are used correctly -- intermediate directories have no `__init__.py`. `make boundaries` (`uv run lint-imports`) enforces these contracts in CI.

**PADR-107 (API Documentation - OpenAPI):** Implemented. `AppSettings` at `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:60-62` exposes `docs_url="/docs"`, `redoc_url="/redoc"`, `openapi_url="/openapi.json"` as configurable settings. The `create_app()` factory at `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:82-91` passes these to `FastAPI()`. Health endpoint is auto-registered at `packages/infra-fastapi/pyproject.toml:28-29`.

**PADR-122 (Entry-Point Auto-Discovery):** Fully and thoroughly implemented. This is the best-implemented PADR in the codebase. The `discover()` utility at `packages/foundation-application/src/praecepta/foundation/application/discovery.py:32-65` wraps `importlib.metadata.entry_points()`. Contribution dataclasses at `packages/foundation-application/src/praecepta/foundation/application/contributions.py:14-53` define `MiddlewareContribution`, `ErrorHandlerContribution`, `LifespanContribution`. The `create_app()` factory at `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:36-157` discovers and wires all six entry point groups. All packages declare entry points in their `pyproject.toml` files. Middleware priority bands match the PADR spec (0-99 outermost, 100-199 security, 200-299 context). Seven packages register entry points across 6 groups.

**Findings:**

| PADR | Implementation Status | Key File |
|------|----------------------|----------|
| 102 | Fully implemented + tooling-enforced | `pyproject.toml:184-215` (import-linter) |
| 107 | Fully implemented | `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:60-62` |
| 122 | Fully implemented (exemplary) | `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:36` |

---

## 7. Specified-But-Missing Features

**Rating: 2/5 -- Initial**
**Severity:** Medium | **Confidence:** High

Several features described in PADRs have zero or near-zero implementation in praecepta:

**Findings:**

| Feature (PADR Source) | Description | Status |
|----------------------|-------------|--------|
| Vertical slice organization (PADR-101) | Code organized by use case with cmd.py/endpoint.py/test_cmd.py per slice | Not implemented. Praecepta packages organize by package/module, not by vertical slice. The domain packages have `tenant.py`, `tenant_app.py` but no slice directories. |
| Domain Service Protocols (PADR-108) | Protocol-based readers for domain services (CycleDetectionService, etc.) | Not applicable to framework. Source-project patterns not extracted. No Protocol-based readers found. |
| ClassVar type discrimination (PADR-111) | ClassVar pattern for aggregate subtype discrimination | Not applicable. No aggregate subtype hierarchy exists in praecepta. |
| Module-level registries (PADR-112) | Module-level constants + pure functions for domain registries | Pattern described but not implemented as a reusable facility. |
| ValidationResult dataclass (PADR-113) | Tier 2 semantic validation via `ValidationResult` return type | `ValidationResult` dataclass not found in codebase. Only Tier 1 format validation is implemented. |
| PostgreSQL RLS policies (PADR-115) | Row-Level Security policies on projection tables | RLS helpers exist (`packages/infra-persistence/src/praecepta/infra/persistence/rls_helpers.py:10-69`) but no actual migration files applying RLS are present. No Alembic migrations directory found in the monorepo. |
| Integration package logic (PADR-002) | Cross-domain sagas in integration layer | `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py` is a stub with only a docstring. No saga logic. |
| Security trimming (PADR-004) | Claim-based UI/API response filtering | No security trimming implementation found. The PADR is still "Draft." |
| OIDC client flow (PADR-116 extension) | OAuth/OIDC authorization code flow with PKCE | `packages/infra-auth/src/praecepta/infra/auth/oidc_client.py` and `pkce.py` exist but are not wired into any entry point or middleware. No router endpoint for `/auth/callback`. |

---

## 8. Partial Implementations

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Several features have partial implementation -- the infrastructure exists but is incomplete relative to the PADR spec.

**Findings:**

| Feature | PADR Spec | What Exists | What's Missing |
|---------|-----------|-------------|----------------|
| Two-tier validation (PADR-113) | ValidationResult dataclass for Tier 2 semantic validation | Tier 1 format validation via value object constructors (`TenantSlug.__post_init__()` at `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:65-77`) | No `ValidationResult` type. No separate semantic validation functions. |
| RLS tenant isolation (PADR-115) | RLS policies on all projection tables, FORCE RLS, parameterized set_config | `rls_helpers.py` utility functions, `tenant_context.py:60-63` using `set_config('app.current_tenant', :tenant, true)` | No Alembic migration files. No actual RLS policies applied to tables. |
| Observability (PADR-105) | Full OpenTelemetry instrumentation: traces, metrics, health checks | Structured logging configured, trace context middleware implemented. `packages/infra-observability/src/praecepta/infra/observability/tracing.py` and `instrumentation.py` exist. | Metrics are not implemented. No metric exports or Prometheus integration visible. |
| Task queue (PADR-005) | Redis/TaskIQ for background tasks, scheduled jobs, event-driven workflows | Broker and scheduler configured at `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:67-81`. | No actual tasks defined. No lifespan integration. No entry points registered for taskiq package. No `praecepta.lifespan` entry point in `packages/infra-taskiq/pyproject.toml`. |
| Projection runner (PADR-109) | Synchronous projections via polling | `ProjectionPoller` exists and is auto-discovered via lifespan entry points. | Polling-based approach replaces the PADR-109 specified "sync projections in same transaction." The actual implementation uses a background polling thread, which is eventually consistent (not same-transaction). |

---

## 9. Decision Drift

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

There are cases where the implementation has evolved beyond or diverged from the PADR specification.

**Findings:**

| PADR | Specified Approach | Actual Implementation | Drift Type |
|------|-------------------|----------------------|------------|
| PADR-109 | Sync projections in same transaction as event save ("When `app.save(agent)` returns, projection is updated") | `ProjectionPoller` uses background polling thread (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:80-147`). Git commit `93d2192` ("fix: replace in-process projection runner with polling-based consumption") explicitly moved away from same-transaction processing. | **Significant drift.** The PADR claims synchronous same-transaction projection updates, but the implementation uses eventual consistency via polling. |
| PADR-120 | Manual LIFO middleware registration via `app.add_middleware()` with comments | Auto-discovery via `MiddlewareContribution` priority bands (`packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:298-301`, priority=100; `jwt_auth.py:348-351`, priority=150) | **Beneficial drift.** The priority-based system is superior to manual ordering. PADR-120 should be updated to reflect this. |
| PADR-121 | References `src/{Project}/shared/infrastructure/projections/agent_api_key.py` and `src/{Project}/shared/infrastructure/middleware/api_key_auth.py` | Implemented in praecepta's package structure: `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/agent_api_key.py` and `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py` | **Expected drift.** PADRs reference source project paths; implementation correctly maps to praecepta's namespace package structure. |
| PADR-001 | Shows `Order` aggregate with memberships pattern | No `Order` aggregate in praecepta. Tenant and User aggregates implement the pattern instead. | **Expected drift.** Framework extracts patterns, not source-project domain models. |

The PADR-109 drift is the most architecturally significant. The PADR's synchronous projection guarantee is a key selling point ("no eventual consistency gap"), but the implementation uses polling. The git history shows this was an intentional change, but the PADR was not updated to reflect it.

---

## 10. Superseded Decisions

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** Medium

**Findings:**

| PADR | Effective Status | Evidence |
|------|-----------------|----------|
| PADR-109 (Sync projections) | **Effectively superseded** by polling-based approach | Git commit `93d2192` "fix: replace in-process projection runner with polling-based consumption" directly contradicts the same-transaction guarantee. The PADR should be updated or a new PADR should supersede it. |
| PADR-120 (Manual middleware ordering) | **Effectively superseded** by PADR-122 priority bands | PADR-120 describes manual `app.add_middleware()` ordering. PADR-122's `MiddlewareContribution` priority system makes this obsolete. PADR-120's patterns are still referenced but the actual ordering mechanism is now declarative priorities. |
| PADR-101 (Vertical slices) | **Not followed** in praecepta | The framework uses a package-per-bounded-context layout, not vertical slices. No `slices/` directories exist. The PADR may only apply to consumer applications, but this is not clarified. |

None of these PADRs are marked as "Superseded" in their metadata. The status tracking does not reflect the actual state of decisions.

---

## 11. Missing PADRs

**Rating: 2/5 -- Initial**
**Severity:** High | **Confidence:** High

Several significant architectural decisions visible in the codebase have no corresponding PADR.

**Findings:**

| Decision | Where Visible | Impact |
|----------|--------------|--------|
| **Polling-based projection consumption** | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:1-15`, git commit `93d2192` | This replaced the PADR-109 synchronous approach. A new PADR should document why, the trade-offs (eventual consistency gap), and the polling interval configuration. |
| **PEP 420 implicit namespace packages** | All packages under `packages/*/src/praecepta/` have no `__init__.py` in intermediate directories. `CLAUDE.md` documents this but no PADR exists. | This is a foundational packaging decision affecting every package. Deserves a PADR given its non-obvious nature and the bugs that can result from adding `__init__.py` files. |
| **BaseAggregate multi-tenancy convention** | `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26-109` requires all aggregates to set `self.tenant_id` | This is a cross-cutting architectural constraint. It's documented in code comments but has no dedicated PADR. |
| **Dev bypass authentication pattern** | `packages/infra-auth/src/praecepta/infra/auth/dev_bypass.py:23-63` with production lockout | Security-critical pattern that deserves its own PADR documenting the safety guarantees. |
| **Request context ContextVar design** | `packages/foundation-application/src/praecepta/foundation/application/context.py:1-222` with separate Principal ContextVar | The decision to separate Principal from RequestContext (to avoid breaking frozen dataclass) and use ContextVars (not request.state) is architecturally significant. |
| **Config cache pattern** | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/config_cache.py` | In-memory config caching with event-sourced invalidation is not covered by any PADR. |
| **OIDC sub registry reservation pattern** | `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py` with reserve/confirm/release | The three-phase reservation pattern for uniqueness enforcement across eventual-consistency boundaries is complex enough to warrant a dedicated PADR. It is partially described in PADR-118 but the registry itself deserves standalone documentation. |

---

## 12. PADR Quality & Consistency

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

PADRs vary significantly in quality and format. They fall into three categories:

**Well-written (6 PADRs):** PADR-109, PADR-120, PADR-121, PADR-122 are exemplary. They include Context, Decision, Rationale, Consequences (Positive/Negative/Neutral), Alternatives Considered with code examples, Implementation Notes, and Related Decisions. PADR-122 (`_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md`) is the gold standard -- it includes a Key Files section mapping to actual implementation.

**Adequate (10 PADRs):** PADR-103, PADR-108, PADR-111, PADR-112, PADR-113, PADR-114, PADR-115, PADR-116, PADR-118, PADR-119 have the essential sections but vary in depth. Some still reference `{Project}` placeholders (e.g., `_kb/decisions/patterns/PADR-111-classvar-aggregate-type-discrimination.md:41` uses `{Project}.shared.domain.aggregates`).

**Incomplete (9 PADRs):** PADR-001, PADR-002, PADR-004, PADR-005, PADR-101, PADR-102, PADR-104, PADR-105, PADR-106, PADR-107 are in "Draft" status with varying levels of completeness. Several are quite brief.

**Findings:**

| Issue | Count | Examples |
|-------|-------|---------|
| `{Project}` placeholder not replaced | 8+ PADRs | `PADR-111-classvar-aggregate-type-discrimination.md:41`, `PADR-121-projection-based-authentication.md:279`, `PADR-120-multi-auth-middleware-sequencing.md:208` |
| Status mismatch (index vs file) | 19 of 25 | Index says "Accepted", files say "Draft" or "Proposed" |
| Source-project references (not praecepta paths) | 8+ PADRs | References like `src/{Project}/shared/domain/tenant.py` instead of praecepta package paths |
| Missing "Key Files" section | 15+ PADRs | Only PADR-122 has a proper Key Files section mapping to implementation |
| Inconsistent metadata format | Multiple | Some use `**Deciders:**`, others use `**Author:**`, some have `**Tags:**`, others don't |
| No "Date Updated" field | All PADRs | PADRs only have creation date, no last-updated tracking |

---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | PADR Coverage Inventory | 3/5 | Medium |
| 2 | Foundation Layer PADRs (001, 108, 111, 113, 114) | 4/5 | Low |
| 3 | Infrastructure Layer PADRs (103, 104, 105, 106, 110) | 4/5 | Low |
| 4 | Auth & Security PADRs (116, 117, 120) | 4/5 | Low |
| 5 | Domain Layer PADRs (109, 112, 118, 119, 121) | 4/5 | Low |
| 6 | Architecture PADRs (102, 107, 122) | 5/5 | Info |
| 7 | Specified-But-Missing Features | 2/5 | Medium |
| 8 | Partial Implementations | 3/5 | Medium |
| 9 | Decision Drift | 3/5 | Medium |
| 10 | Superseded Decisions | 3/5 | Medium |
| 11 | Missing PADRs | 2/5 | High |
| 12 | PADR Quality & Consistency | 3/5 | Medium |

**Overall Assessment:** The PADRs that have been implemented are generally well-implemented (items 2-6 averaging 4.2/5). The primary gaps are in PADR lifecycle management: status tracking is inconsistent (19 of 25 PADRs have mismatched statuses), several decisions have drifted from their specification without PADR updates (particularly PADR-109's shift from synchronous to polling-based projections), and seven significant architectural decisions lack corresponding PADRs. The framework would benefit from a PADR review pass to update statuses, replace `{Project}` placeholders, add Key Files sections, and create new PADRs for undocumented decisions.
