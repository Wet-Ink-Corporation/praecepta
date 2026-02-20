# Layer Boundaries & Namespace Compliance

**Collector ID:** 1A
**Dimension:** Architecture
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. PEP 420 Compliance

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

No `__init__.py` files exist in any intermediate namespace directory. All five intermediate directory levels were verified across all 11 packages:

- `packages/*/src/praecepta/__init__.py` -- **0 files found** (correct)
- `packages/*/src/praecepta/foundation/__init__.py` -- **0 files found** (correct)
- `packages/*/src/praecepta/infra/__init__.py` -- **0 files found** (correct)
- `packages/*/src/praecepta/domain/__init__.py` -- **0 files found** (correct)
- `packages/*/src/praecepta/integration/__init__.py` -- **0 files found** (correct)

The convention is documented in `CLAUDE.md:52-59` and consistently applied across all packages.

---

## 2. Leaf Package `__init__.py`

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

All 11 primary leaf packages have `__init__.py` files with `__all__` exports. Sub-packages within packages also have `__init__.py` files. However, two issues were found:

**Findings:**

| File | `__all__` Present | Notes |
|------|:-----------------:|-------|
| `packages/foundation-domain/src/praecepta/foundation/domain/__init__.py:54` | Yes (39 symbols) | Comprehensive |
| `packages/foundation-domain/src/praecepta/foundation/domain/ports/__init__.py:10` | Yes (2 symbols) | Comprehensive |
| `packages/foundation-application/src/praecepta/foundation/application/__init__.py:45` | Yes (23 symbols) | Comprehensive |
| `packages/infra-fastapi/src/praecepta/infra/fastapi/__init__.py:26` | Yes (14 symbols) | Comprehensive |
| `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/__init__.py:13` | Yes (4 symbols) | Comprehensive |
| `packages/infra-fastapi/src/praecepta/infra/fastapi/dependencies/__init__.py:10` | Yes (2 symbols) | Comprehensive |
| `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/__init__.py:11` | Yes (9 symbols) | Comprehensive |
| `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/__init__.py:12` | Yes (4 symbols) | Comprehensive |
| `packages/infra-auth/src/praecepta/infra/auth/__init__.py:38` | Yes (16 symbols) | Comprehensive |
| `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` | **No** | Only docstring: `"""Authentication middleware subpackage."""` |
| `packages/infra-persistence/src/praecepta/infra/persistence/__init__.py:18` | Yes (10 symbols) | Comprehensive |
| `packages/infra-observability/src/praecepta/infra/observability/__init__.py:43` | Yes (9 symbols) | Comprehensive |
| `packages/infra-taskiq/src/praecepta/infra/taskiq/__init__.py:5` | Yes (3 symbols) | Comprehensive |
| `packages/domain-tenancy/src/praecepta/domain/tenancy/__init__.py:6` | Yes (2 symbols) | Comprehensive |
| `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/__init__.py:15` | Yes (5 symbols) | Comprehensive |
| `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/projections/__init__.py:10` | Yes (2 symbols) | Comprehensive |
| `packages/domain-identity/src/praecepta/domain/identity/__init__.py:8` | Yes (4 symbols) | Comprehensive |
| `packages/domain-identity/src/praecepta/domain/identity/infrastructure/__init__.py:18` | Yes (6 symbols) | Comprehensive |
| `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/__init__.py:10` | Yes (2 symbols) | Comprehensive |
| `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` | **No** | Only docstring: `"""Praecepta Integration Tenancy-Identity -- cross-domain sagas and subscriptions."""` |

**Issues:**

- **Low** -- `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` has no `__all__` and no re-exports. The parent `__init__.py` imports the middleware classes directly, so this is functional but inconsistent with the pattern used elsewhere (e.g., `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/__init__.py` which does define `__all__`).
- **Low** -- `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` has no `__all__` and no re-exports. This appears to be a stub package with no implemented functionality yet, so this is expected for the current pre-alpha stage.

---

## 3. `py.typed` Markers

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All 11 primary leaf packages have PEP 561 `py.typed` markers in the correct location:

| Package | Marker Path |
|---------|-------------|
| foundation-domain | `packages/foundation-domain/src/praecepta/foundation/domain/py.typed` |
| foundation-application | `packages/foundation-application/src/praecepta/foundation/application/py.typed` |
| infra-fastapi | `packages/infra-fastapi/src/praecepta/infra/fastapi/py.typed` |
| infra-eventsourcing | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/py.typed` |
| infra-auth | `packages/infra-auth/src/praecepta/infra/auth/py.typed` |
| infra-persistence | `packages/infra-persistence/src/praecepta/infra/persistence/py.typed` |
| infra-observability | `packages/infra-observability/src/praecepta/infra/observability/py.typed` |
| infra-taskiq | `packages/infra-taskiq/src/praecepta/infra/taskiq/py.typed` |
| domain-tenancy | `packages/domain-tenancy/src/praecepta/domain/tenancy/py.typed` |
| domain-identity | `packages/domain-identity/src/praecepta/domain/identity/py.typed` |
| integration-tenancy-identity | `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/py.typed` |

No sub-packages have `py.typed` markers (not required -- the marker at the leaf package level covers the entire subtree).

---

## 4. Layer Isolation

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Foundation packages (Layer 0) contain zero imports of the forbidden infrastructure frameworks. Verified by searching for `import (fastapi|sqlalchemy|httpx|structlog|opentelemetry|taskiq|redis)` across both foundation packages:

- `packages/foundation-domain/src/` -- **0 matches**
- `packages/foundation-application/src/` -- **0 matches**

**Note on `eventsourcing` library:** Foundation-domain imports `eventsourcing.domain.Aggregate` (`packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:23`) and `eventsourcing.domain.DomainEvent` (`packages/foundation-domain/src/praecepta/foundation/domain/events.py:60`). The `eventsourcing` Python library is intentionally NOT in the forbidden list -- it provides pure domain primitives (Aggregate, DomainEvent) that are conceptually part of the domain layer. The forbidden list (`pyproject.toml:196-204`) targets infrastructure frameworks (fastapi, sqlalchemy, httpx, structlog, opentelemetry, taskiq, redis), which is correct.

This is enforced by import-linter contract at `pyproject.toml:189-204`.

---

## 5. Downward-Only Dependencies

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Comprehensive import analysis across all packages confirms strict downward-only dependency flow:

| Source Layer | Imports from Upper Layers | Result |
|-------------|--------------------------|--------|
| Foundation (L0) -> Infra (L1) | `from praecepta.infra` in foundation-domain/src | **0 matches** |
| Foundation (L0) -> Infra (L1) | `from praecepta.infra` in foundation-application/src | **0 matches** |
| Foundation (L0) -> Domain (L2) | `from praecepta.domain` in foundation-domain/src | **0 matches** |
| Foundation (L0) -> Domain (L2) | `from praecepta.domain` in foundation-application/src | **0 matches** |
| Foundation (L0) -> Integration (L3) | `from praecepta.integration` in foundation-*/src | **0 matches** |
| Infra (L1) -> Domain (L2) | `from praecepta.domain` in all infra-*/src | **0 matches** |
| Infra (L1) -> Integration (L3) | `from praecepta.integration` in all infra-*/src | **0 matches** |
| Domain (L2) -> Integration (L3) | `from praecepta.integration` in domain-tenancy/src | **0 matches** |
| Domain (L2) -> Integration (L3) | `from praecepta.integration` in domain-identity/src | **0 matches** |

This is additionally enforced by the import-linter layers contract at `pyproject.toml:207-215`.

---

## 6. Accepted Exception

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Domain packages (Layer 2) depend on `praecepta-infra-eventsourcing` (Layer 1) exclusively for `BaseProjection`. The imports are precisely scoped:

| File | Import |
|------|--------|
| `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/projections/tenant_config.py:12` | `from praecepta.infra.eventsourcing.projections.base import BaseProjection` |
| `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/projections/tenant_list.py:13` | `from praecepta.infra.eventsourcing.projections.base import BaseProjection` |
| `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/agent_api_key.py:12` | `from praecepta.infra.eventsourcing.projections.base import BaseProjection` |
| `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:13` | `from praecepta.infra.eventsourcing.projections.base import BaseProjection` |

**Note on Application base class:** The domain application services (`TenantApplication`, `UserApplication`, `AgentApplication`) import `Application` from the `eventsourcing` library directly (`from eventsourcing.application import Application`), NOT from `praecepta.infra.eventsourcing`. This means the accepted exception for `Application` is technically not exercised -- the domain packages bypass the infra wrapper entirely, importing from the third-party library. This is actually a cleaner dependency path.

Relevant files:
- `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant_app.py:12`
- `packages/domain-identity/src/praecepta/domain/identity/user_app.py:12`
- `packages/domain-identity/src/praecepta/domain/identity/agent_app.py:12`

The dependency on `praecepta-infra-eventsourcing` is declared in both domain packages' `pyproject.toml`:
- `packages/domain-tenancy/pyproject.toml:13`
- `packages/domain-identity/pyproject.toml:13`

**Additional observation:** Both domain packages also declare `sqlalchemy>=2.0` as a dependency (`packages/domain-tenancy/pyproject.toml:14`, `packages/domain-identity/pyproject.toml:14`). SQLAlchemy is used in their `infrastructure/` sub-packages for repository and projection implementations:
- `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/config_repository.py:13` -- `from sqlalchemy import text`
- `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/tenant_repository.py:11` -- `from sqlalchemy import text`
- `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:14` -- `from sqlalchemy import text`
- `packages/domain-identity/src/praecepta/domain/identity/infrastructure/agent_api_key_repository.py:13` -- `from sqlalchemy import text`

This is acceptable per the architecture -- domain packages (Layer 2) are above infrastructure (Layer 1) and can use infrastructure libraries. The restriction on infrastructure frameworks applies only to foundation packages (Layer 0).

---

## 7. import-linter Contracts

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Two import-linter contracts are defined in `pyproject.toml:184-215`:

**Contract 1 -- Foundation Purity** (`pyproject.toml:189-204`):
- Type: `forbidden`
- Source modules: `praecepta.foundation.domain`, `praecepta.foundation.application`
- Forbidden modules: `fastapi`, `sqlalchemy`, `httpx`, `structlog`, `opentelemetry`, `taskiq`, `redis`
- Status: Correctly configured and verifiable via `make boundaries` / `uv run lint-imports`

**Contract 2 -- Layer Ordering** (`pyproject.toml:207-215`):
- Type: `layers`
- Layers (top to bottom): `praecepta.integration` > `praecepta.domain` > `praecepta.infra` > `praecepta.foundation`
- Status: Correctly configured for downward-only enforcement

Root config: `[tool.importlinter] root_packages = ["praecepta"]` with `include_external_packages = true` (`pyproject.toml:185-186`).

The `Makefile` target `make boundaries` invokes `uv run lint-imports` (`CLAUDE.md:20`), integrating contract verification into the CI workflow.

---

## 8. Build Backend

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All 11 packages use hatchling as the build backend:

| Package | File:Line | Build Backend |
|---------|-----------|---------------|
| foundation-domain | `packages/foundation-domain/pyproject.toml:16-17` | `hatchling.build` |
| foundation-application | `packages/foundation-application/pyproject.toml:18-19` | `hatchling.build` |
| infra-fastapi | `packages/infra-fastapi/pyproject.toml:22-23` | `hatchling.build` |
| infra-eventsourcing | `packages/infra-eventsourcing/pyproject.toml:24-25` | `hatchling.build` |
| infra-auth | `packages/infra-auth/pyproject.toml:28-29` | `hatchling.build` |
| infra-persistence | `packages/infra-persistence/pyproject.toml:25-26` | `hatchling.build` |
| infra-observability | `packages/infra-observability/pyproject.toml:28-29` | `hatchling.build` |
| infra-taskiq | `packages/infra-taskiq/pyproject.toml:15-16` | `hatchling.build` |
| domain-tenancy | `packages/domain-tenancy/pyproject.toml:29-30` | `hatchling.build` |
| domain-identity | `packages/domain-identity/pyproject.toml:30-31` | `hatchling.build` |
| integration-tenancy-identity | `packages/integration-tenancy-identity/pyproject.toml:19-20` | `hatchling.build` |

All packages also consistently declare `[tool.hatch.build.targets.wheel] packages = ["src/praecepta"]`.

---

## 9. Workspace Sources

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All inter-package dependencies are correctly declared with `workspace = true` in `[tool.uv.sources]`:

| Package | Workspace Dependencies | File:Line |
|---------|----------------------|-----------|
| foundation-domain | None (no workspace deps) | N/A |
| foundation-application | praecepta-foundation-domain | `packages/foundation-application/pyproject.toml:14-15` |
| infra-fastapi | praecepta-foundation-domain, praecepta-foundation-application | `packages/infra-fastapi/pyproject.toml:17-19` |
| infra-eventsourcing | praecepta-foundation-domain, praecepta-foundation-application | `packages/infra-eventsourcing/pyproject.toml:19-21` |
| infra-auth | praecepta-foundation-domain, praecepta-foundation-application | `packages/infra-auth/pyproject.toml:19-21` |
| infra-persistence | praecepta-foundation-domain, praecepta-foundation-application | `packages/infra-persistence/pyproject.toml:19-21` |
| infra-observability | praecepta-foundation-application | `packages/infra-observability/pyproject.toml:18-19` |
| infra-taskiq | None (no workspace deps) | N/A |
| domain-tenancy | praecepta-foundation-domain, praecepta-foundation-application, praecepta-infra-eventsourcing | `packages/domain-tenancy/pyproject.toml:17-20` |
| domain-identity | praecepta-foundation-domain, praecepta-foundation-application, praecepta-infra-eventsourcing | `packages/domain-identity/pyproject.toml:17-20` |
| integration-tenancy-identity | praecepta-domain-tenancy, praecepta-domain-identity | `packages/integration-tenancy-identity/pyproject.toml:15-17` |

Every dependency listed in `[project] dependencies` that references a workspace package has a corresponding `workspace = true` entry in `[tool.uv.sources]`. No workspace dependency is missing its source mapping.

---

## 10. Root pyproject.toml

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The root `pyproject.toml` correctly lists all 11 packages in both required sections:

**`[project] dependencies`** (`pyproject.toml:18-30`):
1. praecepta-foundation-domain
2. praecepta-foundation-application
3. praecepta-infra-fastapi
4. praecepta-infra-eventsourcing
5. praecepta-infra-auth
6. praecepta-infra-persistence
7. praecepta-infra-observability
8. praecepta-infra-taskiq
9. praecepta-domain-tenancy
10. praecepta-domain-identity
11. praecepta-integration-tenancy-identity

**`[tool.uv.sources]`** (`pyproject.toml:42-53`):
All 11 packages listed with `workspace = true`.

**`[tool.uv.workspace]`** (`pyproject.toml:39-40`):
`members = ["packages/*"]` -- wildcard covers all packages.

---

## 11. mypy Paths

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All 11 package `src/` directories are listed in the mypy_path (`pyproject.toml:157`):

```
mypy_path = "packages/foundation-domain/src:packages/foundation-application/src:packages/infra-fastapi/src:packages/infra-eventsourcing/src:packages/infra-auth/src:packages/infra-persistence/src:packages/infra-observability/src:packages/infra-taskiq/src:packages/domain-tenancy/src:packages/domain-identity/src:packages/integration-tenancy-identity/src"
```

Cross-checked against all 11 `packages/*/pyproject.toml` entries -- complete match. Additionally, mypy is configured with `namespace_packages = true` and `explicit_package_bases = true` (`pyproject.toml:172-173`), which is required for PEP 420 implicit namespace packages.

---

## 12. Package Naming Convention

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All package directory names correctly map to their namespace paths:

| Package Directory | Namespace Path | Convention Match |
|-------------------|---------------|:----------------:|
| `packages/foundation-domain/` | `praecepta.foundation.domain` | Yes |
| `packages/foundation-application/` | `praecepta.foundation.application` | Yes |
| `packages/infra-fastapi/` | `praecepta.infra.fastapi` | Yes |
| `packages/infra-eventsourcing/` | `praecepta.infra.eventsourcing` | Yes |
| `packages/infra-auth/` | `praecepta.infra.auth` | Yes |
| `packages/infra-persistence/` | `praecepta.infra.persistence` | Yes |
| `packages/infra-observability/` | `praecepta.infra.observability` | Yes |
| `packages/infra-taskiq/` | `praecepta.infra.taskiq` | Yes |
| `packages/domain-tenancy/` | `praecepta.domain.tenancy` | Yes |
| `packages/domain-identity/` | `praecepta.domain.identity` | Yes |
| `packages/integration-tenancy-identity/` | `praecepta.integration.tenancy_identity` | Yes |

The naming convention is `{layer}-{name}` for directories and `praecepta.{layer}.{name}` for namespaces, with hyphens in directory names mapping to dots in namespace paths (except `tenancy_identity` which uses an underscore in the Python namespace, consistent with Python identifier rules).

---

## 13. Consistent Version

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All 12 `pyproject.toml` files (root + 11 packages) share the same version string: `"0.3.0"`.

| File | Line | Version |
|------|:----:|---------|
| `pyproject.toml` | 3 | 0.3.0 |
| `packages/foundation-domain/pyproject.toml` | 3 | 0.3.0 |
| `packages/foundation-application/pyproject.toml` | 3 | 0.3.0 |
| `packages/infra-fastapi/pyproject.toml` | 3 | 0.3.0 |
| `packages/infra-eventsourcing/pyproject.toml` | 3 | 0.3.0 |
| `packages/infra-auth/pyproject.toml` | 3 | 0.3.0 |
| `packages/infra-persistence/pyproject.toml` | 3 | 0.3.0 |
| `packages/infra-observability/pyproject.toml` | 3 | 0.3.0 |
| `packages/infra-taskiq/pyproject.toml` | 3 | 0.3.0 |
| `packages/domain-tenancy/pyproject.toml` | 3 | 0.3.0 |
| `packages/domain-identity/pyproject.toml` | 3 | 0.3.0 |
| `packages/integration-tenancy-identity/pyproject.toml` | 3 | 0.3.0 |

**Note:** `CLAUDE.md:7` states "currently in pre-alpha (v0.1.0)" but the actual version across all packages is `0.3.0`. This is a documentation drift issue.

---

## 14. Namespace Consistency

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All package namespace paths match their `pyproject.toml` metadata. Each package's `name` field in `[project]` follows the pattern `praecepta-{layer}-{name}`, and the source layout under `src/praecepta/{layer}/{name}/` corresponds exactly:

| pyproject.toml `name` | Source Path | Match |
|-----------------------|-------------|:-----:|
| praecepta-foundation-domain | `src/praecepta/foundation/domain/` | Yes |
| praecepta-foundation-application | `src/praecepta/foundation/application/` | Yes |
| praecepta-infra-fastapi | `src/praecepta/infra/fastapi/` | Yes |
| praecepta-infra-eventsourcing | `src/praecepta/infra/eventsourcing/` | Yes |
| praecepta-infra-auth | `src/praecepta/infra/auth/` | Yes |
| praecepta-infra-persistence | `src/praecepta/infra/persistence/` | Yes |
| praecepta-infra-observability | `src/praecepta/infra/observability/` | Yes |
| praecepta-infra-taskiq | `src/praecepta/infra/taskiq/` | Yes |
| praecepta-domain-tenancy | `src/praecepta/domain/tenancy/` | Yes |
| praecepta-domain-identity | `src/praecepta/domain/identity/` | Yes |
| praecepta-integration-tenancy-identity | `src/praecepta/integration/tenancy_identity/` | Yes |

All packages use `[tool.hatch.build.targets.wheel] packages = ["src/praecepta"]` consistently.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Items rated | 14 |
| Average maturity | 4.93 / 5.00 |
| Rating 5 (Optimizing) | 12 |
| Rating 4 (Managed) | 2 |
| Rating 3 (Defined) | 0 |
| Rating 2 (Initial) | 0 |
| Rating 1 (Not Implemented) | 0 |

### Findings by Severity

| Severity | Count | Details |
|----------|:-----:|---------|
| Critical | 0 | -- |
| High | 0 | -- |
| Medium | 0 | -- |
| Low | 2 | Missing `__all__` in infra-auth middleware and integration-tenancy-identity `__init__.py` |
| Info | 12 | All passing checks |

---

## Additional Observations

### 1. CLAUDE.md Version Drift (Low)

`CLAUDE.md:7` states the project is "currently in pre-alpha (v0.1.0)" but all `pyproject.toml` files show `version = "0.3.0"`. The version has been bumped three times without updating the documentation. This should be corrected to avoid confusion for new contributors.

- **File:** `CLAUDE.md:7`
- **Severity:** Low
- **Confidence:** High

### 2. Domain Infrastructure Sub-Packages Are Well-Structured (Info)

Both domain packages (`domain-tenancy`, `domain-identity`) have an `infrastructure/` sub-package containing repositories and projections. These sub-packages correctly:
- Have `__init__.py` with `__all__` exports
- Import `BaseProjection` only from `praecepta.infra.eventsourcing.projections.base` (the accepted exception)
- Use SQLAlchemy for repository implementations (acceptable for Layer 2)
- Follow a consistent `infrastructure/projections/` nesting pattern

### 3. Entry-Point Auto-Discovery Is Consistently Applied (Info)

Seven of the 11 packages register entry points, covering all documented extension point categories:
- `praecepta.applications`: domain-tenancy (`pyproject.toml:22-23`), domain-identity (`pyproject.toml:22-24`)
- `praecepta.projections`: domain-tenancy (`pyproject.toml:25-27`), domain-identity (`pyproject.toml:26-28`)
- `praecepta.middleware`: infra-fastapi (`pyproject.toml:31-34`), infra-auth (`pyproject.toml:23-25`), infra-observability (`pyproject.toml:21-22`)
- `praecepta.lifespan`: infra-eventsourcing (`pyproject.toml:27-29`), infra-observability (`pyproject.toml:24-25`)
- `praecepta.routers`: infra-fastapi (`pyproject.toml:28-29`)
- `praecepta.error_handlers`: infra-fastapi (`pyproject.toml:36-37`)

### 4. infra-observability Missing praecepta-foundation-domain Dependency (Info)

`packages/infra-observability/pyproject.toml:11` lists only `praecepta-foundation-application` as a workspace dependency but not `praecepta-foundation-domain`. Since `foundation-application` transitively depends on `foundation-domain`, this works at runtime. However, if `infra-observability` ever directly imports from `praecepta.foundation.domain`, it would need the explicit dependency. Currently, its only foundation import is `from praecepta.foundation.application.contributions import LifespanContribution` (`packages/infra-observability/src/praecepta/infra/observability/__init__.py:8`), so the transitive dependency is sufficient.

### 5. infra-taskiq Is Isolated (Info)

`packages/infra-taskiq/` has no workspace dependencies at all -- it depends only on `taskiq` and `taskiq-redis`. This means it is completely decoupled from the rest of the praecepta ecosystem. This is either intentional (the broker is standalone infrastructure) or indicates missing integration with the foundation layer.

- **File:** `packages/infra-taskiq/pyproject.toml:10-13`
- **Severity:** Info
- **Confidence:** Medium
