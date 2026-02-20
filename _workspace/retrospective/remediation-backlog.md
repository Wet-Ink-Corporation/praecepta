# Praecepta Remediation Backlog

**Generated:** 2026-02-18
**Source:** Consolidated Quality Audit
**Baseline:** 815 tests, 0 lint/type/boundary issues, average maturity 3.8/5, 8 High findings, 66 Medium findings

---

## Priority Matrix

### P1 -- Address Before Next Release

These items should be fixed before the codebase is shared with external contributors or used in downstream projects. They represent adoption blockers, correctness risks, or quality gate gaps.

---

**P1-01. Enforce coverage threshold in CI**
- **Finding:** Coverage `fail_under = 70` configured but not enforced (1-H1)
- **Dimension:** 1 -- Architecture Compliance
- **Affected files:** `.github/workflows/quality.yml:44`
- **Fix:** Add `--cov-fail-under=70` to the pytest command in the CI workflow
- **Effort:** S

**P1-02. Fix factual errors in add-api-endpoint guide**
- **Finding:** ValidationError status 400 vs actual 422; NotFoundError constructor TypeError (5-H3, 5-M14)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** `docs/docs/guides/add-api-endpoint.md:66,81`
- **Fix:** Change 400 to 422 on line 66; change `raise NotFoundError(f"Order {order_id} not found")` to `raise NotFoundError("Order", str(order_id))` on line 81
- **Effort:** S

**P1-03. Update CLAUDE.md version reference**
- **Finding:** States "v0.1.0" but actual version is "0.3.0" (1-M9, 5-M15, 6-M9)
- **Dimension:** 1, 5, 6
- **Affected files:** `CLAUDE.md:7`
- **Fix:** Change "pre-alpha (v0.1.0)" to "pre-alpha (v0.3.0)" or remove hardcoded version
- **Effort:** S

**P1-04. Create CHANGELOG.md**
- **Finding:** No changelog exists across 3 version bumps (5-H1)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** Root directory (new file)
- **Fix:** Create CHANGELOG.md documenting changes from 0.1.0 through 0.3.0. Establish versioning strategy (SemVer, monorepo-wide versioning)
- **Effort:** M

**P1-05. Add README to dog_school example**
- **Finding:** No README, no run instructions, no standalone execution path (5-H2)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** `examples/dog_school/` (new README.md, new `__main__.py`)
- **Fix:** Create README with setup instructions, `uvicorn` invocation command, test command, and feature list. Add `__main__.py` for direct execution
- **Effort:** S

**P1-06. Create Pydantic settings for TaskIQ**
- **Finding:** TaskIQ bypasses all infrastructure conventions (3-H1)
- **Dimension:** 3 -- Convention & Standards
- **Affected files:** `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:48-81`
- **Fix:** Introduce `TaskIQSettings(BaseSettings)` with `env_prefix="TASKIQ_"`, validated Redis URL, configurable result TTL. Replace module-level instantiation with factory. Add `LifespanContribution` for broker lifecycle
- **Effort:** M

**P1-07. Fix nondeterministic timestamp in Agent event mutator**
- **Finding:** `datetime.now(UTC)` in `_apply_api_key_rotated` violates ES replay determinism (2-M8)
- **Dimension:** 2 -- Domain Model Quality
- **Affected files:** `packages/domain-identity/src/praecepta/domain/identity/agent.py:196`
- **Fix:** Move `datetime.now(UTC).isoformat()` from the apply method into `request_rotate_api_key` and pass as event parameter
- **Effort:** S

**P1-08. Harmonize tenant identifier validation**
- **Finding:** TenantId, TenantSlug, and BaseEvent enforce divergent validation rules (2-M1)
- **Dimension:** 2 -- Domain Model Quality
- **Affected files:** `identifiers.py:47`, `tenant_value_objects.py:46`, `events.py:126`
- **Fix:** Extract canonical validation rule (2-63 chars, pattern `^[a-z0-9][a-z0-9-]*[a-z0-9]$`) into a shared constant. Update TenantId to match
- **Effort:** S

**P1-09. Align `make verify` with CI behavior**
- **Finding:** Local verify auto-fixes code; CI uses check-only flags (1-M7)
- **Dimension:** 1 -- Architecture Compliance
- **Affected files:** `Makefile:25-30`
- **Fix:** Change `make verify` to use `ruff check` (no `--fix`) and `ruff format --check`. Optionally add `make fix` target for auto-fix behavior
- **Effort:** S

**P1-10. Enforce config value constraints**
- **Finding:** IntegerConfigValue, FloatConfigValue, EnumConfigValue don't validate bounds (2-M4)
- **Dimension:** 2 -- Domain Model Quality
- **Affected files:** `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:59-97`
- **Fix:** Add Pydantic `model_validator` to check `value` against `min_value`/`max_value`/`allowed_values`
- **Effort:** S

**P1-11. Add tests for untested infrastructure modules**
- **Finding:** `redis_client.py` (168 LOC) and `instrumentation.py` (214 LOC) have zero coverage (4-M1, 4-M2, 6-M10)
- **Dimension:** 4, 6
- **Affected files:** `packages/infra-persistence/src/.../redis_client.py`, `packages/infra-observability/src/.../instrumentation.py`
- **Fix:** Write unit tests covering `RedisFactory` singleton lifecycle, `traced_operation` decorator, `start_span` context manager, `get_tracer` factory
- **Effort:** M

**P1-12. Create dedicated error handling guide**
- **Finding:** No error-handling documentation; PADR-103 is stale (5-H3)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** `docs/docs/guides/` (new file)
- **Fix:** Create `docs/docs/guides/error-handling.md` documenting all 10 exception-to-HTTP mappings, ProblemDetail schema, production vs debug mode, and common error resolution steps
- **Effort:** M

---

### P2 -- Address This Quarter

These items improve quality, maintainability, and developer experience but are not blocking release or adoption.

---

**P2-01. Add typed protocols for contribution callables**
- **Finding:** `handler: Any`, `hook: Any`, `DiscoveredContribution.value: Any` (1-M1, 1-M2, 5-M2)
- **Dimension:** 1, 5
- **Affected files:** `contributions.py:40,52`, `discovery.py:29`
- **Fix:** Replace `Any` with `Callable` type aliases or `Protocol` types. Consider making `discover()` generic (`discover[T]()`)
- **Effort:** M

**P2-02. Resolve sync/async ConfigCache protocol mismatch**
- **Finding:** Foundation protocol is sync; `HybridConfigCache` is async (3-M6)
- **Dimension:** 3 -- Convention & Standards
- **Affected files:** `config_service.py:48-69`, `config_cache.py:17-138`
- **Fix:** Make `ConfigCache` protocol async-compatible or introduce async adapter
- **Effort:** M

**P2-03. Add integration tests for database-level guarantees**
- **Finding:** All tests are unit-only; DB guarantees unverified (2-M12, 4-M7)
- **Dimension:** 2, 4
- **Affected files:** `packages/domain-tenancy/tests/`, `packages/domain-identity/tests/`, `tests/conftest.py:16-23`
- **Fix:** Create `@pytest.mark.integration` tests for slug registry uniqueness, OIDC sub registry uniqueness, RLS tenant isolation, UPSERT idempotency
- **Effort:** L

**P2-04. Implement cascade deletion for projections**
- **Finding:** `CascadeDeletionService.delete_tenant_data()` is a stub (2-M6)
- **Dimension:** 2 -- Domain Model Quality
- **Affected files:** `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/cascade_deletion.py:76-84`
- **Fix:** Implement actual deletion of rows from `tenant_list`, `tenant_config`, `user_profiles`, `agent_api_key_registry` tables
- **Effort:** M

**P2-05. Create PADR for polling-based projection consumption**
- **Finding:** Synchronous projections superseded by polling without PADR update (6-M4, 6-H1)
- **Dimension:** 6 -- Completeness & Gaps
- **Affected files:** `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projection_lifespan.py:80-147`, PADR-109
- **Fix:** Draft new PADR documenting motivation, trade-offs, polling interval configuration. Mark PADR-109 as superseded
- **Effort:** M

**P2-06. Reconcile PADR statuses**
- **Finding:** 19 of 25 PADRs have stale status fields (6-M1)
- **Dimension:** 6 -- Completeness & Gaps
- **Affected files:** `_kb/decisions/_index.md`, all 25 PADR files
- **Fix:** Update each PADR file status to match reality. Mark superseded PADRs (109, 120). Mark inapplicable PADRs (108, 111, 112) as "Informational"
- **Effort:** M

**P2-07. Add `spec=` to MagicMock usage across test suite**
- **Finding:** Untyped `MagicMock()` is dominant pattern -- mocks accept any attribute (4-M5)
- **Dimension:** 4 -- Test Quality
- **Affected files:** `test_issue_api_key.py:16-33`, `test_rotate_api_key.py:17-34`, `test_config_service.py:31-49`, `test_resource_limits.py:23-27`, others
- **Fix:** Audit all `MagicMock()` and add `spec=<TargetClass>`. For port boundaries, follow `test_ports.py` Protocol-conforming pattern
- **Effort:** M

**P2-08. Add projection multi-event sequence replay tests**
- **Finding:** Projections tested with isolated events, not cumulative sequences (4-M6)
- **Dimension:** 4 -- Test Quality
- **Affected files:** `packages/domain-tenancy/tests/test_tenant_list_projection.py`
- **Fix:** Add tests dispatching Provisioned -> Activated -> Suspended and verifying final read model state
- **Effort:** S

**P2-09. Replace blocking `time.sleep()` in provisioning retry**
- **Finding:** Blocks event loop in async context (2-M9)
- **Dimension:** 2 -- Domain Model Quality
- **Affected files:** `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:113`
- **Fix:** Use `asyncio.sleep()` or document the service as sync-only
- **Effort:** S

**P2-10. Add dependency security scanning**
- **Finding:** No pip-audit, safety, or Dependabot (1-M8)
- **Dimension:** 1 -- Architecture Compliance
- **Affected files:** `.github/workflows/` (new step or workflow)
- **Fix:** Add `pip-audit` step to `quality.yml` or enable Dependabot
- **Effort:** S

**P2-11. Create CONTRIBUTING.md**
- **Finding:** No contributing guide at repository root (5-M12)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** Root directory (new file)
- **Fix:** Consolidate dev setup, PR conventions, commit format, and "Adding a New Package" checklist
- **Effort:** M

**P2-12. Complete mkdocstrings paths and add missing reference pages**
- **Finding:** infra-taskiq and integration packages missing from docs (1-M10, 5-M7, 6-M9)
- **Dimension:** 1, 5, 6
- **Affected files:** `docs/mkdocs.yml:50-59`, `docs/docs/reference/`
- **Fix:** Add `infra-taskiq/src` and `integration-tenancy-identity/src` to mkdocstrings paths. Add reference pages
- **Effort:** S

**P2-13. Establish router mount conventions**
- **Finding:** No URL prefix, tag, or versioning policy (1-M4, 3-M3, 6-M7)
- **Dimension:** 1, 3, 6
- **Affected files:** `app_factory.py:153`, documentation
- **Fix:** Document and enforce `/api/v1/{domain}/...` prefix patterns, tag requirements. Add validation in router discovery loop. Register at least one domain router from tenancy package
- **Effort:** M

**P2-14. Eliminate duplicate ResourceLimitResult**
- **Finding:** Two separate classes with identical structure (3-M7)
- **Dimension:** 3 -- Convention & Standards
- **Affected files:** `foundation/application/resource_limits.py:25`, `infra/fastapi/dependencies/resource_limits.py:44`
- **Fix:** Import the foundation version in the FastAPI layer
- **Effort:** S

**P2-15. Extract duplicate EventSourcedApplication Protocol**
- **Finding:** Identical Protocol defined twice (5-M3)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** `issue_api_key.py:20`, `rotate_api_key.py:19`
- **Fix:** Extract into shared module and import from both
- **Effort:** S

**P2-16. Resolve BaseEvent / @event-generated event class disconnect**
- **Finding:** BaseEvent metadata (correlation_id, causation_id, user_id) absent from aggregate events (2-M2)
- **Dimension:** 2 -- Domain Model Quality
- **Affected files:** `events.py:117-122`, `tenant.py:60`
- **Fix:** Document or implement strategy for threading metadata into @event-generated classes
- **Effort:** L

**P2-17. Add tests for ProjectionRebuilder**
- **Finding:** Destructive operation with zero test coverage (3-M2, 6-M10)
- **Dimension:** 3, 6
- **Affected files:** `packages/infra-eventsourcing/src/.../projections/rebuilder.py:65-177`
- **Fix:** Add unit tests for clear/reset workflow, error handling, and full rebuild cycle. Type the `upstream_app` parameter properly
- **Effort:** M

**P2-18. Clean up dead conftest fixtures**
- **Finding:** Domain conftest fixtures defined but unused by any test (4-M4)
- **Dimension:** 4 -- Test Quality
- **Affected files:** `packages/domain-tenancy/tests/conftest.py`, `packages/domain-identity/tests/conftest.py`
- **Fix:** Either refactor tests to use the fixtures or remove the dead code
- **Effort:** S

**P2-19. Publish PADRs to documentation site**
- **Finding:** 6 of 25 PADRs surfaced; 19 only in internal `_kb/` (5-M8)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** `docs/docs/decisions.md`, `_kb/decisions/`
- **Fix:** Configure MkDocs to include the `_kb/decisions/` directory or copy PADR content into published docs
- **Effort:** M

**P2-20. Fix documentation freshness issues**
- **Finding:** Wrong git clone URL, missing prerequisites, phantom entry-point group (5-M15)
- **Dimension:** 5 -- Developer Experience
- **Affected files:** `docs/docs/getting-started/installation.md:48`, `docs/docs/architecture/entry-points.md:28`
- **Fix:** Correct `wetink` to `wet-ink-corporation`, add PostgreSQL/Redis prerequisites, remove or implement `praecepta.subscriptions`
- **Effort:** S

---

### P3 -- Backlog / Nice-to-Have

These items improve overall polish, consistency, and completeness but have no immediate impact on adoption or correctness.

---

**P3-01. Implement or descope the integration package**
- **Finding:** Integration package is a pure stub (2-H1, 6-H2)
- **Dimension:** 2, 6
- **Affected files:** `packages/integration-tenancy-identity/`
- **Fix:** Implement minimal cross-domain saga (tenant provisioned -> create admin user) with tests and entry points. Alternatively, mark as future milestone in package table
- **Effort:** L

**P3-02. Implement `praecepta.subscriptions` entry-point group**
- **Finding:** Documented in PADR-122 but no implementation exists (1-M5)
- **Dimension:** 1
- **Affected files:** `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:51`
- **Fix:** Wire in integration-tenancy-identity package or formally remove from ADR
- **Effort:** L

**P3-03. Create missing PADR documents for undocumented decisions**
- **Finding:** Seven architectural decisions lack PADRs (6-H1)
- **Dimension:** 6
- **Affected files:** `_kb/decisions/` (new files)
- **Fix:** Write PADRs for polling-based projections, PEP 420, BaseAggregate multi-tenancy, dev bypass, ContextVar design, config cache, OIDC sub registry reservation
- **Effort:** L

**P3-04. Replace `{Project}` placeholders in PADRs**
- **Finding:** 8+ PADRs retain source-project placeholders (6-M6)
- **Dimension:** 6
- **Affected files:** Multiple PADR files
- **Fix:** Search-and-replace `{Project}` with praecepta-specific namespace paths
- **Effort:** S

**P3-05. Add lifecycle terminal events to identity aggregates**
- **Finding:** No User.Deactivated or Agent.Deregistered events (2-M11)
- **Dimension:** 2
- **Affected files:** `user.py:17-100`, `agent.py:23-199`
- **Fix:** Implement deactivation/deregistration events with terminal state enforcement
- **Effort:** M

**P3-06. Implement ValidationResult per PADR-113**
- **Finding:** Tier 2 semantic validation not codified (2-M5)
- **Dimension:** 2
- **Affected files:** Foundation-domain package (new type)
- **Fix:** Create frozen dataclass `ValidationResult` for structured semantic validation
- **Effort:** S

**P3-07. Introduce async test functions**
- **Finding:** Zero async tests despite `asyncio_mode = "strict"` (4-M3)
- **Dimension:** 4
- **Affected files:** All test directories
- **Fix:** Add `@pytest.mark.asyncio` tests for `redis_client.py` async methods, `async_wrapper` in instrumentation, and at least one direct async middleware dispatch test
- **Effort:** M

**P3-08. Add pytest markers to smoke tests**
- **Finding:** Smoke tests lack markers (4-M8, 1-Low)
- **Dimension:** 4, 1
- **Affected files:** `tests/test_smoke.py:10-51`
- **Fix:** Add `@pytest.mark.unit` to all smoke test functions
- **Effort:** S

**P3-09. Enable `pytest-xdist` in CI**
- **Finding:** Installed but unused for 815+ tests (1-Low)
- **Dimension:** 1
- **Affected files:** `.github/workflows/quality.yml:44`
- **Fix:** Add `-n auto` to pytest command
- **Effort:** S

**P3-10. Add missing `__all__` exports**
- **Finding:** Two `__init__.py` files lack `__all__` (1-Low, 5-M1)
- **Dimension:** 1, 5
- **Affected files:** `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1`, `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1`
- **Fix:** Add `__all__` with appropriate re-exports
- **Effort:** S

**P3-11. Extract display name derivation into shared function**
- **Finding:** Logic duplicated between aggregate and projection (2-M10)
- **Dimension:** 2
- **Affected files:** `user.py:60-65`, `user_profile.py:66-73`
- **Fix:** Create a shared utility function for the `name -> email prefix -> "User"` fallback chain
- **Effort:** S

**P3-12. Consolidate duplicated mock-app factory helpers**
- **Finding:** `_make_mock_app()` duplicated across packages (4-M9)
- **Dimension:** 4
- **Affected files:** `test_slug_registry.py:14-24`, `test_oidc_sub_registry.py:14-25`
- **Fix:** Extract into shared test utility module
- **Effort:** S

**P3-13. Cache DatabaseSettings via lru_cache**
- **Finding:** Re-instantiated on every `_get_database_url()` call (3-M5)
- **Dimension:** 3
- **Affected files:** `packages/infra-persistence/src/praecepta/infra/persistence/database.py:98`
- **Fix:** Add `@lru_cache` consistent with pattern used by AuthSettings, LoggingSettings, TracingSettings
- **Effort:** S

**P3-14. Standardize RedisSettings env_prefix**
- **Finding:** No `env_prefix`; fields manually prefixed (3-M5)
- **Dimension:** 3
- **Affected files:** `packages/infra-persistence/src/praecepta/infra/persistence/redis_settings.py:16-49`
- **Fix:** Add `env_prefix="REDIS_"` and remove manual `redis_` field prefixes
- **Effort:** S

**P3-15. Add `BaseAggregate` tenant_id enforcement**
- **Finding:** tenant_id annotation exists but no runtime verification (2-M3)
- **Dimension:** 2
- **Affected files:** `aggregates.py:104`, `user.py:57`, `agent.py:59`
- **Fix:** Add `__init_subclass__` hook or post-init validation for tenant_id
- **Effort:** S

**P3-16. Make import-linter accepted exception explicit**
- **Finding:** Domain->infra-eventsourcing dependency not explicitly documented in contract (1-M11)
- **Dimension:** 1
- **Affected files:** `pyproject.toml:207-215`
- **Fix:** Add `ignore_imports` directive that explicitly documents the accepted dependency
- **Effort:** S

**P3-17. Add second example application**
- **Finding:** Only one example covers a narrow slice of capabilities (5-M13)
- **Dimension:** 5
- **Affected files:** `examples/` (new directory)
- **Fix:** Create example demonstrating projections, auth, persistence, and observability
- **Effort:** L

**P3-18. Resolve Development Constitution**
- **Finding:** Template placeholder, async-first contradiction with PADR-109 (5-M11)
- **Dimension:** 5
- **Affected files:** `_kb/design/references/con-development-constitution.md:1`
- **Fix:** Replace `{Project}` placeholder, resolve async/sync contradiction, publish or archive
- **Effort:** M

**P3-19. Create Development Constitution document for published docs**
- **Finding:** Quality standards scattered across multiple files (3-M4)
- **Dimension:** 3
- **Affected files:** `docs/docs/architecture/development-constitution.md` (new)
- **Fix:** Consolidate CLAUDE.md, decisions.md, and guide standards into single document
- **Effort:** M

**P3-20. Add TenantApplication orchestration methods**
- **Finding:** Bare Application subclass with no domain service value (2-M7)
- **Dimension:** 2
- **Affected files:** `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant_app.py:17-27`
- **Fix:** Add `provision_tenant()`, `get_by_slug()`, and other orchestration methods
- **Effort:** M

**P3-21. Introduce typed return for config service**
- **Finding:** `get_config()` returns `dict[str, Any]` with known keys (5-M4)
- **Dimension:** 5
- **Affected files:** `config_service.py:149,198`
- **Fix:** Create TypedDict or dataclass for config results
- **Effort:** S

**P3-22. Align IssueAPIKeyHandler return type with RotateAPIKeyHandler**
- **Finding:** Returns untyped `tuple[str, str]` vs named result (5-M5)
- **Dimension:** 5
- **Affected files:** `issue_api_key.py:62`
- **Fix:** Create `IssueAPIKeyResult` dataclass matching `RotateAPIKeyResult` pattern
- **Effort:** S

**P3-23. Wire TaskIQ into app lifecycle**
- **Finding:** No entry points, no lifespan hook (6-M8)
- **Dimension:** 6
- **Affected files:** `packages/infra-taskiq/pyproject.toml`
- **Fix:** Add `[project.entry-points]` with `praecepta.lifespan` for broker startup/shutdown
- **Effort:** S

**P3-24. Add "Key Files" sections to PADRs**
- **Finding:** 15+ PADRs lack implementation file references (6-M6)
- **Dimension:** 6
- **Affected files:** Multiple PADR files under `_kb/decisions/`
- **Fix:** Follow PADR-122 model -- add file path references to each PADR
- **Effort:** M

---

## Quick Wins

Items that are P1 or P2 with effort S -- can be fixed in under an hour each.

| # | Finding | Dimension | Effort | Files |
|---|---------|-----------|--------|-------|
| 1 | Enforce coverage threshold in CI (`--cov-fail-under=70`) | 1 | S | `.github/workflows/quality.yml:44` |
| 2 | Fix ValidationError status code in guide (400 -> 422) | 5 | S | `docs/docs/guides/add-api-endpoint.md:66` |
| 3 | Fix NotFoundError constructor in guide | 5 | S | `docs/docs/guides/add-api-endpoint.md:81` |
| 4 | Update CLAUDE.md version (0.1.0 -> 0.3.0) | 1,5,6 | S | `CLAUDE.md:7` |
| 5 | Add README to dog_school example | 5 | S | `examples/dog_school/` |
| 6 | Fix nondeterministic timestamp in Agent mutator | 2 | S | `agent.py:196` |
| 7 | Harmonize tenant identifier validation | 2 | S | `identifiers.py:47`, `tenant_value_objects.py:46`, `events.py:126` |
| 8 | Align `make verify` with CI (remove auto-fix) | 1 | S | `Makefile:25-30` |
| 9 | Enforce config value constraints | 2 | S | `config_value_objects.py:59-97` |
| 10 | Replace `time.sleep()` with `asyncio.sleep()` | 2 | S | `user_provisioning.py:113` |
| 11 | Add dependency security scanning | 1 | S | `.github/workflows/quality.yml` |
| 12 | Complete mkdocstrings paths | 1,5,6 | S | `docs/mkdocs.yml:50-59` |
| 13 | Eliminate duplicate ResourceLimitResult | 3 | S | `resource_limits.py` (both) |
| 14 | Extract duplicate EventSourcedApplication Protocol | 5 | S | `issue_api_key.py`, `rotate_api_key.py` |
| 15 | Clean up dead conftest fixtures | 4 | S | `domain-tenancy/tests/conftest.py`, `domain-identity/tests/conftest.py` |
| 16 | Fix documentation freshness issues (git URL, prerequisites) | 5 | S | `installation.md:48`, `entry-points.md:28` |
| 17 | Add pytest markers to smoke tests | 4 | S | `tests/test_smoke.py` |
| 18 | Replace `{Project}` placeholders in PADRs | 6 | S | Multiple PADR files |
| 19 | Add `__all__` to two missing packages | 1,5 | S | `middleware/__init__.py`, `tenancy_identity/__init__.py` |
| 20 | Add projection multi-event replay tests | 4 | S | `test_tenant_list_projection.py` |

## Dependency Graph

Several remediation items have logical dependencies:

```
P1-06 (TaskIQ Pydantic settings)
  --> P3-23 (Wire TaskIQ into app lifecycle)
       --> P3-02 (Implement praecepta.subscriptions)

P2-05 (PADR for polling projections)
  --> P2-06 (Reconcile all PADR statuses)
       --> P3-03 (Create missing PADR documents)
            --> P3-24 (Add Key Files sections)

P2-13 (Router mount conventions)
  --> P3-01 (Implement integration package)
       --> P3-02 (Implement praecepta.subscriptions)

P2-03 (Integration tests for DB guarantees)
  --> P2-04 (Implement cascade deletion)

P1-12 (Error handling guide)
  --> P1-02 (Fix guide factual errors)
       Both fix documentation trust issues

P3-07 (Async test functions)
  --> P1-11 (Tests for redis_client.py, instrumentation.py)
       redis_client.py tests should be async
```

## Metrics Targets

Suggested targets for the next audit cycle (projected: Q2 2026):

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Overall RAG | RED | AMBER | Requires resolving all 3 Dim-5 High findings |
| Average maturity | 3.8 | 4.0 | Requires closing Medium findings in Dims 5 and 6 |
| Critical findings | 0 | 0 | Maintain |
| High findings | 8 | 0 | All 8 are addressable with M or less effort |
| Medium findings | 66 | < 30 | Focus on P1 and P2 items; some P3 will persist |
| Dim 1 - Architecture | 4.4 (AMBER) | 4.5 (GREEN) | Close H1 (CI coverage) to achieve GREEN |
| Dim 2 - Domain Model | 3.8 (AMBER) | 4.0 (GREEN) | Fix validation, ES determinism, add integration tests |
| Dim 3 - Conventions | 4.0 (AMBER) | 4.2 (GREEN) | Fix TaskIQ conventions, resolve sync/async mismatch |
| Dim 4 - Test Quality | 3.9 (AMBER) | 4.2 (GREEN) | Add async tests, infrastructure coverage, spec= mocks |
| Dim 5 - Dev Experience | 3.7 (RED) | 4.0 (AMBER->GREEN) | Changelog, example README, fix guide errors |
| Dim 6 - Completeness | 3.2 (AMBER) | 3.8 (AMBER) | Reconcile PADRs, implement integration package |
| Test count | 815 | 900+ | Integration tests and infrastructure tests will add ~85 |
| Async test coverage | 0% | > 20% | Target for infrastructure and middleware modules |
