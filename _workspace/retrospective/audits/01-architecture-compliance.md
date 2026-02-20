# Dimension 1: Architecture Compliance

**RAG Status:** AMBER
**Average Maturity:** 4.4/5
**Date:** 2026-02-18

## Executive Summary

The Praecepta monorepo demonstrates strong architectural discipline across its 11-package, 4-layer hierarchy. PEP 420 implicit namespace compliance is perfect -- no stray `__init__.py` files exist in any intermediate directory. Layer isolation is rigorously enforced: foundation packages (Layer 0) import zero forbidden infrastructure frameworks, and the two import-linter contracts (forbidden imports and layer ordering) correctly codify the architectural rules. All packages use a consistent build backend (hatchling), consistent versioning (0.3.0), correctly declared workspace sources, and complete mypy path coverage. The entry-point auto-discovery system (PADR-122) is well-implemented with 20 active entry points across 6 groups, a well-structured app factory, and robust graceful degradation on failures.

The single factor preventing a GREEN rating is one High-severity finding: the 70% code coverage threshold declared in `[tool.coverage.report]` is not actually enforced in CI because the pytest command does not pass `--cov-fail-under=70`. This means the quality gate has a gap that could allow coverage regression to go undetected. Additionally, there are 11 Medium-severity findings spanning type safety gaps in the discovery/contribution types (use of `Any` rather than proper protocols), an unimplemented `praecepta.subscriptions` entry-point group, documentation drift (version, Makefile descriptions), incomplete mkdocstrings paths, absence of dependency security scanning, and the local `make verify` target auto-fixing code before testing (diverging from CI behavior).

Overall, the architecture is well-conceived and consistently applied. The findings are primarily about hardening enforcement mechanisms, improving type safety at plugin boundaries, and keeping documentation synchronized -- all signs of a maturing codebase that has outpaced its initial scaffolding documentation.

## Consolidated Checklist

| # | Area | Item | Rating | Severity | Source |
|---|------|------|--------|----------|--------|
| 1 | Namespace | PEP 420 Compliance | 5/5 | Info | 1A |
| 2 | Namespace | Leaf Package `__init__.py` | 4/5 | Low | 1A |
| 3 | Namespace | `py.typed` Markers | 5/5 | Info | 1A |
| 4 | Layer Rules | Layer Isolation (Foundation Purity) | 5/5 | Info | 1A |
| 5 | Layer Rules | Downward-Only Dependencies | 5/5 | Info | 1A |
| 6 | Layer Rules | Accepted Exception (Domain->Infra ES) | 5/5 | Info | 1A |
| 7 | Layer Rules | import-linter Contracts | 5/5 | Info | 1A |
| 8 | Build | Build Backend Consistency | 5/5 | Info | 1A |
| 9 | Workspace | Workspace Sources | 5/5 | Info | 1A |
| 10 | Workspace | Root pyproject.toml | 5/5 | Info | 1A |
| 11 | Workspace | mypy Paths | 5/5 | Info | 1A |
| 12 | Naming | Package Naming Convention | 5/5 | Info | 1A |
| 13 | Versioning | Consistent Version | 5/5 | Info | 1A |
| 14 | Naming | Namespace Consistency | 5/5 | Info | 1A |
| 15 | Discovery | Discovery Module | 5/5 | Info | 1B |
| 16 | Discovery | Contribution Types | 4/5 | Medium | 1B |
| 17 | Discovery | App Factory | 5/5 | Info | 1B |
| 18 | Discovery | Middleware Ordering | 5/5 | Info | 1B |
| 19 | Discovery | Lifespan Hooks | 5/5 | Info | 1B |
| 20 | Discovery | Projection Registration | 4/5 | Low | 1B |
| 21 | Discovery | Error Handler Registration | 4/5 | Low | 1B |
| 22 | Discovery | Router Mounting | 3/5 | Medium | 1B |
| 23 | Discovery | Entry-Point Declarations | 4/5 | Medium | 1B |
| 24 | Discovery | Graceful Degradation | 5/5 | Info | 1B |
| 25 | Discovery | Type Safety | 3/5 | Medium | 1B |
| 26 | Testing | Test Coverage (Discovery) | 4/5 | Low | 1B |
| 27 | Discovery | PADR-122 Alignment | 4/5 | Medium | 1B |
| 28 | CI/Build | Makefile Targets | 4/5 | Medium | 1C |
| 29 | CI/Build | GitHub Workflows | 4/5 | Medium | 1C |
| 30 | CI/Build | Coverage Configuration | 3/5 | High | 1C |
| 31 | CI/Build | mypy Configuration | 5/5 | Info | 1C |
| 32 | CI/Build | import-linter Configuration | 4/5 | Medium | 1C |
| 33 | Workspace | Workspace Members | 5/5 | Info | 1C |
| 34 | CI/Build | Cross-Package Dependencies | 4/5 | Low | 1C |
| 35 | CI/Build | Dev Dependencies | 4/5 | Medium | 1C |
| 36 | Testing | Root Test Configuration | 4/5 | Low | 1C |
| 37 | Documentation | CLAUDE.md Accuracy | 3/5 | Medium | 1C |

### RAG Calculation

- **Total checklist items:** 37
- **Sum of ratings:** (1A: 12x5 + 2x4 = 68) + (1B: 5x5 + 6x4 + 2x3 = 55) + (1C: 2x5 + 6x4 + 2x3 = 40) = 163
- **Average maturity:** 163 / 37 = **4.41 / 5**
- **Items at 4+:** 33 / 37 = **89.2%**
- **Items at 3+:** 37 / 37 = **100%**
- **Severity counts:** 0 Critical, 1 High, 11 Medium, 14 Low, 48 Info
- **GREEN requires:** 0 Critical AND 0 High AND avg >= 4.0 AND >= 80% at 4+ --> **FAILS** (1 High finding)
- **AMBER requires:** 0 Critical AND <= 2 High AND avg >= 3.0 AND >= 60% at 3+ --> **PASSES**
- **Result: AMBER**

## Critical & High Findings

### High Severity

**H1. Coverage threshold not enforced in CI** (Source: 1C)

The `fail_under = 70` setting in `[tool.coverage.report]` at `pyproject.toml:140-149` is not enforced during CI test runs. The CI command at `.github/workflows/quality.yml:44` runs `uv run pytest --tb=short --cov --cov-report=term-missing` but does NOT pass `--cov-fail-under=70`. The `fail_under` setting in `[tool.coverage.report]` is only enforced when `coverage report` is explicitly invoked as a separate command, not by pytest-cov's `--cov` flag alone. This means the 70% coverage threshold is effectively a dead letter in the CI pipeline, and coverage regressions can merge without detection.

**Fix:** Add `--cov-fail-under=70` to the pytest command at `.github/workflows/quality.yml:44`.

## Medium Findings

**M1. Contribution types use `Any` instead of typed protocols** (Source: 1B)

`ErrorHandlerContribution.handler` at `packages/foundation-application/src/praecepta/foundation/application/contributions.py:40` and `LifespanContribution.hook` at `contributions.py:52` use `Any` for callable fields. The intended signatures are documented in comments but not enforced by the type system.

**M2. `DiscoveredContribution.value` is `Any`** (Source: 1B)

At `packages/foundation-application/src/praecepta/foundation/application/discovery.py:29`, the loaded entry point value is untyped. The `discover()` function could be made generic (`discover[T]()`) to return `DiscoveredContribution[T]`. Currently, all consumers perform runtime `isinstance` checks to compensate.

**M3. `compose_lifespan()` return type is `object`** (Source: 1B)

At `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py:24`, the return type should be the proper `Callable[[FastAPI], AsyncContextManager[None]]` or equivalent.

**M4. Router mounting only proven with stub** (Source: 1B)

The `praecepta.routers` entry-point group has only one declaration: the health stub at `packages/infra-fastapi/pyproject.toml:29`. Domain packages (`domain-tenancy`, `domain-identity`) do not declare router entry points despite being the primary expected contributors. No `RouterContribution` wrapper exists to enforce prefix/tags metadata.

**M5. `praecepta.subscriptions` group not implemented** (Source: 1B)

PADR-122 documents a `praecepta.subscriptions` group at `_kb/decisions/patterns/PADR-122-entry-point-auto-discovery.md:51`, but no package declares entries in this group and no consumer code exists. The `integration-tenancy-identity` package, which is the expected contributor, has no entry points at all.

**M6. Entry-point declarations incomplete for infra packages** (Source: 1B)

`infra-persistence` (`packages/infra-persistence/pyproject.toml`) and `infra-taskiq` (`packages/infra-taskiq/pyproject.toml`) have no entry-point declarations. These could contribute lifespan hooks for database pool initialization and task broker startup respectively.

**M7. `make verify` auto-fixes before testing** (Source: 1C)

The local `verify` target at `Makefile:25-30` runs `ruff check --fix` and `ruff format`, mutating source files before running mypy and pytest. CI correctly separates check-only (no fix) and format-check (with `--check` flag) at `.github/workflows/quality.yml:32-35`. This divergence means code that passes `make verify` locally could still fail in CI.

**M8. No dependency security scanning** (Source: 1C)

No `pip-audit`, `safety`, or Dependabot configuration found across `.github/workflows/` or dev dependencies at `pyproject.toml:56-65`. For a framework project, dependency supply chain security is important.

**M9. CLAUDE.md version drift** (Source: 1A, 1C)

`CLAUDE.md:7` states "currently in pre-alpha (v0.1.0)" but all 12 `pyproject.toml` files show `version = "0.3.0"`. This was independently identified by both collectors 1A and 1C.

**M10. Docs mkdocstrings paths incomplete** (Source: 1C)

At `docs/mkdocs.yml:50-59`, the mkdocstrings Python handler paths are missing `infra-taskiq/src` and `integration-tenancy-identity/src`. These two packages would not be included in API reference auto-generation. CLAUDE.md does not document docs paths as a configuration touchpoint when adding new packages.

**M11. import-linter accepted exception not explicitly configured** (Source: 1C)

The CLAUDE.md documents an accepted exception where domain packages may depend on `praecepta-infra-eventsourcing`. The layers contract at `pyproject.toml:207-215` would normally flag domain-to-infra imports. The fact that `make boundaries` passes suggests the contract permits this implicitly, but the exception is not explicitly documented in the contract configuration via `ignore_imports`. This should be made explicit.

## Low & Info Findings

### Low Findings (14 total)

- **Missing `__all__` in two `__init__.py` files** (1A): `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` and `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` lack `__all__` exports, inconsistent with the pattern in all other packages.
- **CLAUDE.md `make lint` description incomplete** (1C): Actual target also runs `ruff format` (`Makefile:12-14` vs `CLAUDE.md:17`).
- **CLAUDE.md `make verify` description incomplete** (1C): Actual target runs 5 steps but only 4 are documented (`Makefile:25-30` vs `CLAUDE.md:12`).
- **Projection discovery lacks `exclude_names` support** (1B): Individual projections cannot be excluded at the app factory level, unlike middleware/routers/error handlers.
- **Error handler only uses callable pattern** (1B): Only `infra-fastapi` declares error handler entry points; no package uses the `ErrorHandlerContribution` dataclass pattern.
- **No `--cov` in local `make test`** (1C): Coverage is only measured in CI, not during local development.
- **No coverage report upload** (1C): Coverage results exist only in CI logs; no Codecov/Coveralls integration.
- **`pytest-xdist` installed but unused** (1C): Available for parallel execution but no target uses `-n auto` (`pyproject.toml:60`).
- **Smoke tests lack markers** (1C): `tests/test_smoke.py` has no `@pytest.mark.unit` or `@pytest.mark.integration` markers.
- **No pre-commit hooks** (1C): No `.pre-commit-config.yaml` for local quality gates.
- **`infra-taskiq` fully isolated** (1A, 1C): Zero workspace dependencies (`packages/infra-taskiq/pyproject.toml:10-13`); does not use foundation types.
- **No uv dependency caching in CI** (1C): Adding `uv cache` could speed up builds (`.github/workflows/quality.yml:28-29`).
- **Domain packages depend on SQLAlchemy directly** (1C): Both `domain-tenancy/pyproject.toml:14` and `domain-identity/pyproject.toml:14` declare `sqlalchemy>=2.0` for their infrastructure sub-packages.
- **Discovery test gaps** (1B): No tests for failing entry points, middleware priority ordering via discovery, error handler callable pattern, projection discovery end-to-end, or non-conforming entry point values.

### Info Findings (48 total)

All remaining items across the three collectors represent passing checks, correct configurations, and well-functioning subsystems. Key highlights include: perfect PEP 420 compliance across all packages, all `py.typed` markers present, consistent hatchling build backend, 815 passing tests, strict mypy with full namespace package support, correct Python 3.12+3.13 CI matrix, well-structured publish and docs workflows, and sensible middleware/lifespan priority ordering.

## Cross-Cutting Themes

### Theme 1: Documentation Drift

Multiple findings across collectors 1A and 1C converge on documentation not keeping pace with code evolution. The version number in CLAUDE.md is stale (v0.1.0 vs v0.3.0), Makefile target descriptions are incomplete (`make lint` and `make verify`), and the docs configuration (`mkdocs.yml`) has not been updated for all packages. This suggests that the "Adding a New Package" checklist in CLAUDE.md should be expanded to include documentation touchpoints.

### Theme 2: Type Safety at Plugin Boundaries

Collectors 1B and 1C both surface that the entry-point/contribution system trades type safety for flexibility. The `DiscoveredContribution.value` is `Any`, contribution callable fields are `Any`, and `compose_lifespan()` returns `object`. While runtime `isinstance` checks compensate, the strict mypy configuration (5/5 rating) cannot verify conformance at these plugin boundaries. This is a systemic gap between the strong internal type discipline and the weaker plugin-boundary typing.

### Theme 3: CI/Local Parity Gap

The local `make verify` auto-fixes code before testing, while CI correctly uses check-only flags. The coverage threshold is configured but not enforced in CI. Local `make test` does not measure coverage at all. These three findings (from 1C) point to a broader theme: the local development experience and CI pipeline have subtle behavioral differences that could allow issues to slip through.

### Theme 4: Scaffolding vs. Completion

Several Medium findings reflect the pre-alpha nature of the project: only a stub health router exercises the `praecepta.routers` discovery, the `praecepta.subscriptions` group is completely unimplemented, `integration-tenancy-identity` is empty, and `infra-taskiq`/`infra-persistence` lack entry-point declarations. The architecture is well-designed for extensibility but many extension points are not yet exercised by real domain code.

## Strengths

1. **Perfect namespace compliance.** PEP 420 implicit namespaces are flawlessly implemented across all 11 packages with zero stray `__init__.py` files, correct `py.typed` markers, and consistent `src/praecepta/{layer}/{name}/` layout. This is difficult to get right in a monorepo and it is executed perfectly.

2. **Rigorous layer enforcement.** Two import-linter contracts (forbidden imports and layer ordering) are backed by zero violations found through comprehensive import analysis. The 4-layer hierarchy is both documented and mechanically enforced, with the accepted domain-to-infra exception precisely scoped to `BaseProjection` imports only.

3. **Well-engineered entry-point system.** The `discover()` utility, contribution dataclasses with priority-based ordering, `AsyncExitStack`-based lifespan composition, and LIFO-correct middleware registration demonstrate sophisticated plugin architecture. 20 entry points across 6 active groups are correctly wired with no priority collisions.

4. **Excellent graceful degradation.** Every boundary between entry-point discovery and consumption handles failures gracefully: failing entry points are logged and skipped, non-conforming values generate warnings, missing projections/applications yield no-ops, and poller failures trigger cleanup before re-raise.

5. **Consistent tooling and configuration.** All 11 packages share identical build backend (hatchling), version (0.3.0), wheel target configuration, and workspace source declarations. mypy strict mode, ruff formatting, and pytest markers are uniformly applied.

## Recommendations

**P1 -- Fix within current sprint:**

1. **Enforce coverage threshold in CI.** Add `--cov-fail-under=70` to the pytest command at `.github/workflows/quality.yml:44`. This is a one-line fix that closes the highest-severity gap.

2. **Update CLAUDE.md version reference.** Change `CLAUDE.md:7` from "v0.1.0" to "v0.3.0" (or remove the hardcoded version and refer to `pyproject.toml`).

3. **Align `make verify` with CI behavior.** Either add a `make verify-ci` target that uses `--check` flags (matching CI), or update `make verify` to not auto-fix. Document the difference in CLAUDE.md.

**P2 -- Fix within next 2 sprints:**

4. **Add typed protocols for contribution callables.** Replace `Any` in `ErrorHandlerContribution.handler`, `LifespanContribution.hook`, and `DiscoveredContribution.value` with proper `Protocol` types or `Callable` signatures at `packages/foundation-application/src/praecepta/foundation/application/contributions.py`. Consider making `discover()` generic.

5. **Add dependency security scanning.** Introduce `pip-audit` or Dependabot to the CI pipeline. Add a workflow or step in `quality.yml`.

6. **Complete mkdocstrings paths.** Add `infra-taskiq/src` and `integration-tenancy-identity/src` to `docs/mkdocs.yml:50-59`. Update the "Adding a New Package" checklist in CLAUDE.md to include docs configuration.

7. **Make the domain-to-infra exception explicit in import-linter.** Add an `ignore_imports` directive to the layers contract at `pyproject.toml:207-215` that explicitly documents the accepted `praecepta.domain -> praecepta.infra.eventsourcing` dependency.

**P3 -- Address in backlog:**

8. **Implement `praecepta.subscriptions` entry-point group.** Wire it in the integration-tenancy-identity package as specified in PADR-122, or formally remove it from the ADR if the design has changed.

9. **Add missing `__all__` exports.** Address the two `__init__.py` files lacking `__all__`: `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` and `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1`.

10. **Enable `pytest-xdist` in CI.** Add `-n auto` to the CI pytest command to leverage parallel test execution for 815+ tests.

11. **Add failure-mode tests for discovery.** Cover failing entry points, non-conforming values, middleware priority ordering via discovery, and the error handler callable pattern.

12. **Add `@pytest.mark.unit` to smoke tests.** Ensure `tests/test_smoke.py` is captured by `make test-unit` runs.

13. **Evaluate `infra-taskiq` integration.** Determine whether the package's complete isolation from the workspace (zero workspace dependencies) is intentional or indicates missing integration with foundation types.
