# KB Coverage & Stub Detection — Completeness & Gaps

**Collector ID:** 6B
**Dimension:** Completeness & Gaps
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. KB Manifest Accuracy

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The `_kb/MANIFEST.md` accurately describes the current KB structure. All 9 domain briefs listed in the manifest correspond to actual files on disk. The 4 strategic and 21 pattern PADRs listed in `_kb/decisions/_index.md` match the 25 actual PADR files found. Cross-cutting constraints (import-boundaries, async-strategy, multi-tenancy, event-sourcing) are documented and enforced in the codebase. The collections and tools sections are accurate.

**Findings:**

| Area | Status | Notes |
|------|--------|-------|
| Domain brief count (9) | Accurate | All 9 briefs exist at listed paths |
| PADR count (25 = 4+21) | Accurate | `_kb/decisions/_index.md:3` says "25 PADRs (4 strategic + 21 pattern)" and 25 files exist |
| Cross-cutting constraints | Accurate | Import boundaries enforced via `pyproject.toml:184-215`, async strategy consistent |
| Design collection | Accurate | `_kb/design/BRIEF.md` exists with 7 references |
| Tools section | Accurate | SEARCH_INDEX.md exists and functional |

Minor gap: The manifest does not mention the `_kb/decisions/_index.md` file in its Collections table, only referencing it indirectly (`decisions/_index.md:1`). This is not a significant issue since the index is reachable from the collections row.

---

## 2. KB Search Index

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The `_kb/SEARCH_INDEX.md` search index accurately maps keywords to domain briefs. All 11 keyword rows resolve to valid brief paths. The keyword coverage is comprehensive for the project's domain vocabulary.

**Findings:**

| Keyword Row | Brief Path | Valid? |
|-------------|-----------|--------|
| aggregate, entity, value object... | `domains/ddd-patterns/BRIEF.md` | Yes |
| event sourcing, event store... | `domains/event-store-cqrs/BRIEF.md` | Yes |
| tenant, multi-tenancy, RLS... | `domains/multi-tenancy/BRIEF.md` | Yes |
| FastAPI, route, endpoint... | `domains/api-framework/BRIEF.md` | Yes |
| JWT, JWKS, OIDC... | `domains/security/BRIEF.md` | Yes |
| logging, tracing, metrics... | `domains/observability/BRIEF.md` | Yes |
| test, pytest, fixture... | `domains/test-strategy/BRIEF.md` | Yes |
| PostgreSQL, Redis, Neo4j... | `domains/infrastructure/BRIEF.md` | Yes |
| deploy, Docker Compose... | `domains/deployment/BRIEF.md` | Yes |
| constitution, governance... | `design/BRIEF.md` | Yes |
| ADR, PADR, decision... | `decisions/_index.md` | Yes |

No broken references found. Keywords added in recent work (e.g., `MiddlewareContribution`, `LifespanContribution`, `RequestContext`) are properly indexed in the api-framework row (`_kb/SEARCH_INDEX.md:13`).

---

## 3. Domain Brief Coverage

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Domain briefs exist for all 9 knowledge domains and accurately describe the architectural patterns used. However, the briefs describe conceptual bounded contexts rather than directly mapping 1:1 to the 11 implementation packages. There is no "identity" or "tenancy" specific BRIEF -- these are covered under "multi-tenancy" and "security" respectively.

**Findings:**

| Bounded Context (Package) | Matching KB Brief | Accuracy |
|---------------------------|-------------------|----------|
| praecepta-domain-tenancy | `_kb/domains/multi-tenancy/BRIEF.md` | Good -- covers tenant lifecycle, RLS, context propagation |
| praecepta-domain-identity | `_kb/domains/security/BRIEF.md` | Partial -- identity is implicitly covered under security (JWT, OIDC, JIT provisioning) |
| praecepta-infra-fastapi | `_kb/domains/api-framework/BRIEF.md` | Good -- covers auto-discovery, middleware, error handling |
| praecepta-infra-eventsourcing | `_kb/domains/event-store-cqrs/BRIEF.md` | Good -- covers event store, projections, CQRS |
| praecepta-infra-auth | `_kb/domains/security/BRIEF.md` | Good -- covers JWT, JWKS, multi-auth |
| praecepta-infra-persistence | `_kb/domains/infrastructure/BRIEF.md` | Good -- covers PostgreSQL, Redis |
| praecepta-infra-observability | `_kb/domains/observability/BRIEF.md` | Good |
| praecepta-infra-taskiq | `_kb/domains/infrastructure/BRIEF.md` | Partial -- TaskIQ briefly mentioned under Redis |
| praecepta-foundation-domain | `_kb/domains/ddd-patterns/BRIEF.md` | Good |
| praecepta-foundation-application | `_kb/domains/ddd-patterns/BRIEF.md` | Partial -- application layer patterns spread across multiple briefs |
| praecepta-integration-tenancy-identity | No dedicated brief | Missing -- no brief covers the integration layer specifically |

The integration package (`praecepta-integration-tenancy-identity`) has no KB brief coverage, though this is partly because the package is itself a stub (see item 4).

---

## 4. Integration Package Status

**Rating: 1/5 -- Not Implemented**
**Severity:** High | **Confidence:** High

The `praecepta-integration-tenancy-identity` package is a pure stub. It contains a single `__init__.py` file with only a docstring and no implementation code. There are no tests, no entry point registrations, no source modules beyond the init file, and no KB documentation covering what this package should eventually contain.

**Findings:**

| File | Content | Status |
|------|---------|--------|
| `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` | `"""Praecepta Integration Tenancy-Identity -- cross-domain sagas and subscriptions."""` | Docstring only, no exports |
| `packages/integration-tenancy-identity/pyproject.toml:1-24` | Dependencies on tenancy + identity packages, no entry points | No entry point registrations |
| `packages/integration-tenancy-identity/tests/` | Directory does not exist | No tests at all |

**What is missing:**
- Cross-domain saga handlers (e.g., auto-provisioning a user identity when a tenant is created)
- Event subscriptions wiring tenancy events to identity actions
- Entry point registrations for `praecepta.projections` or `praecepta.lifespan`
- Any test coverage
- KB brief or reference documentation

---

## 5. TaskIQ Package Completeness

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

The `praecepta-infra-taskiq` package has a real but minimal implementation. It provides a properly configured Redis Stream broker, result backend, and scheduler with dual schedule sources. The implementation is functional but narrow in scope -- it only provides broker factory configuration, not any of the higher-level patterns that production use would require.

**Findings:**

| Component | File | Status |
|-----------|------|--------|
| Broker factory | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:67-69` | Implemented -- RedisStreamBroker with result backend |
| Result backend | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:61-64` | Implemented -- 1hr TTL |
| Scheduler | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:75-81` | Implemented -- dual sources (label + Redis list) |
| Unit tests | `packages/infra-taskiq/tests/test_broker.py:1-49` | 5 tests covering type assertions and env parsing |
| Entry points | `packages/infra-taskiq/pyproject.toml` | None registered |
| Lifespan hook | N/A | Missing -- no startup/shutdown integration |
| FastAPI DI sharing | N/A | Missing -- taskiq-fastapi integration not wired |
| Task definition patterns | N/A | Missing -- no reusable task decorators or patterns |
| Retry/error handling | N/A | Missing |
| Observability integration | N/A | Missing -- no tracing spans for tasks |

The package has no entry points registered in its `pyproject.toml`, meaning it is not auto-discovered by `create_app()`. The PADR-005 (Task Queue) decision references TaskIQ but the implementation gap between the decision and the code is significant.

---

## 6. Missing Router Implementations

**Rating: 2/5 -- Initial**
**Severity:** Medium | **Confidence:** High

Neither `praecepta-domain-tenancy` nor `praecepta-domain-identity` register any `praecepta.routers` entry points. These packages register `praecepta.applications` and `praecepta.projections` entry points but have no API router modules. The only router entry point in the entire codebase is the health stub in `praecepta-infra-fastapi`.

**Findings:**

| Package | `praecepta.routers` Entry Point | Router Module | Status |
|---------|-------------------------------|---------------|--------|
| praecepta-infra-fastapi | `_health_stub` (`packages/infra-fastapi/pyproject.toml:29`) | `_health.py` | Health endpoint only |
| praecepta-domain-tenancy | None | No `api/` or `router.py` module exists | Missing |
| praecepta-domain-identity | None | No `api/` or `router.py` module exists | Missing |
| praecepta-integration-tenancy-identity | None | Entire package is stub | Missing |

The KB brief for api-framework (`_kb/domains/api-framework/BRIEF.md:11`) states "Routers: Per-context router, mounted on main app" and the DDD patterns BRIEF (`_kb/domains/ddd-patterns/BRIEF.md:28-30`) shows an expected `api/` directory in each context. Neither domain package follows this convention. The only working example of a router is in `examples/dog_school/router.py`, which is passed via `extra_routers` rather than entry-point discovery.

This means the auto-discovery system for routers (`GROUP_ROUTERS` in `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:30`) is functionally untested with real domain routers -- only the health stub exercises it.

---

## 7. Documentation Site Coverage

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

The mkdocs.yml navigation covers 9 of 11 packages in the API Reference section. Two packages are completely absent from documentation: `praecepta-infra-taskiq` and `praecepta-integration-tenancy-identity`. The mkdocstrings plugin paths list also omits these two packages.

**Findings:**

| Package | In mkdocs nav? | In mkdocstrings paths? | Doc file exists? |
|---------|---------------|----------------------|-----------------|
| foundation-domain | Yes (`docs/mkdocs.yml:34`) | Yes (`docs/mkdocs.yml:51`) | Yes |
| foundation-application | Yes (`docs/mkdocs.yml:35`) | Yes (`docs/mkdocs.yml:52`) | Yes |
| infra-fastapi | Yes (`docs/mkdocs.yml:36`) | Yes (`docs/mkdocs.yml:53`) | Yes |
| infra-eventsourcing | Yes (`docs/mkdocs.yml:37`) | Yes (`docs/mkdocs.yml:54`) | Yes |
| infra-auth | Yes (`docs/mkdocs.yml:38`) | Yes (`docs/mkdocs.yml:55`) | Yes |
| infra-persistence | Yes (`docs/mkdocs.yml:39`) | Yes (`docs/mkdocs.yml:56`) | Yes |
| infra-observability | Yes (`docs/mkdocs.yml:40`) | Yes (`docs/mkdocs.yml:57`) | Yes |
| infra-taskiq | **No** | **No** | **No** |
| domain-tenancy | Yes (`docs/mkdocs.yml:41`) | Yes (`docs/mkdocs.yml:58`) | Yes |
| domain-identity | Yes (`docs/mkdocs.yml:42`) | Yes (`docs/mkdocs.yml:59`) | Yes |
| integration-tenancy-identity | **No** | **No** | **No** |

Additionally, the docs site lacks some guide pages referenced in the nav. All nav-listed `.md` files do appear to exist under `docs/docs/`, so the site builds cleanly. The missing packages align with the least-implemented packages (items 4 and 5 above).

---

## 8. CLAUDE.md Accuracy

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

CLAUDE.md is substantially accurate. The package table lists all 11 packages correctly. The 4-layer hierarchy, PEP 420 conventions, entry-point groups, and code style rules all match the codebase reality. The version is described as "pre-alpha (v0.1.0)" in `CLAUDE.md:7` but the root `pyproject.toml:3` shows `version = "0.3.0"`.

**Findings:**

| CLAUDE.md Claim | Actual State | Verdict |
|----------------|-------------|---------|
| "11 packages" (`CLAUDE.md:7`) | 11 packages in `pyproject.toml:18-30` | Accurate |
| "pre-alpha (v0.1.0)" (`CLAUDE.md:7`) | `pyproject.toml:3`: `version = "0.3.0"`, classifier: "2 - Pre-Alpha" | **Stale** -- version is 0.3.0 not 0.1.0 |
| 4-layer hierarchy (`CLAUDE.md:34-38`) | Enforced by import-linter in `pyproject.toml:184-215` | Accurate |
| PEP 420 namespace (`CLAUDE.md:46-58`) | Verified -- no `__init__.py` in intermediate namespace dirs | Accurate |
| Entry point groups (6 listed, `CLAUDE.md:69-74`) | All 6 used in `app_factory.py:30-33` (4 directly) + discovery | Accurate |
| Package table (11 entries, `CLAUDE.md:78-90`) | All match directory structure | Accurate |
| `make verify` command (`CLAUDE.md:12`) | Makefile target would run lint + typecheck + boundaries + test | Accurate |
| Accepted exception for domain->infra-eventsourcing (`CLAUDE.md:43`) | Domain packages do import from infra-eventsourcing | Accurate |

The only stale entry is the version number (0.1.0 vs 0.3.0).

---

## 9. Stub Pattern Detection

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Searching across all `packages/*/src/**/*.py` files reveals a moderate number of stub-like patterns. Most are intentional (Protocol method bodies using `...`, exception handling `pass` clauses) rather than unimplemented functionality. The integration package is the only true "empty stub."

**Findings:**

### `pass` statements in source (7 occurrences)

| File:Line | Context | Stub? |
|-----------|---------|-------|
| `packages/infra-taskiq/src/.../broker.py:22` | Example in docstring: `async def hourly_task() -> None: pass` | No -- docstring example |
| `packages/infra-observability/src/.../instrumentation.py:15` | Example in docstring: `async def append_events(...): pass` | No -- docstring example |
| `packages/infra-eventsourcing/src/.../projections/base.py:20` | Default singledispatch handler: `def policy(...): pass` | No -- intentional no-op for unhandled events |
| `packages/infra-eventsourcing/src/.../projections/rebuilder.py:23` | Example in docstring | No -- docstring example |
| `packages/infra-eventsourcing/src/.../projections/runner.py:17` | Example in docstring | No -- docstring example |
| `packages/infra-fastapi/src/.../middleware/request_id.py:140` | Exception handler: `except Exception: pass` | No -- intentional silent catch |
| `packages/infra-fastapi/src/.../middleware/request_id.py:150` | Exception handler: `except Exception: pass` | No -- intentional silent catch |

### Ellipsis (`...`) in source (29 occurrences)

| Category | Count | Examples | Stub? |
|----------|-------|---------|-------|
| Protocol method bodies | 20 | `config_service.py:31,35,45,57,61,65,69`, `dependencies.py:16,19,73`, `feature_flags.py:44`, `database.py:13,19`, `llm_service.py:60,98`, `api_key_generator.py:33,37,52,64,75` | No -- standard Protocol pattern |
| Abstract method bodies | 3 | `aggregates.py:67,71,91` | No -- docstring example in BaseAggregate |
| Event class body | 1 | `events.py:209` | No -- class body in example |
| Projection abstract method | 2 | `poller.py:22`, `base.py:151` | No -- abstract interface |
| FastAPI dependency protocol | 3 | `feature_flags.py:15`, `resource_limits.py:25` | No -- Protocol pattern |

### `NotImplementedError` (0 occurrences)

No `raise NotImplementedError` found anywhere in source code.

### `TODO`/`FIXME`/`HACK`/`XXX` (0 occurrences)

No TODO or FIXME markers found in any source files under `packages/*/src/`.

### True stubs (1 package)

| Package | Status |
|---------|--------|
| `packages/integration-tenancy-identity/src/.../tenancy_identity/__init__.py:1` | Single docstring, no implementation |

---

## 10. Test Coverage Gaps

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Most source modules have corresponding test files, but there are notable gaps. The analysis below compares source modules (excluding `__init__.py` and `py.typed`) against test files in each package.

**Findings:**

| Package | Source Modules | Test Files | Untested Modules |
|---------|---------------|------------|-----------------|
| foundation-domain | 13 (incl. ports/) | 7 | `config_defaults.py`, `policy_types.py`, `tenant_value_objects.py`, `user_value_objects.py`, `agent_value_objects.py` (some may be covered by `test_value_objects.py`) |
| foundation-application | 7 | 7 | Fully covered |
| infra-fastapi | 9 (incl. middleware/, deps/) | 10 | Fully covered |
| infra-eventsourcing | 9 (incl. projections/) | 8 | `projections/rebuilder.py`, `projections/runner.py` -- no dedicated test files |
| infra-auth | 7 (incl. middleware/) | 8 | `dependencies.py` has no dedicated test file |
| infra-persistence | 5 | 4 | `redis_client.py` -- no test file |
| infra-observability | 4 | 3 | `instrumentation.py` -- no test file |
| infra-taskiq | 1 | 1 | Covered |
| domain-tenancy | 8 (incl. infra/) | 8 | Fully covered |
| domain-identity | 10 (incl. infra/) | 9 | `agent_api_key_repository.py` and `user_profile_repository.py` may lack direct tests (covered by projection tests) |
| integration-tenancy-identity | 0 (stub) | 0 | **Entire package untested** |

**Key gaps:**
- `packages/infra-persistence/src/.../redis_client.py` -- No test file (`test_redis_client.py` does not exist)
- `packages/infra-observability/src/.../instrumentation.py` -- No test file (`test_instrumentation.py` does not exist)
- `packages/infra-eventsourcing/src/.../projections/rebuilder.py` -- No test file
- `packages/infra-eventsourcing/src/.../projections/runner.py` -- No test file
- `packages/infra-auth/src/.../dependencies.py` -- No dedicated test (though may be exercised indirectly via integration tests)
- `packages/integration-tenancy-identity/` -- No test directory at all

Root-level integration tests exist in `tests/` (5 test files) covering app factory, middleware, dog school example, and error handling integration.

---

## 11. Example Completeness

**Rating: 3/5 -- Defined**
**Severity:** Low | **Confidence:** High

The `examples/` directory contains a single example (`dog_school/`) with 4 files. This example is well-crafted and demonstrates the core consumer pattern (domain aggregate, router, app factory wiring). However, it is the only example and covers only a narrow slice of framework capabilities.

**Findings:**

| Example | Files | Demonstrates |
|---------|-------|-------------|
| `examples/dog_school/` | `__init__.py`, `domain.py`, `app.py`, `router.py` | Aggregate definition, router creation, `create_app()` wiring, tenant context, entry-point exclusion |

**Not covered by any example:**
- Projection definition and event handling
- Integration test patterns
- Multi-auth middleware configuration
- TaskIQ task definition and scheduling
- Real event sourcing with event store persistence
- Feature flag usage in endpoints
- Resource limit enforcement
- Custom lifespan hooks
- Custom error handler registration
- Multi-package composition (multiple domain contexts)

The dog school example uses an in-memory store (`examples/dog_school/router.py:21`: `_dogs: dict[UUID, Dog] = {}`) rather than actual event sourcing persistence, which limits its pedagogical value for the framework's primary use case.

---

## 12. Cross-Package Wiring Gaps

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

The entry-point auto-discovery system is well-designed and functional for the packages that participate. However, several packages do not register any entry points, and some expected contribution types are missing across the board.

**Findings:**

### Entry Point Registrations by Package

| Package | `.applications` | `.projections` | `.middleware` | `.lifespan` | `.routers` | `.error_handlers` |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|
| infra-fastapi | -- | -- | 3 | -- | 1 | 1 |
| infra-auth | -- | -- | 2 | -- | -- | -- |
| infra-observability | -- | -- | 1 | 1 | -- | -- |
| infra-eventsourcing | -- | -- | -- | 2 | -- | -- |
| infra-persistence | -- | -- | -- | -- | -- | -- |
| infra-taskiq | -- | -- | -- | -- | -- | -- |
| domain-tenancy | 1 | 2 | -- | -- | -- | -- |
| domain-identity | 2 | 2 | -- | -- | -- | -- |
| integration-tenancy-identity | -- | -- | -- | -- | -- | -- |
| foundation-domain | -- | -- | -- | -- | -- | -- |
| foundation-application | -- | -- | -- | -- | -- | -- |

### Wiring Gaps

| Gap | Severity | Details |
|-----|----------|---------|
| No domain routers registered | Medium | Neither domain package registers `praecepta.routers` -- applications have no REST API endpoints discoverable via entry points |
| infra-persistence has no entry points | Low | Database session factory and RLS helpers are imported directly, not auto-discovered. Could benefit from a lifespan hook for engine disposal |
| infra-taskiq has no entry points | Medium | Broker/scheduler not integrated into app lifecycle; `packages/infra-taskiq/pyproject.toml` has no `[project.entry-points]` section |
| integration package has no entry points | High | `packages/integration-tenancy-identity/pyproject.toml:1-24` -- no entry points declared at all, package is inert |
| `praecepta.applications` not consumed by app_factory | Info | The `app_factory.py` discovers routers, middleware, error_handlers, and lifespan but does NOT discover `praecepta.applications` -- application singletons are wired via separate mechanism (FastAPI Depends) |
| Foundation packages have no entry points | Info | Expected -- foundation layer provides primitives, not contributions |

The `create_app()` function in `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:30-33` defines 4 group constants (`GROUP_ROUTERS`, `GROUP_MIDDLEWARE`, `GROUP_ERROR_HANDLERS`, `GROUP_LIFESPAN`) but `praecepta.applications` and `praecepta.projections` are not consumed by the app factory. The CLAUDE.md (`CLAUDE.md:69-74`) lists 6 entry point groups, but only 4 are wired in the factory. Applications are resolved via `Depends()` and projections via the projection runner lifespan hook, which is a deliberate design choice per PADR-110 and the projection poller architecture.

---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | KB Manifest Accuracy | 4/5 | Low |
| 2 | KB Search Index | 4/5 | Low |
| 3 | Domain Brief Coverage | 4/5 | Low |
| 4 | Integration Package Status | 1/5 | High |
| 5 | TaskIQ Package Completeness | 3/5 | Medium |
| 6 | Missing Router Implementations | 2/5 | Medium |
| 7 | Documentation Site Coverage | 3/5 | Medium |
| 8 | CLAUDE.md Accuracy | 4/5 | Low |
| 9 | Stub Pattern Detection | 3/5 | Medium |
| 10 | Test Coverage Gaps | 3/5 | Medium |
| 11 | Example Completeness | 3/5 | Low |
| 12 | Cross-Package Wiring Gaps | 3/5 | Medium |

**Overall Assessment:** The KB and documentation layer is well-maintained (items 1-3, 8 scoring 4/5). The primary gaps are in implementation completeness: the integration package is a pure stub (item 4, 1/5), domain packages lack REST API routers (item 6, 2/5), and several infrastructure packages have incomplete entry-point wiring (item 12). The codebase has zero `NotImplementedError`, zero `TODO`/`FIXME` markers, and the `...` patterns are exclusively Protocol method bodies, indicating deliberate architectural interfaces rather than deferred work. The most actionable improvements would be implementing the integration package, adding domain routers, and completing TaskIQ lifecycle integration.
