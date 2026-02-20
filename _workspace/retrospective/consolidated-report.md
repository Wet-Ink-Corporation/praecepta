# Praecepta Codebase Quality Audit -- Consolidated Report

**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)
**Baseline:** make verify -- ALL GREEN (815 tests pass, 0 lint/type/boundary issues)

---

## Executive Summary

The Praecepta monorepo is a well-architected DDD/Event Sourcing framework with strong foundations. Its 4-layer package hierarchy is machine-enforced by import-linter contracts, PEP 420 implicit namespaces are flawlessly applied across all 11 packages, and the entry-point auto-discovery system (PADR-122) provides a clean, extensible plugin architecture with 20 active entry points across 6 groups. The baseline `make verify` passes cleanly: 815 tests, zero lint violations, zero type errors, and zero boundary violations. The domain model quality is high where implemented -- the Tenant aggregate is a reference-grade event-sourced lifecycle implementation, the exception hierarchy is exemplary (5/5), and concurrency-safe registration patterns (SlugRegistry, OidcSubRegistry) demonstrate sophisticated engineering. Code-level developer experience is excellent, with 100% docstring coverage, ergonomic imports, full PEP 561 compliance, and production-grade RFC 7807 error handling.

The primary risk is that architectural intent outpaces implementation delivery. Nine features specified in PADRs have zero implementation, the integration package (Layer 3) is a complete stub, no domain package registers REST routers, and the TaskIQ package bypasses every infrastructure convention. PADR lifecycle management is systematically neglected: 19 of 25 PADRs have stale status fields, and the most consequential architectural change (polling-based projections replacing synchronous projections, commit `93d2192`) has no corresponding PADR. Developer onboarding documentation lags significantly behind code quality -- there is no changelog, no CONTRIBUTING.md, no example README, and published guides contain factual errors including an incorrect HTTP status code mapping and a constructor call that would raise a TypeError at runtime.

The codebase sits at a "Managed-to-Defined" maturity level (overall average 3.7/5), appropriate for its pre-alpha stage but with specific gaps that should be addressed before broader adoption. The core packages (foundation, infra-fastapi, infra-eventsourcing, infra-auth, domain-tenancy, domain-identity) are well-implemented and tested; the peripheral packages (infra-taskiq, infra-persistence, integration-tenancy-identity) need significant completion work. The strongest areas are architectural enforcement, error handling, and aggregate design. The weakest areas are documentation freshness, PADR lifecycle management, and consumer-facing surfaces (examples, routers, onboarding materials).

The overall assessment is AMBER-RED: no blocking defects exist, the baseline is clean, and the core is solid, but the accumulated weight of 8 High-severity findings across documentation, completeness, and convention compliance creates meaningful adoption risk that should be systematically addressed.

## Overall RAG Status: RED

The overall RAG is the worst of all dimensional RAGs. Dimension 5 (Developer Experience) rates RED due to 3 High-severity findings related to missing changelog, absent example documentation, and incorrect error documentation. The conservative (worst-case) approach mandates an overall RED despite five dimensions rating AMBER. This reflects the reality that developer onboarding barriers -- factual errors in guides, missing run instructions, no changelog across 3 version bumps -- represent tangible adoption blockers even when the underlying code quality is strong.

## Dimensional Scorecard

| # | Dimension | RAG | Avg Maturity | Critical | High | Medium | Low |
|---|-----------|-----|:------------:|:--------:|:----:|:------:|:---:|
| 1 | Architecture Compliance | AMBER | 4.4 | 0 | 1 | 11 | 14 |
| 2 | Domain Model Quality | AMBER | 3.8 | 0 | 1 | 12 | 18 |
| 3 | Convention & Standards | AMBER | 4.0 | 0 | 1 | 7 | 9 |
| 4 | Test Quality | AMBER | 3.9 | 0 | 0 | 9 | 11 |
| 5 | Developer Experience | RED | 3.7 | 0 | 3 | 15 | 7 |
| 6 | Completeness & Gaps | AMBER | 3.2 | 0 | 2 | 12 | 6 |
| | **Overall** | **RED** | **3.8** | **0** | **8** | **66** | **65** |

## Cross-Cutting Themes

### Theme 1: Architectural Intent Outpaces Implementation Delivery

- **Dimensions affected:** 1, 2, 3, 6
- **Summary:** The monorepo has thorough architectural documentation and well-designed extension points, but many specified features remain unimplemented or stubbed. The architecture is sound; the execution is incomplete.
- **Impact:** Downstream consumers cannot rely on documented capabilities. The gap between architecture diagrams (which show 11 functional packages) and reality (where 3 packages are incomplete) creates false expectations.
- **Examples:**
  - Integration package is a pure stub with no code, tests, or entry points: `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` (Dim 2 H-1, Dim 6 H2)
  - Nine PADR-specified features have zero implementation including vertical slices, ValidationResult, RLS migrations, integration sagas (Dim 6 M2)
  - `praecepta.subscriptions` entry-point group documented in PADR-122 but no package declares entries and no consumer code exists (Dim 1 M5)
  - Cascade deletion is a stub that logs but does not delete: `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/cascade_deletion.py:76-84` (Dim 2 M-6)

### Theme 2: Documentation Drift and Factual Errors

- **Dimensions affected:** 1, 2, 5, 6
- **Summary:** Documentation has not kept pace with code evolution. Version numbers are stale, guide examples contain errors that would fail at runtime, PADR statuses are unreliable, and critical onboarding documents are absent.
- **Impact:** Developers who trust documentation over code will encounter runtime failures. The decision record cannot be used as a reliable source of truth. Onboarding friction is unnecessarily high.
- **Examples:**
  - `CLAUDE.md:7` states "v0.1.0" but all `pyproject.toml` files show `version = "0.3.0"` (Dim 1 M9, Dim 5 M-15, Dim 6 M9 via item #20)
  - `docs/docs/guides/add-api-endpoint.md:66` says `ValidationError` maps to 400, but code returns 422 at `error_handlers.py:259` (Dim 5 H-3)
  - `docs/docs/guides/add-api-endpoint.md:81` uses incorrect `NotFoundError` constructor that would raise TypeError at runtime (Dim 5 H-3)
  - 19 of 25 PADRs have mismatched statuses between index and actual files (Dim 6 M1)

### Theme 3: Type Safety Gaps at System Boundaries

- **Dimensions affected:** 1, 2, 3, 5
- **Summary:** The codebase has strict internal type discipline (mypy strict mode passes cleanly) but systematically uses `Any` at plugin boundaries, contribution types, and repository return types. This creates a "type-safe core with untyped edges" pattern.
- **Impact:** Runtime type errors can occur at exactly the integration points where they are hardest to diagnose. Mock-based tests (which also lack `spec=`) cannot detect these mismatches.
- **Examples:**
  - `DiscoveredContribution.value` is `Any` at `discovery.py:29`; `ErrorHandlerContribution.handler` is `Any` at `contributions.py:40`; `LifespanContribution.hook` is `Any` at `contributions.py:52` (Dim 1 M1, M2)
  - `compose_lifespan()` returns `object` at `lifespan.py:24` (Dim 1 M3)
  - `dict[str, Any]` return types in `config_service.py:149,198` instead of typed structures (Dim 5 M-4)
  - Duplicate `EventSourcedApplication` Protocol in `issue_api_key.py:20` and `rotate_api_key.py:19` (Dim 5 M-3)

### Theme 4: CI/Local Parity and Enforcement Gaps

- **Dimensions affected:** 1, 3, 4
- **Summary:** The local development experience and CI pipeline have subtle behavioral differences. Quality gates that appear configured are not actually enforced.
- **Impact:** Code that passes local verification can fail in CI (or vice versa). Coverage regressions can merge undetected.
- **Examples:**
  - Coverage threshold `fail_under = 70` in `pyproject.toml:140-149` not enforced in CI -- `--cov-fail-under=70` missing from `.github/workflows/quality.yml:44` (Dim 1 H1)
  - `make verify` auto-fixes code before testing (`Makefile:25-30`) while CI uses check-only flags (`.github/workflows/quality.yml:32-35`) (Dim 1 M7)
  - `asyncio_mode = "strict"` configured in `pyproject.toml:118` but zero async test functions exist anywhere (Dim 4 M3)

### Theme 5: Peripheral Package Immaturity

- **Dimensions affected:** 1, 3, 5, 6
- **Summary:** A clear two-tier maturity pattern exists. Core packages are well-implemented; peripheral packages (infra-taskiq, infra-persistence, integration-tenancy-identity) lag significantly in convention adherence, testing, documentation, and auto-discovery wiring.
- **Impact:** The framework's 11-package architecture creates an expectation of breadth that the peripheral packages do not fulfill. TaskIQ's convention violations could set a negative precedent for future packages.
- **Examples:**
  - TaskIQ bypasses all infrastructure conventions: no Pydantic settings, hardcoded `os.getenv("REDIS_URL")` at `broker.py:57`, module-level instantiation at `broker.py:61-81`, no lifespan integration (Dim 3 H1)
  - Three packages register no entry points: `infra-persistence`, `infra-taskiq`, `integration-tenancy-identity` (Dim 6 M11)
  - Six modules lack dedicated test files including `redis_client.py`, `instrumentation.py`, `rebuilder.py`, `runner.py`, `dependencies.py` (Dim 6 M10)

### Theme 6: Unit-Only Test Strategy Leaves Database Guarantees Unverified

- **Dimensions affected:** 2, 4
- **Summary:** All 815 tests are unit tests with mocked dependencies. No integration tests verify PostgreSQL-level behavior despite the domain model relying heavily on database guarantees.
- **Impact:** Slug uniqueness, OIDC sub uniqueness, RLS tenant isolation, UPSERT idempotency, and projection table operations are unverified at the database level. These are exactly the guarantees that unit tests with mocks cannot validate.
- **Examples:**
  - All tests in `packages/domain-identity/tests/` and `packages/domain-tenancy/tests/` are `@pytest.mark.unit` (Dim 2 M-12)
  - Auth stack and event store excluded from integration fixtures at `tests/conftest.py:16-23` (Dim 4 M7)
  - No test replays a multi-event sequence through projections to verify cumulative read model state (Dim 4 M6)

## All Findings by Severity

### Critical Findings

None.

### High Findings

| # | Dim | ID | Description | File/Location |
|---|-----|----|-------------|---------------|
| H1 | 1 | 1-H1 | Coverage threshold not enforced in CI -- `--cov-fail-under=70` missing | `.github/workflows/quality.yml:44`, `pyproject.toml:140-149` |
| H2 | 2 | 2-H1 | Integration package is a complete stub -- no cross-domain sagas, no tests, no entry points | `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` |
| H3 | 3 | 3-H1 | TaskIQ configuration bypasses all infrastructure conventions -- no Pydantic settings, hardcoded env, module-level instantiation, no lifespan | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:48-81` |
| H4 | 5 | 5-H1 | No changelog or versioning documentation across 3 version bumps (0.1.0 to 0.3.0) | Root directory (missing CHANGELOG.md), `CLAUDE.md:7`, `pyproject.toml:3` |
| H5 | 5 | 5-H2 | Example README and run instructions missing -- no way to discover how to use dog_school | `examples/dog_school/` (missing README.md), `examples/dog_school/app.py:7-11` |
| H6 | 5 | 5-H3 | Incomplete and partially incorrect error documentation -- ValidationError 400 vs 422, NotFoundError constructor TypeError | `docs/docs/guides/add-api-endpoint.md:66,81`, `error_handlers.py:259`, `exceptions.py:95-99` |
| H7 | 6 | 6-H1 | Seven significant architectural decisions have no corresponding PADR (polling projections, PEP 420, BaseAggregate multi-tenancy, dev bypass, ContextVar design, config cache, OIDC sub registry) | Multiple files (see Dim 6 H1 table) |
| H8 | 6 | 6-H2 | Integration package is a pure stub (duplicate of H2, independently identified) | `packages/integration-tenancy-identity/` |

### Medium Findings

**Dimension 1 -- Architecture Compliance (11 findings)**

| # | ID | Description | File/Location |
|---|----|-------------|---------------|
| 1 | 1-M1 | Contribution types use `Any` instead of typed protocols | `contributions.py:40,52` |
| 2 | 1-M2 | `DiscoveredContribution.value` is `Any` -- `discover()` could be generic | `discovery.py:29` |
| 3 | 1-M3 | `compose_lifespan()` return type is `object` | `lifespan.py:24` |
| 4 | 1-M4 | Router mounting only proven with health stub -- no domain routers | `packages/infra-fastapi/pyproject.toml:29` |
| 5 | 1-M5 | `praecepta.subscriptions` entry-point group not implemented | PADR-122 at `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:51` |
| 6 | 1-M6 | Entry-point declarations incomplete for infra-persistence and infra-taskiq | `packages/infra-persistence/pyproject.toml`, `packages/infra-taskiq/pyproject.toml` |
| 7 | 1-M7 | `make verify` auto-fixes before testing, diverging from CI | `Makefile:25-30`, `.github/workflows/quality.yml:32-35` |
| 8 | 1-M8 | No dependency security scanning (pip-audit, safety, Dependabot) | `.github/workflows/` (absent) |
| 9 | 1-M9 | CLAUDE.md version drift: "v0.1.0" vs actual "0.3.0" | `CLAUDE.md:7` |
| 10 | 1-M10 | Docs mkdocstrings paths missing infra-taskiq and integration packages | `docs/mkdocs.yml:50-59` |
| 11 | 1-M11 | import-linter accepted exception (domain->infra-eventsourcing) not explicit in contract | `pyproject.toml:207-215` |

**Dimension 2 -- Domain Model Quality (12 findings)**

| # | ID | Description | File/Location |
|---|----|-------------|---------------|
| 12 | 2-M1 | TenantId/TenantSlug/BaseEvent validation inconsistency -- divergent rules for same concept | `identifiers.py:47`, `tenant_value_objects.py:46`, `events.py:126` |
| 13 | 2-M2 | BaseEvent metadata absent from @event-generated inner event classes | `events.py:117-122`, `tenant.py:60` |
| 14 | 2-M3 | BaseAggregate does not enforce tenant_id assignment | `aggregates.py:104`, `user.py:57`, `agent.py:59` |
| 15 | 2-M4 | Config value constraint metadata (min/max/allowed) not enforced | `config_value_objects.py:59-97` |
| 16 | 2-M5 | Tier 2 (semantic) ValidationResult not codified per PADR-113 | No implementation in foundation-domain |
| 17 | 2-M6 | Cascade deletion is a stub -- logs but does not delete | `cascade_deletion.py:76-84` |
| 18 | 2-M7 | TenantApplication adds minimal domain service value -- bare subclass | `tenant_app.py:17-27` |
| 19 | 2-M8 | Nondeterministic timestamp in Agent event mutator violates ES determinism | `agent.py:196` |
| 20 | 2-M9 | Blocking `time.sleep()` in provisioning retry loop (should be async) | `user_provisioning.py:113` |
| 21 | 2-M10 | Display name derivation logic duplicated between aggregate and projection | `user.py:60-65`, `user_profile.py:66-73` |
| 22 | 2-M11 | Missing lifecycle terminal events for identity aggregates (no deactivation/deletion) | `user.py:17-100`, `agent.py:23-199` |
| 23 | 2-M12 | No integration tests across any domain package -- all unit with mocks | `packages/domain-identity/tests/`, `packages/domain-tenancy/tests/` |

**Dimension 3 -- Convention & Standards (7 findings)**

| # | ID | Description | File/Location |
|---|----|-------------|---------------|
| 24 | 3-M1 | Missing repository and unit-of-work abstractions -- direct SQLAlchemy coupling | `database.py:84-89`, `rls_helpers.py:18-20`, `tenant_context.py:60` |
| 25 | 3-M2 | Projection rebuilder lacks tests and operational documentation | `rebuilder.py:65-177` (no test file exists) |
| 26 | 3-M3 | Router mount convention undefined -- no prefix/tag/versioning policy | `app_factory.py:153`, `_health.py:1-17` |
| 27 | 3-M4 | Development Constitution document missing -- standards scattered | `docs/docs/architecture/development-constitution.md` (does not exist) |
| 28 | 3-M5 | Pydantic settings inconsistencies across infra packages | `redis_settings.py:16-49`, `database.py:98`, `settings.py:93-116` |
| 29 | 3-M6 | Sync/async protocol mismatch in ConfigCache | `config_service.py:48-69` vs `config_cache.py:17-138` |
| 30 | 3-M7 | Duplicate ResourceLimitResult types in foundation and FastAPI layers | `resource_limits.py:25` (foundation) vs `resource_limits.py:44` (fastapi) |

**Dimension 4 -- Test Quality (9 findings)**

| # | ID | Description | File/Location |
|---|----|-------------|---------------|
| 31 | 4-M1 | `redis_client.py` entirely untested (168 LOC) | `packages/infra-persistence/src/.../redis_client.py` |
| 32 | 4-M2 | `instrumentation.py` entirely untested (214 LOC) | `packages/infra-observability/src/.../instrumentation.py` |
| 33 | 4-M3 | Zero direct async test functions despite `asyncio_mode = "strict"` config | `pyproject.toml:118-119`, all test files |
| 34 | 4-M4 | Conftest fixtures defined but unused (dead code) in domain packages | `packages/domain-tenancy/tests/conftest.py`, `packages/domain-identity/tests/conftest.py` |
| 35 | 4-M5 | Untyped `MagicMock` without `spec=` is dominant mocking pattern | `test_issue_api_key.py:16-33`, `test_config_service.py:31-49`, others |
| 36 | 4-M6 | No projection multi-event sequence replay tests | `packages/domain-tenancy/tests/test_tenant_list_projection.py` |
| 37 | 4-M7 | Auth stack and event store excluded from integration fixtures | `tests/conftest.py:16-23` |
| 38 | 4-M8 | Smoke tests lack pytest markers | `tests/test_smoke.py:10-51` |
| 39 | 4-M9 | Duplicated mock-app factory helpers across packages | `test_slug_registry.py:14-24`, `test_oidc_sub_registry.py:14-25` |

**Dimension 5 -- Developer Experience (15 findings)**

| # | ID | Description | File/Location |
|---|----|-------------|---------------|
| 40 | 5-M1 | `__all__` missing on two packages | `integration/tenancy_identity/__init__.py:1`, `infra/auth/middleware/__init__.py:1` |
| 41 | 5-M2 | `Any` type annotations where more specific types are possible | `contributions.py:40,52`, `issue_api_key.py:28,30,82`, `redis_client.py:58` |
| 42 | 5-M3 | Duplicate `EventSourcedApplication` Protocol | `issue_api_key.py:20`, `rotate_api_key.py:19` |
| 43 | 5-M4 | `dict[str, Any]` return types instead of typed structures | `config_service.py:149,198` |
| 44 | 5-M5 | `IssueAPIKeyHandler.handle()` returns untyped `tuple[str, str]` vs named result | `issue_api_key.py:62` |
| 45 | 5-M6 | `infra.auth.middleware` subpackage missing re-exports | `middleware/__init__.py:1` |
| 46 | 5-M7 | API Reference pages missing for infra-taskiq and integration packages | `docs/mkdocs.yml` nav (lines 33-42) |
| 47 | 5-M8 | PADRs largely inaccessible from published docs (6 of 25 surfaced) | `docs/docs/decisions.md`, `_kb/decisions/_index.md` |
| 48 | 5-M9 | Cross-reference gaps in documentation | Reference pages lack links to related guides |
| 49 | 5-M10 | Code examples in docs are illustrative only -- no CI verification | `docs/docs/index.md:31-47` (missing import), `docs/docs/guides/build-projection.md:16-19` (invalid API) |
| 50 | 5-M11 | Development Constitution visibility and accuracy -- template placeholder, async contradiction | `_kb/design/references/con-development-constitution.md:1` |
| 51 | 5-M12 | Contributing guide absent | Root directory (missing CONTRIBUTING.md) |
| 52 | 5-M13 | Dog School example omits key framework features | `examples/dog_school/` |
| 53 | 5-M14 | ValidationError status-code discrepancy between docs (400) and code (422) | `add-api-endpoint.md:66`, `error_handlers.py:259` |
| 54 | 5-M15 | Documentation freshness issues -- stale version, wrong git URL, phantom entry-point group | `CLAUDE.md:7`, `installation.md:48`, `entry-points.md:28` |

**Dimension 6 -- Completeness & Gaps (12 findings)**

| # | ID | Description | File/Location |
|---|----|-------------|---------------|
| 55 | 6-M1 | PADR status tracking unreliable -- 19 of 25 have stale statuses | `_kb/decisions/_index.md` vs individual PADR files |
| 56 | 6-M2 | Nine specified features have zero implementation | PADRs 101, 108, 111, 112, 113, 115, 002, 004, 116-extension |
| 57 | 6-M3 | Five features partially implemented | PADRs 113, 115, 105, 005, 109 |
| 58 | 6-M4 | Decision drift on PADR-109 -- synchronous projections superseded by polling | `projection_lifespan.py:80-147`, commit `93d2192` |
| 59 | 6-M5 | Three effectively superseded PADRs not marked (109, 120, 101) | Individual PADR files |
| 60 | 6-M6 | PADR quality inconsistencies -- 8+ with `{Project}` placeholders, no Key Files sections | Multiple PADR files |
| 61 | 6-M7 | No domain routers registered -- only health stub exercises router discovery | `packages/infra-fastapi/pyproject.toml:29`, `app_factory.py:30` |
| 62 | 6-M8 | TaskIQ missing lifecycle integration -- no entry points, no lifespan hook | `packages/infra-taskiq/pyproject.toml` |
| 63 | 6-M9 | Documentation site missing two packages | `docs/mkdocs.yml` (infra-taskiq, integration absent) |
| 64 | 6-M10 | Test coverage gaps -- six untested modules, one untested package | `redis_client.py`, `instrumentation.py`, `rebuilder.py`, `runner.py`, `dependencies.py`, integration pkg |
| 65 | 6-M11 | Cross-package wiring gaps -- three packages with no entry points | `infra-persistence`, `infra-taskiq`, `integration-tenancy-identity` |
| 66 | 6-M12 | Single true stub (integration package) amid zero TODO/FIXME markers | `packages/integration-tenancy-identity/` |

### Notable Low/Info Findings

**Low -- Most Actionable:**

- Missing `__all__` in `infra-auth/middleware/__init__.py:1` and `integration/tenancy_identity/__init__.py:1` (Dim 1)
- `pytest-xdist` installed but unused -- 815+ tests could benefit from parallel execution (Dim 1)
- No pre-commit hooks (`.pre-commit-config.yaml` absent) (Dim 1)
- Nondeterministic timestamp in Agent API key rotation mutator at `agent.py:196` (Dim 2 -- borderline Medium)
- `BaseEvent.to_dict()` does not automatically include subclass fields (Dim 2)
- JWT JWKS URI constructed via string concatenation rather than OIDC discovery at `jwks.py:67` (Dim 3)
- Health check endpoint is a stub returning only `{"status": "ok"}` with no dependency probes (Dim 3)
- Three instances of bare `pytest.raises(Exception)` with `# noqa: B017` suppression (Dim 4)
- Event types asserted by string comparison (`__class__.__name__`) rather than domain event imports (Dim 4)
- `record_data_deleted` on Tenant breaks `request_*` naming convention at `tenant.py:299` (Dim 5)
- Getting-started installation guide uses wrong git clone URL (`wetink` vs `wet-ink-corporation`) at `installation.md:48` (Dim 5)

**Info -- Key Strengths:**

- Perfect PEP 420 compliance across all 11 packages with zero stray `__init__.py` files (Dim 1)
- All `py.typed` markers present in correct PEP 561 locations (Dim 1, 5)
- Import ergonomics excellent -- all key symbols importable from top-level namespaces (Dim 5)
- RFC 7807 error handling fully compliant with security sanitization (Dim 3, 5)
- Foundation application context cleanly separates request and principal contexts (Dim 3)
- Zero `NotImplementedError`, `TODO`, `FIXME`, `HACK`, or `XXX` markers in source code (Dim 6)
- Exception hierarchy supports 5 levels of catch granularity with error codes (Dim 5)

## Strengths Summary

1. **Perfect namespace compliance.** PEP 420 implicit namespaces are flawlessly implemented across all 11 packages with zero stray `__init__.py` files, correct `py.typed` markers, and consistent `src/praecepta/{layer}/{name}/` layout.

2. **Exemplary Tenant aggregate design.** The Tenant aggregate is a reference-grade DDD/ES implementation with a rigorous four-state lifecycle, comprehensive idempotency, rich audit metadata, and terminal state enforcement.

3. **Production-grade error handling.** RFC 7807 `ProblemDetail` responses, a nine-class exception hierarchy with error codes and structured context, security-aware sanitization, protocol-compliant headers (`WWW-Authenticate`, `Retry-After`), and stack-trace safety with production/debug mode toggle.

4. **Machine-enforced architecture.** Two import-linter contracts mechanically enforce the 4-layer hierarchy and foundation purity. Zero violations across 144 analyzed files and 538 dependencies.

5. **Well-engineered entry-point system.** PADR-122's auto-discovery with `discover()`, contribution dataclasses, priority-based ordering, `AsyncExitStack` lifespan composition, and LIFO middleware registration -- 20 entry points across 6 groups.

6. **100% docstring coverage.** Every public module, class, method, protocol, and exception has Google-style docstrings with `Args:`, `Returns:`, `Raises:`, and `Example:` sections.

7. **Defense-in-depth auth bypass safety.** Production lockout regardless of `AUTH_DEV_BYPASS` value, explicit opt-in, ERROR-level logging of production bypass attempts, and synthetic non-production claims.

8. **Strong concurrency-safe registration patterns.** SlugRegistry, OidcSubRegistry, and JIT UserProvisioningService all implement reserve-confirm-release with PostgreSQL uniqueness enforcement and compensating actions.

9. **Consistent tooling across all packages.** Identical build backend (hatchling), version (0.3.0), wheel configuration, workspace sources, mypy strict mode, ruff formatting, and pytest markers.

10. **Excellent projection polling infrastructure.** `ProjectionPoller` handles cross-process event consumption with daemon threads, responsive shutdown, exception resilience, and proper lifespan ordering.

## Risk Summary

1. **Documentation-code divergence creates adoption barriers.** Three High-severity documentation findings (missing changelog, missing example README, incorrect guide examples) plus pervasive documentation freshness issues mean that developers relying on documentation will encounter friction, runtime errors, or confusion. This is the highest-impact risk for framework adoption.

2. **Peripheral package immaturity creates false expectations.** The 11-package architecture suggests breadth, but 3 packages (infra-taskiq, infra-persistence entry points, integration-tenancy-identity) are incomplete. TaskIQ's convention violations could set negative precedent as the codebase grows. The integration package's stub status means the Layer 3 architecture is entirely untested.

3. **Unit-only test strategy leaves database guarantees unverified.** The domain model relies on PostgreSQL-level guarantees (uniqueness, RLS, UPSERT) that 815 unit tests with mocked dependencies cannot validate. This creates a confidence gap for production deployment.

4. **PADR lifecycle neglect erodes decision record value.** 19 of 25 stale statuses, 3 superseded-but-unmarked decisions (including the significant PADR-109 polling change), 8+ `{Project}` placeholders, and 7 undocumented decisions mean the PADR system functions as a write-once artifact rather than a living decision record.

5. **Type safety gaps at plugin boundaries.** The `Any`-typed contribution system, `object` return types, and untyped mocks (without `spec=`) create a class of integration bugs that neither the type checker nor the test suite can detect. This risk compounds as more packages contribute entry points.
