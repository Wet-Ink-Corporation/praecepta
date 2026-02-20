# Dimension 6: Completeness & Gaps

**RAG Status:** AMBER
**Average Maturity:** 3.2/5
**Date:** 2026-02-18

## Executive Summary

The Praecepta monorepo demonstrates strong completeness in its core architectural infrastructure and knowledge base maintenance, but reveals significant gaps in implementation follow-through and decision lifecycle management. The 25 PADRs cover the major architectural concerns, and where implemented, the quality is generally high -- the foundation, infrastructure, auth, and architecture layer PADRs average 4.2/5 for implementation fidelity. The KB layer (manifest, search index, domain briefs, CLAUDE.md) is well-maintained and accurate, with all 9 domain briefs, 11 search index rows, and the package table in CLAUDE.md matching codebase reality.

However, the audit surfaces a pattern of "architectural intent outpacing implementation delivery." Nine features specified in PADRs have zero or near-zero implementation (vertical slices, ValidationResult, RLS migrations, integration sagas, OIDC client flow, among others). The integration package is a pure stub with no code, tests, or entry points. Neither domain package registers REST API routers, meaning the auto-discovery system for routers is effectively untested with real domain endpoints. The TaskIQ package provides only broker configuration without lifecycle integration. Seven significant architectural decisions visible in the codebase (polling-based projections, PEP 420 namespaces, BaseAggregate multi-tenancy convention, dev bypass pattern, ContextVar design, config cache, OIDC sub registry reservation) have no corresponding PADR.

PADR lifecycle management is the most pervasive gap. Of 25 PADRs, 19 have status mismatches between the index (all "Accepted") and the actual files (many "Draft" or "Proposed"). At least three decisions have been effectively superseded without PADR updates -- most notably PADR-109's synchronous projection guarantee, which was intentionally replaced by polling-based consumption (git commit `93d2192`) but the PADR still claims same-transaction consistency. Eight or more PADRs retain `{Project}` placeholders from the source project instead of praecepta-specific paths. These documentation hygiene issues, while not blocking functionality, erode trust in the decision record as a reliable source of truth.

## Consolidated Checklist

| # | Area | Item | Rating | Severity | Source |
|---|------|------|--------|----------|--------|
| 1 | Decision Coverage | PADR Coverage Inventory (25 PADRs, 19/25 status mismatches) | 3/5 | Medium | 6A |
| 2 | Implementation Fidelity | Foundation Layer PADRs (001, 108, 111, 113, 114) | 4/5 | Low | 6A |
| 3 | Implementation Fidelity | Infrastructure Layer PADRs (103, 104, 105, 106, 110) | 4/5 | Low | 6A |
| 4 | Implementation Fidelity | Auth & Security PADRs (116, 120) | 4/5 | Low | 6A |
| 5 | Implementation Fidelity | Domain Layer PADRs (109, 112, 118, 119, 121) | 4/5 | Low | 6A |
| 6 | Implementation Fidelity | Architecture PADRs (102, 107, 122) | 5/5 | Info | 6A |
| 7 | Missing Features | Specified-But-Missing Features (9 features with zero implementation) | 2/5 | Medium | 6A |
| 8 | Partial Implementation | Partial Implementations (5 features with incomplete delivery) | 3/5 | Medium | 6A |
| 9 | Decision Lifecycle | Decision Drift (3 drifted PADRs, 1 significant) | 3/5 | Medium | 6A |
| 10 | Decision Lifecycle | Superseded Decisions (3 PADRs effectively superseded, none marked) | 3/5 | Medium | 6A |
| 11 | Decision Coverage | Missing PADRs (7 undocumented architectural decisions) | 2/5 | High | 6A |
| 12 | Documentation Quality | PADR Quality & Consistency (8+ with {Project} placeholders, inconsistent metadata) | 3/5 | Medium | 6A |
| 13 | KB Accuracy | KB Manifest Accuracy | 4/5 | Low | 6B |
| 14 | KB Accuracy | KB Search Index (11 keyword rows, all valid) | 4/5 | Low | 6B |
| 15 | KB Coverage | Domain Brief Coverage (9 briefs, integration layer uncovered) | 4/5 | Low | 6B |
| 16 | Package Completeness | Integration Package Status (pure stub, no code/tests/entry points) | 1/5 | High | 6B |
| 17 | Package Completeness | TaskIQ Package Completeness (broker only, no lifecycle integration) | 3/5 | Medium | 6B |
| 18 | Package Completeness | Missing Router Implementations (no domain routers registered) | 2/5 | Medium | 6B |
| 19 | Documentation | Documentation Site Coverage (2 of 11 packages missing from mkdocs) | 3/5 | Medium | 6B |
| 20 | Documentation | CLAUDE.md Accuracy (version 0.1.0 vs actual 0.3.0) | 4/5 | Low | 6B |
| 21 | Code Quality | Stub Pattern Detection (0 NotImplementedError, 0 TODO/FIXME, 1 true stub) | 3/5 | Medium | 6B |
| 22 | Test Coverage | Test Coverage Gaps (6 untested modules, 1 untested package) | 3/5 | Medium | 6B |
| 23 | Examples | Example Completeness (1 example, narrow coverage, in-memory store) | 3/5 | Low | 6B |
| 24 | Wiring | Cross-Package Wiring Gaps (3 packages with no entry points) | 3/5 | Medium | 6B |

### RAG Calculation

- **Critical findings:** 0
- **High findings:** 2 (items #11 and #16)
- **Average maturity:** 76 / 24 = 3.17 (rounded to 3.2)
- **Items at 3+:** 20 / 24 = 83.3%
- **Items at 4+:** 9 / 24 = 37.5%
- **RAG determination:** No Critical; <=2 High; avg maturity 3.2 >= 3.0; 83.3% at 3+ >= 60% --> **AMBER**

## Critical & High Findings

### High Severity

**H1. Missing PADRs for Significant Architectural Decisions (Item #11, Source: 6A)**

Seven architectural decisions visible in the codebase have no corresponding PADR:

| Decision | Where Visible | Impact |
|----------|--------------|--------|
| Polling-based projection consumption | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:1-15`, git commit `93d2192` | Replaced PADR-109 synchronous approach; trade-offs (eventual consistency gap) undocumented |
| PEP 420 implicit namespace packages | All `packages/*/src/praecepta/` intermediate directories | Foundational packaging decision affecting every package; non-obvious and bug-prone |
| BaseAggregate multi-tenancy convention | `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26-109` | Cross-cutting constraint requiring all aggregates to set `self.tenant_id` |
| Dev bypass authentication pattern | `packages/infra-auth/src/praecepta/infra/auth/dev_bypass.py:23-63` | Security-critical pattern with production lockout |
| Request context ContextVar design | `packages/foundation-application/src/praecepta/foundation/application/context.py:1-222` | Separate Principal ContextVar from RequestContext, use of ContextVars over request.state |
| Config cache pattern | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/config_cache.py` | In-memory config caching with event-sourced invalidation |
| OIDC sub registry reservation pattern | `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py` | Three-phase reservation pattern for uniqueness enforcement |

**H2. Integration Package Is a Pure Stub (Item #16, Source: 6B)**

The `praecepta-integration-tenancy-identity` package is entirely empty:

- `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` contains only a docstring: `"""Praecepta Integration Tenancy-Identity -- cross-domain sagas and subscriptions."""`
- `packages/integration-tenancy-identity/pyproject.toml:1-24` declares dependencies on tenancy + identity packages but has no entry point registrations
- No `tests/` directory exists
- No KB brief covers the integration layer
- No cross-domain saga handlers, event subscriptions, or projection registrations exist
- The package is listed in the 11-package inventory and architecture diagrams but contributes zero functionality

## Medium Findings

**M1. PADR Status Tracking Is Unreliable (Item #1, Source: 6A)**

19 of 25 PADRs have mismatched statuses between `_kb/decisions/_index.md` (all listed as "Accepted") and the actual PADR files. Examples:
- `_kb/decisions/_index.md:12` says PADR-001 is "Accepted" but `_kb/decisions/strategic/PADR-001-event-sourcing.md:4` says "Draft"
- `_kb/decisions/_index.md:13` says PADR-002 is "Accepted" but `_kb/decisions/strategic/PADR-002-modular-monolith.md:4` says "Draft"
- `_kb/decisions/_index.md:37` says PADR-116 is "Accepted" but `_kb/decisions/patterns/PADR-116-jwt-auth-jwks.md:4` says "Proposed"

**M2. Nine Specified Features Have Zero Implementation (Item #7, Source: 6A)**

Features specified in PADRs with no implementation: vertical slice organization (PADR-101), Domain Service Protocols (PADR-108), ClassVar type discrimination (PADR-111), module-level registries (PADR-112), ValidationResult dataclass (PADR-113), PostgreSQL RLS policies (PADR-115, no Alembic migrations), integration package logic (PADR-002), security trimming (PADR-004), and OIDC client flow (PADR-116 extension -- `packages/infra-auth/src/praecepta/infra/auth/oidc_client.py` and `pkce.py` exist but are not wired).

**M3. Five Features Are Partially Implemented (Item #8, Source: 6A)**

- Two-tier validation (PADR-113): Tier 1 format validation exists at `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:65-77`, but no `ValidationResult` type for Tier 2 semantic validation
- RLS tenant isolation (PADR-115): `rls_helpers.py` utility functions exist, `tenant_context.py:60-63` uses `set_config('app.current_tenant', :tenant, true)`, but no Alembic migration files apply actual RLS policies
- Observability (PADR-105): Structured logging and trace context middleware implemented, but metrics are not (no Prometheus integration)
- Task queue (PADR-005): Broker configured at `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:67-81`, but no tasks defined, no lifespan integration, no entry points
- Projection runner (PADR-109): Implementation uses polling (`ProjectionPoller`) rather than the PADR-specified same-transaction sync approach

**M4. Decision Drift on PADR-109 (Item #9, Source: 6A)**

PADR-109 specifies synchronous projections in the same transaction as event save ("When `app.save(agent)` returns, projection is updated"). The implementation uses `ProjectionPoller` with background polling (`packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:80-147`). Git commit `93d2192` ("fix: replace in-process projection runner with polling-based consumption") explicitly moved away from same-transaction processing. The PADR was not updated.

**M5. Three Effectively Superseded PADRs Not Marked (Item #10, Source: 6A)**

- PADR-109 (Sync projections) superseded by polling-based approach (commit `93d2192`)
- PADR-120 (Manual middleware ordering) superseded by PADR-122 priority bands
- PADR-101 (Vertical slices) not followed in praecepta's package-per-bounded-context layout

**M6. PADR Quality Inconsistencies (Item #12, Source: 6A)**

- 8+ PADRs retain `{Project}` placeholders (e.g., `PADR-111-classvar-aggregate-type-discrimination.md:41`, `PADR-121-projection-based-authentication.md:279`, `PADR-120-multi-auth-middleware-sequencing.md:208`)
- 15+ PADRs lack a "Key Files" section (only PADR-122 has one)
- Inconsistent metadata format: some use `**Deciders:**`, others `**Author:**`
- No "Date Updated" field in any PADR

**M7. No Domain Routers Registered (Item #18, Source: 6B)**

Neither `praecepta-domain-tenancy` nor `praecepta-domain-identity` registers `praecepta.routers` entry points. The only router entry point is the health stub in `praecepta-infra-fastapi` (`packages/infra-fastapi/pyproject.toml:29`). The `GROUP_ROUTERS` discovery mechanism in `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:30` is functionally untested with real domain routers.

**M8. TaskIQ Missing Lifecycle Integration (Item #17, Source: 6B)**

`packages/infra-taskiq/pyproject.toml` has no `[project.entry-points]` section. The broker and scheduler at `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:67-81` are not auto-discovered by `create_app()`. Missing: lifespan hook, FastAPI DI sharing, task definition patterns, retry/error handling, observability integration.

**M9. Documentation Site Missing Two Packages (Item #19, Source: 6B)**

`praecepta-infra-taskiq` and `praecepta-integration-tenancy-identity` are absent from `docs/mkdocs.yml` navigation and mkdocstrings plugin paths.

**M10. Test Coverage Gaps (Item #22, Source: 6B)**

Six modules lack dedicated test files:
- `packages/infra-persistence/src/.../redis_client.py`
- `packages/infra-observability/src/.../instrumentation.py`
- `packages/infra-eventsourcing/src/.../projections/rebuilder.py`
- `packages/infra-eventsourcing/src/.../projections/runner.py`
- `packages/infra-auth/src/.../dependencies.py`
- `packages/integration-tenancy-identity/` -- no test directory at all

**M11. Cross-Package Wiring Gaps (Item #24, Source: 6B)**

Three packages register no entry points: `infra-persistence`, `infra-taskiq`, and `integration-tenancy-identity`. Additionally, only 4 of 6 documented entry-point groups (`praecepta.routers`, `.middleware`, `.error_handlers`, `.lifespan`) are consumed by `create_app()` at `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:30-33`. The `praecepta.applications` and `praecepta.projections` groups are wired through separate mechanisms.

**M12. Stub Pattern Detection (Item #21, Source: 6B)**

While the codebase has zero `NotImplementedError` and zero `TODO`/`FIXME` markers (a positive signal), the 29 `...` occurrences and 7 `pass` statements are all either Protocol method bodies, docstring examples, or intentional no-ops. The single true stub is the integration package.

## Low & Info Findings

**Low severity items** include: foundation layer PADRs are well-implemented with minor gaps such as the missing `ValidationResult` type from PADR-113 (Item #2); infrastructure, auth, and domain layer PADRs are fully or nearly fully implemented (Items #3, #4, #5); the KB manifest, search index, and domain briefs are accurate and comprehensive (Items #13, #14, #15); CLAUDE.md is accurate except for the stale version number "0.1.0" vs actual "0.3.0" at `pyproject.toml:3` (Item #20); the single dog_school example is well-crafted but covers only a narrow slice of capabilities and uses an in-memory store rather than event sourcing (Item #23).

**Info severity items** include: architecture PADRs (102, 107, 122) are exemplary -- PADR-122 is the gold standard with Key Files section mapping to implementation (Item #6); foundation packages correctly have no entry points as they provide primitives, not contributions.

## Cross-Cutting Themes

### Theme 1: Architectural Intent Outpaces Implementation Delivery

The monorepo has thorough architectural documentation (25 PADRs, 9 domain briefs, enforced boundary contracts) but implementation completeness trails behind. Nine PADR-specified features have zero implementation, five are partial, and one entire package (integration) is a stub. The framework's "pre-alpha" status explains this, but the gap between documented architecture and working code is wider than the maturity labels suggest.

### Theme 2: Decision Lifecycle Management Is Neglected

PADRs are written but not maintained. 19 of 25 have stale status fields, 3 are effectively superseded without any status update, 8+ retain source-project `{Project}` placeholders, and 7 significant decisions have no PADR at all. The most consequential is PADR-109, whose synchronous projection guarantee was explicitly reversed in commit `93d2192` without updating the PADR. The decision record functions as a write-once artifact rather than a living document.

### Theme 3: Peripheral Packages Lag Behind Core

A clear two-tier maturity pattern emerges. Core packages (foundation-domain, foundation-application, infra-fastapi, infra-eventsourcing, infra-auth, domain-tenancy, domain-identity) are well-implemented, tested, and wired into auto-discovery. Peripheral packages (infra-taskiq, infra-persistence, integration-tenancy-identity) lack entry points, have minimal tests, and are absent from documentation. This creates a reliable core surrounded by incomplete scaffolding.

### Theme 4: Consumer-Facing Surfaces Are Underdeveloped

The framework lacks the surfaces that downstream consumers would need: no domain REST routers are registered (only the health stub exercises router auto-discovery), only one example exists (using an in-memory store rather than real event sourcing), and critical consumer patterns (projections, multi-auth, feature flags, task scheduling) have no example coverage. The framework is architecturally sound but not yet approachable for new adopters.

## Strengths

1. **Architecture PADRs are exemplary (5/5).** PADR-102 (hexagonal architecture) is enforced by `import-linter` contracts at `pyproject.toml:184-215`. PADR-122 (entry-point auto-discovery) is the gold standard -- thoroughly implemented across 7 packages with priority bands, contribution dataclasses, and a well-structured `create_app()` factory at `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:36-157`.

2. **Zero deferred-work markers.** No `NotImplementedError`, `TODO`, `FIXME`, `HACK`, or `XXX` markers exist anywhere in source files under `packages/*/src/`. The only true stub is the integration package's `__init__.py`. This indicates deliberate architectural interfaces (Protocol `...` bodies) rather than deferred work.

3. **KB layer is accurate and well-maintained (4/5 average).** The manifest, search index, domain briefs, and CLAUDE.md all accurately reflect codebase reality. All 11 keyword rows in `_kb/SEARCH_INDEX.md` resolve to valid paths, and recently added concepts (MiddlewareContribution, LifespanContribution, RequestContext) are properly indexed.

4. **Auth and security PADRs are fully implemented (4/5).** JWT auth with JWKS (`packages/infra-auth/src/praecepta/infra/auth/middleware/jwt_auth.py:60-345`), multi-auth middleware sequencing (priority-based, evolved beyond PADR spec), JIT user provisioning (`packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:31-145`), and projection-based API key lookup are all complete.

5. **Boundary enforcement is automated.** The 4-layer dependency hierarchy is not merely documented -- it is machine-enforced via `import-linter` contracts and exercised through `make boundaries`. This prevents architectural erosion as the codebase grows.

## Recommendations

**P1 -- Address Before Next Milestone**

1. **Create PADR for polling-based projection consumption.** The shift from PADR-109's synchronous approach to `ProjectionPoller` (commit `93d2192`) is the most significant undocumented decision. Draft a new PADR documenting the motivation, trade-offs (eventual consistency gap), polling interval configuration, and mark PADR-109 as superseded. Reference: `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:80-147`.

2. **Implement or descope the integration package.** `packages/integration-tenancy-identity/` is listed as a first-class package but contributes nothing. Either implement a minimal cross-domain saga (e.g., auto-provision identity context on tenant creation) with tests and entry points, or remove it from the package table and mark it as a future milestone.

3. **Reconcile PADR statuses.** Run a single pass to update all 25 PADR files to match their actual status. The 6 fully implemented PADRs should be "Accepted." PADRs describing source-project patterns not applicable to praecepta (108, 111, 112) should be marked "Not Applicable" or "Informational." Superseded PADRs (109, 120) should be marked "Superseded" with references to their replacements.

**P2 -- Address Within Current Phase**

4. **Add at least one domain router.** Register a `praecepta.routers` entry point from `praecepta-domain-tenancy` to validate that router auto-discovery works end-to-end with a real domain context, not just the health stub.

5. **Wire TaskIQ into app lifecycle.** Add `[project.entry-points]` to `packages/infra-taskiq/pyproject.toml` with a `praecepta.lifespan` entry for broker startup/shutdown. This would bring the package from scaffolding to functional.

6. **Replace `{Project}` placeholders.** Systematically replace the 8+ `{Project}` placeholder references in PADRs with praecepta-specific namespace paths. This is a low-effort, high-trust improvement.

7. **Expand example coverage.** Add a second example demonstrating event sourcing with projection handling, multi-auth configuration, and real persistence (PostgreSQL event store). The current dog_school example uses `_dogs: dict[UUID, Dog] = {}` at `examples/dog_school/router.py:21`, which does not demonstrate the framework's core value proposition.

**P3 -- Address When Convenient**

8. **Add "Key Files" sections to PADRs.** Following PADR-122's model, add implementation file references to the 15+ PADRs that lack them. This improves navigability between decisions and code.

9. **Add missing packages to documentation site.** Include `praecepta-infra-taskiq` and `praecepta-integration-tenancy-identity` in `docs/mkdocs.yml` navigation and mkdocstrings paths.

10. **Update CLAUDE.md version.** Change "pre-alpha (v0.1.0)" to match `pyproject.toml:3` version "0.3.0".

11. **Create PADRs for remaining undocumented decisions.** PEP 420 implicit namespaces, BaseAggregate multi-tenancy convention, dev bypass authentication pattern, and ContextVar design are architecturally significant enough to warrant standalone PADRs.

12. **Add test files for uncovered modules.** Priority targets: `packages/infra-persistence/src/.../redis_client.py`, `packages/infra-observability/src/.../instrumentation.py`, `packages/infra-eventsourcing/src/.../projections/rebuilder.py`, `packages/infra-eventsourcing/src/.../projections/runner.py`.
