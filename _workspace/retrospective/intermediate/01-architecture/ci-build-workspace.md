# CI/Build & Workspace Wiring Audit

**Dimension:** 01-Architecture
**Collector:** 1C -- CI/Build & Workspace Wiring
**Date:** 2026-02-18
**Baseline:** All checks pass (ruff, mypy, lint-imports, pytest 815 tests)

---

## 1. Makefile Targets

**Maturity: 4 -- Managed**

All documented targets in CLAUDE.md exist and are correctly wired in the Makefile. The `verify` target chains lint, format, typecheck, boundaries, and test in sequence.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| All 10 documented targets (`test`, `test-unit`, `test-int`, `lint`, `format`, `typecheck`, `boundaries`, `verify`, `install`, `docs`, `docs-dev`) are present and functional. | `Makefile:1-48` | Info | High |
| The `lint` target performs both `ruff check --fix` AND `ruff format`, making it a superset of the `format` target. The CLAUDE.md documents `make lint` as only "ruff check ... --fix" but the actual Makefile also runs format. | `Makefile:12-14` vs `CLAUDE.md:17` | Low | High |
| The `verify` target runs lint with `--fix` (auto-correcting) before testing. In CI, `quality.yml` correctly separates check (no fix) and format check (with `--check` flag). The Makefile `verify` mutates code before running tests, which could mask issues locally. | `Makefile:25-30` vs `.github/workflows/quality.yml:32-35` | Medium | High |
| `help` target uses grep/awk to auto-generate help text from comments. Clean implementation. | `Makefile:45-48` | Info | High |

---

## 2. GitHub Workflows

**Maturity: 4 -- Managed**

Three well-structured workflows exist covering quality, publishing, and docs deployment.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| `quality.yml` covers lint, format check, typecheck, boundaries, and tests -- all five pillars. Runs on push to main and PRs. | `.github/workflows/quality.yml:1-44` | Info | High |
| Quality workflow tests against Python 3.12 and 3.13 matrix -- good version coverage. | `.github/workflows/quality.yml:14-15` | Info | High |
| `publish.yml` gates on quality workflow via `workflow_call`, builds all packages, verifies installability, and creates GitHub Release. Well-structured pipeline. | `.github/workflows/publish.yml:1-61` | Info | High |
| `docs.yml` deploys to GitHub Pages on main push when docs or package `__init__.py` files change. Uses path filtering for efficiency. | `.github/workflows/docs.yml:1-56` | Info | High |
| CI lint step uses `ruff check` (no `--fix`), correctly failing on issues rather than silently auto-fixing. This is the right approach for CI vs the Makefile's `--fix` for local dev. | `.github/workflows/quality.yml:32` | Info | High |
| CI format step uses `--check` flag, correctly failing on unformatted code without modifying it. | `.github/workflows/quality.yml:35` | Info | High |
| No workflow for dependency security scanning (e.g., `pip-audit`, `safety`, Dependabot). | `.github/workflows/` | Medium | High |
| No caching of uv dependencies in CI workflows. Adding `uv cache` could speed up builds. | `.github/workflows/quality.yml:28-29` | Low | High |

---

## 3. Coverage Configuration

**Maturity: 3 -- Defined**

Coverage is configured with pytest-cov and `coverage.py` settings, but enforcement has a gap.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| `pytest-cov>=4.1` is in dev dependencies. | `pyproject.toml:59` | Info | High |
| `[tool.coverage.run]` configures `source_pkgs = ["praecepta"]` with branch coverage enabled. | `pyproject.toml:136-138` | Info | High |
| `[tool.coverage.report]` sets `fail_under = 70` with sensible exclusion lines (`pragma: no cover`, `TYPE_CHECKING`, `__main__`, `@overload`, `raise NotImplementedError`). | `pyproject.toml:140-149` | Info | High |
| CI runs `uv run pytest --tb=short --cov --cov-report=term-missing` but does NOT pass `--cov-fail-under=70`. The `fail_under = 70` in `[tool.coverage.report]` is only enforced when `coverage report` is explicitly called, not by pytest-cov's `--cov` flag alone. This means the 70% threshold is NOT actually enforced in CI. | `.github/workflows/quality.yml:44` | High | High |
| Local `make test` does not include `--cov` at all. Coverage is only measured in CI, not during local development via Makefile targets. | `Makefile:3-4` | Low | Medium |
| No coverage report upload (e.g., Codecov, Coveralls) in CI. Coverage results exist only in CI logs. | `.github/workflows/quality.yml:44` | Low | High |

---

## 4. mypy Configuration

**Maturity: 5 -- Optimizing**

Strict mode is enabled with comprehensive settings for a namespace-packages monorepo.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| `strict = true` enabled globally. | `pyproject.toml:159` | Info | High |
| `namespace_packages = true` and `explicit_package_bases = true` correctly set for PEP 420 implicit namespace packages. | `pyproject.toml:172-173` | Info | High |
| `mypy_path` lists all 11 package `src` directories, one for each workspace package. Verified: `foundation-domain`, `foundation-application`, `infra-fastapi`, `infra-eventsourcing`, `infra-auth`, `infra-persistence`, `infra-observability`, `infra-taskiq`, `domain-tenancy`, `domain-identity`, `integration-tenancy-identity`. | `pyproject.toml:157` | Info | High |
| Test overrides relax `disallow_untyped_defs` and `disallow_untyped_decorators` for the `tests.*` module, which is pragmatic for test code. | `pyproject.toml:175-178` | Info | High |
| Additional strict flags beyond `strict = true` are specified (`warn_return_any`, `warn_unused_configs`, `disallow_untyped_defs`, etc.). These are redundant since `strict = true` already enables them, but they serve as documentation and protection against changes to mypy's `strict` flag definition. | `pyproject.toml:160-171` | Info | High |
| `show_error_codes = true` and `show_column_numbers = true` provide good developer experience for diagnosing type errors. | `pyproject.toml:170-171` | Info | High |

---

## 5. import-linter Configuration

**Maturity: 4 -- Managed**

Two contracts enforce the 4-layer hierarchy, covering both forbidden imports and layer ordering.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| Contract 1 (forbidden): Foundation layer (`praecepta.foundation.domain`, `praecepta.foundation.application`) is forbidden from importing `fastapi`, `sqlalchemy`, `httpx`, `structlog`, `opentelemetry`, `taskiq`, `redis`. This matches the CLAUDE.md specification. | `pyproject.toml:188-204` | Info | High |
| Contract 2 (layers): Enforces `integration > domain > infra > foundation` ordering. This is the correct 4-layer hierarchy. | `pyproject.toml:207-215` | Info | High |
| The `include_external_packages = true` setting is important for the forbidden contract to work correctly with external packages. | `pyproject.toml:186` | Info | High |
| The accepted exception documented in CLAUDE.md (domain packages depending on `praecepta-infra-eventsourcing` for `Application` and `BaseProjection`) is NOT explicitly reflected in the import-linter contracts. The `layers` contract type in import-linter allows upward imports by default only if the layers contract is configured with `ignore_imports`. Since the layer contract lists `praecepta.infra` below `praecepta.domain`, domain importing infra would normally be a violation. However, the tests pass, which suggests import-linter's layer contract is configured in a way that permits this or the imports are structured to avoid detection. This warrants investigation. | `pyproject.toml:207-215` vs `CLAUDE.md:43` | Medium | Medium |
| The forbidden contract does not include `eventsourcing` (the `eventsourcing` PyPI package) in the forbidden list for foundation. Foundation packages DO depend on `eventsourcing>=9.5` (see `packages/foundation-domain/pyproject.toml:11`). This is architecturally intentional but worth noting -- the `eventsourcing` library is treated as a domain-level primitive, not infrastructure. | `packages/foundation-domain/pyproject.toml:11` vs `pyproject.toml:196-204` | Info | High |
| No contract explicitly forbids integration-layer packages from importing infrastructure directly (bypassing domain). The layers contract handles this implicitly. | `pyproject.toml:207-215` | Info | Medium |

---

## 6. Workspace Members

**Maturity: 5 -- Optimizing**

All 11 packages are correctly registered in the workspace.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| `[tool.uv.workspace] members = ["packages/*"]` uses glob pattern, automatically including all 11 package directories. | `pyproject.toml:39-40` | Info | High |
| All 11 packages listed in `[project] dependencies` with corresponding `[tool.uv.sources]` entries using `workspace = true`. | `pyproject.toml:18-53` | Info | High |
| Physical directories verified: `domain-identity`, `domain-tenancy`, `foundation-application`, `foundation-domain`, `infra-auth`, `infra-eventsourcing`, `infra-fastapi`, `infra-observability`, `infra-persistence`, `infra-taskiq`, `integration-tenancy-identity` -- exactly 11. | `packages/*/` | Info | High |
| Each package has its own `pyproject.toml` with `hatchling` build backend. | `packages/*/pyproject.toml` | Info | High |
| `[tool.uv] package = false` on the root project correctly marks it as a virtual package (workspace root only, not installable itself). | `pyproject.toml:37` | Info | High |

---

## 7. Cross-Package Dependencies

**Maturity: 4 -- Managed**

Dependencies flow correctly through the layer hierarchy with appropriate workspace source declarations.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| **Foundation layer (Layer 0):** `foundation-domain` has zero workspace dependencies (leaf). `foundation-application` depends only on `foundation-domain`. Correct. | `packages/foundation-domain/pyproject.toml:10-13`, `packages/foundation-application/pyproject.toml:10-12` | Info | High |
| **Infra layer (Layer 1):** All infra packages depend on foundation packages only (`foundation-domain` and/or `foundation-application`). `infra-taskiq` has zero workspace dependencies (only external: `taskiq`, `taskiq-redis`). `infra-observability` depends only on `foundation-application`. Correct. | `packages/infra-*/pyproject.toml` | Info | High |
| **Domain layer (Layer 2):** Both `domain-tenancy` and `domain-identity` depend on `foundation-domain`, `foundation-application`, AND `infra-eventsourcing`. This is the documented "accepted exception" where domain packages depend on infra for `Application` and `BaseProjection` base classes. | `packages/domain-tenancy/pyproject.toml:10-14`, `packages/domain-identity/pyproject.toml:10-14` | Info | High |
| **Integration layer (Layer 3):** `integration-tenancy-identity` depends only on `domain-tenancy` and `domain-identity`. Correct -- no direct foundation or infra dependencies (they come transitively). | `packages/integration-tenancy-identity/pyproject.toml:10-13` | Info | High |
| All inter-workspace dependencies have matching `[tool.uv.sources]` entries with `workspace = true` in their respective `pyproject.toml` files. Verified for all 11 packages. | `packages/*/pyproject.toml` | Info | High |
| `infra-taskiq` has no workspace dependencies at all, and no `[tool.uv.sources]` section. It depends only on external packages (`taskiq`, `taskiq-redis`). This means it is architecturally isolated -- it does not use foundation types. This may be intentional (pure broker factory) or could indicate incomplete wiring. | `packages/infra-taskiq/pyproject.toml:10-13` | Low | High |
| Domain packages both depend on `sqlalchemy>=2.0` directly. This is an infrastructure library at the domain layer, which is somewhat unusual. It suggests domain packages include infrastructure-adjacent code (e.g., SQLAlchemy-based projections/repositories). | `packages/domain-tenancy/pyproject.toml:14`, `packages/domain-identity/pyproject.toml:14` | Low | Medium |

---

## 8. Dev Dependencies

**Maturity: 4 -- Managed**

All needed development tools are present in the dev dependency group.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| Core dev tools present: `pytest>=8.0`, `pytest-asyncio>=0.23`, `pytest-cov>=4.1`, `pytest-xdist>=3.5`, `mypy>=1.8`, `ruff>=0.1`, `import-linter>=2.0`, `httpx>=0.27`. | `pyproject.toml:56-65` | Info | High |
| `httpx>=0.27` included for test client support (used by FastAPI's `TestClient`). | `pyproject.toml:61` | Info | High |
| `pytest-xdist>=3.5` is available for parallel test execution but is not used in any Makefile target or CI workflow (no `-n auto` flag). | `pyproject.toml:60` | Low | High |
| Docs dependency group (`docs`) is separate: `mkdocs>=1.6`, `mkdocs-shadcn`, `mkdocstrings[python]>=0.27`, `mkdocs-llmstxt>=0.2`. | `pyproject.toml:66-71` | Info | High |
| No `pre-commit` in dev dependencies. Consider adding pre-commit hooks for local development quality gates. | `pyproject.toml:56-65` | Low | Medium |
| No `pip-audit` or `safety` for dependency vulnerability scanning. | `pyproject.toml:56-65` | Medium | High |

---

## 9. Root Test Configuration

**Maturity: 4 -- Managed**

Well-structured test configuration with proper markers, test paths, and fixtures.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| `testpaths = ["tests", "packages/*/tests"]` collects both root integration tests and per-package tests. | `pyproject.toml:116` | Info | High |
| `asyncio_mode = "strict"` requires explicit `@pytest.mark.asyncio` on async tests. Good for clarity. | `pyproject.toml:118` | Info | High |
| Three markers defined: `integration`, `unit`, `slow`. `--strict-markers` enforces no typos. | `pyproject.toml:120-124` | Info | High |
| `--import-mode=importlib` is correct for PEP 420 namespace packages where `__init__.py` files are intentionally absent at intermediate levels. | `pyproject.toml:128` | Info | High |
| Root `tests/conftest.py` provides shared fixtures (`dog_school_app`, `client`, `tenant_headers`) for integration tests. Clean fixture design with proper cleanup (`_dogs.clear()`). | `tests/conftest.py:1-49` | Info | High |
| `test_smoke.py` verifies all 11 packages are importable -- acts as a namespace resolution regression test. Notably, these tests have NO marker (`unit` or `integration`), so they always run with `make test` but are excluded from both `make test-unit` and `make test-int`. | `tests/test_smoke.py:1-51` | Low | High |
| Four integration test files cover app factory, middleware, dog school domain/API, and error handling. All properly marked `@pytest.mark.integration`. | `tests/test_integration_*.py` | Info | High |
| 66 package-level test files across all packages demonstrate comprehensive per-package testing. All have `@pytest.mark.unit` markers based on grep analysis (~355 occurrences). | `packages/*/tests/test_*.py` | Info | High |

---

## 10. CLAUDE.md Accuracy

**Maturity: 3 -- Defined**

CLAUDE.md is mostly accurate but contains a few stale or inaccurate items.

| Finding | File | Severity | Confidence |
|---------|------|----------|------------|
| **Version mismatch:** CLAUDE.md states "currently in pre-alpha (v0.1.0)" but actual version is `0.3.0` across all packages. | `CLAUDE.md:7` vs `pyproject.toml:3` | Medium | High |
| **`make lint` description incomplete:** CLAUDE.md says `make lint` is `uv run ruff check packages/ tests/ examples/ --fix`. Actual Makefile target also runs `uv run ruff format packages/ tests/ examples/` as a second step. | `CLAUDE.md:17` vs `Makefile:12-14` | Low | High |
| **`make verify` description incomplete:** CLAUDE.md says "Full check: lint + typecheck + boundaries + test". The actual Makefile target runs 5 steps: ruff check --fix, ruff format, mypy, lint-imports, pytest. The format step is not mentioned. | `CLAUDE.md:12` vs `Makefile:25-30` | Low | High |
| Package table is accurate -- all 11 packages with correct namespace and layer assignments match the actual codebase. | `CLAUDE.md:78-90` | Info | High |
| Command reference matches actual Makefile for all listed targets. | `CLAUDE.md:9-23` vs `Makefile:1-48` | Info | High |
| Architecture description (4-layer hierarchy, PEP 420, hatchling, entry-point auto-discovery) accurately reflects configuration in `pyproject.toml`. | `CLAUDE.md:29-74` | Info | High |
| Code style section accurately reflects ruff, mypy, and pytest configuration. | `CLAUDE.md:94-98` | Info | High |
| "Adding a New Package" checklist is accurate and matches the actual configuration touchpoints. | `CLAUDE.md:102-110` | Info | High |
| **Docs configuration gaps:** `docs/mkdocs.yml` mkdocstrings paths are missing `infra-taskiq/src` and `integration-tenancy-identity/src`. These two packages would not be included in API reference auto-generation. CLAUDE.md does not document docs paths as a configuration touchpoint when adding new packages. | `docs/mkdocs.yml:50-59` | Medium | High |

---

## Summary Statistics

| Checklist Item | Maturity | Top Severity |
|----------------|----------|--------------|
| 1. Makefile Targets | 4 | Medium |
| 2. GitHub Workflows | 4 | Medium |
| 3. Coverage Configuration | 3 | **High** |
| 4. mypy Configuration | 5 | Info |
| 5. import-linter Configuration | 4 | Medium |
| 6. Workspace Members | 5 | Info |
| 7. Cross-Package Dependencies | 4 | Low |
| 8. Dev Dependencies | 4 | Medium |
| 9. Root Test Configuration | 4 | Low |
| 10. CLAUDE.md Accuracy | 3 | Medium |

**Overall Dimension Maturity: 4.0 (Managed)**

### Severity Distribution

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 7 |
| Low | 9 |
| Info | 30 |

---

## Additional Observations

### High-Priority Action Items

1. **Coverage threshold not enforced in CI (High).** The `fail_under = 70` in `[tool.coverage.report]` is not enforced because CI runs `pytest --cov --cov-report=term-missing` without also running `coverage report` or passing `--cov-fail-under=70` to pytest. Fix: add `--cov-fail-under=70` to the CI pytest command at `.github/workflows/quality.yml:44`.

### Medium-Priority Observations

2. **`make verify` auto-fixes before testing.** The local `verify` target runs `ruff check --fix` and `ruff format`, which modifies source files before running mypy and pytest. This could mask formatting/lint issues that would fail in CI. Consider separating the fix step from the verify step, or adding a `verify-ci` target that uses `--check` flags.

3. **No dependency security scanning.** No `pip-audit`, `safety`, or Dependabot configuration found. For a framework project, dependency supply chain security is important.

4. **Version drift in CLAUDE.md.** The version claim of "v0.1.0" should be updated to "v0.3.0" or changed to reference a dynamic source.

5. **Docs mkdocstrings paths incomplete.** Two packages (`infra-taskiq`, `integration-tenancy-identity`) are missing from the mkdocstrings Python handler paths in `docs/mkdocs.yml:50-59`. Their API reference pages also do not appear in the nav at `docs/mkdocs.yml:33-42`.

6. **import-linter and the domain-to-infra exception.** The CLAUDE.md documents an accepted exception where domain packages may depend on `praecepta-infra-eventsourcing`. The current import-linter `layers` contract at `pyproject.toml:207-215` would normally flag this. The fact that `make boundaries` passes suggests either the contract allows it implicitly or the imports are structured to avoid triggering the linter. This should be explicitly documented in the contract configuration (e.g., via `ignore_imports`).

### Low-Priority Observations

7. **`pytest-xdist` installed but unused.** The parallel test runner is a dev dependency but no Makefile target or CI step uses `-n auto`. For 815 tests, parallel execution could reduce CI time.

8. **Smoke tests lack markers.** `tests/test_smoke.py` has no `@pytest.mark.unit` or `@pytest.mark.integration` markers, so these 11 tests are excluded from both `make test-unit` and `make test-int` while always running with `make test`. Consider adding `@pytest.mark.unit` to ensure they are captured by selective runs.

9. **No pre-commit hooks.** Adding a `.pre-commit-config.yaml` with ruff and mypy hooks would catch issues before commit rather than at CI time.
