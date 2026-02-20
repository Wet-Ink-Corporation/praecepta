# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Praecepta is a composable Python framework for building DDD/ES (Domain-Driven Design / Event Sourcing) multi-tenant applications. It is a uv workspaces monorepo containing 11 packages, currently in pre-alpha (v0.3.0) with stub scaffolding in place.

## Commands

```bash
make install           # uv sync --dev + install git hooks
make verify            # Full check: lint + typecheck + boundaries + test
make test              # uv run pytest (all tests)
make test-unit         # uv run pytest -m unit
make test-int          # uv run pytest -m integration
make lint              # uv run ruff check packages/ tests/ examples/ --fix
make format            # uv run ruff format packages/ tests/ examples/
make typecheck         # uv run mypy (strict mode)
make boundaries        # uv run lint-imports (architecture boundary contracts)
make docs              # Build documentation site (MkDocs + shadcn)
make docs-dev          # Start docs dev server
make changelog         # Generate CHANGELOG.md from git history
make changelog-preview # Preview unreleased changes
make bump             # Bump version auto-detected from commits (creates commit + tag)
make bump-patch        # Bump patch version (creates commit + tag)
make bump-minor        # Bump minor version (creates commit + tag)
make bump-major        # Bump major version (creates commit + tag)
```

Run a single test file: `uv run pytest path/to/test_file.py`
Run a single test: `uv run pytest path/to/test_file.py::test_name`

## Architecture

### 4-Layer Dependency Hierarchy

All packages live under `packages/` and use **PEP 420 implicit namespace packages** under the `praecepta.*` namespace. Dependencies flow strictly downward — enforced by `import-linter` contracts.

```
Layer 3: Integration   praecepta.integration.*    (cross-domain sagas)
Layer 2: Domain        praecepta.domain.*         (reusable bounded contexts)
Layer 1: Infrastructure praecepta.infra.*         (adapter implementations)
Layer 0: Foundation    praecepta.foundation.*     (pure domain primitives)
```

Foundation packages must never import infrastructure frameworks (fastapi, sqlalchemy, httpx, structlog, opentelemetry, taskiq, redis).

**Accepted exception:** Domain packages (Layer 2) may depend on `praecepta-infra-eventsourcing` (Layer 1) for `Application` and `BaseProjection` base classes. These are structural dependencies required by the eventsourcing pattern — application services extend `Application[UUID]` and projections extend `BaseProjection`. Extracting these into separate packages would create excessive proliferation without meaningful architectural benefit.

### Package Layout Convention

Each package follows this structure:
```
packages/{name}/
├── pyproject.toml
├── src/
│   └── praecepta/              # NO __init__.py (PEP 420 implicit namespace)
│       └── {layer}/{name}/
│           ├── __init__.py     # Leaf package only
│           └── py.typed        # PEP 561 marker
└── tests/
```

Intermediate directories (`praecepta/`, `praecepta/foundation/`, etc.) must **not** have `__init__.py` files — only the leaf package directory gets one.

### Inter-Package Dependencies

Workspace packages reference each other via `[tool.uv.sources]` with `workspace = true` in both the root and individual `pyproject.toml` files. The build backend is hatchling.

### Entry-Point Auto-Discovery

The app factory (`create_app()`) uses Python entry points for plugin-style auto-discovery (PADR-122). Packages register contributions in their `pyproject.toml` under `[project.entry-points]`:

- `praecepta.applications` — Application service singletons
- `praecepta.projections` — Event projection handlers
- `praecepta.middleware` — Middleware contributions (ordering via `MiddlewareContribution`)
- `praecepta.lifespan` — App lifespan hooks (`LifespanContribution`)
- `praecepta.routers` — FastAPI router mounts
- `praecepta.error_handlers` — Exception-to-HTTP-status mappers

### Packages

| Package | Namespace | Layer |
|---------|-----------|-------|
| praecepta-foundation-domain | praecepta.foundation.domain | 0 |
| praecepta-foundation-application | praecepta.foundation.application | 0 |
| praecepta-infra-fastapi | praecepta.infra.fastapi | 1 |
| praecepta-infra-eventsourcing | praecepta.infra.eventsourcing | 1 |
| praecepta-infra-auth | praecepta.infra.auth | 1 |
| praecepta-infra-persistence | praecepta.infra.persistence | 1 |
| praecepta-infra-observability | praecepta.infra.observability | 1 |
| praecepta-infra-taskiq | praecepta.infra.taskiq | 1 |
| praecepta-domain-tenancy | praecepta.domain.tenancy | 2 |
| praecepta-domain-identity | praecepta.domain.identity | 2 |
| praecepta-integration-tenancy-identity | praecepta.integration.tenancy_identity | 3 |

## Code Style

- Python 3.12+, line length 100
- Ruff for linting and formatting (double quotes, spaces)
- mypy in strict mode with `namespace_packages = true` and `explicit_package_bases = true`
- pytest markers: `unit`, `integration`, `slow`; async mode is `strict`
- All `uv run` prefix required for tool invocations (ruff, mypy, pytest, lint-imports)

## Versioning & Releases

### Version Strategy

All 11 packages share a single version number (monorepo-wide versioning). The version is managed by **commitizen** and defined in the `[tool.commitizen]` section of the root `pyproject.toml`. The `version_files` config keeps all 12 `pyproject.toml` files and this file in sync automatically during bumps.

### Commit Conventions

Commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification, enforced by a `commit-msg` pre-commit hook. Format: `type(scope): description`

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Scopes** (optional but encouraged, mapped to packages):
`foundation-domain`, `foundation-app`, `infra-fastapi`, `infra-es`, `infra-auth`, `infra-persistence`, `infra-observability`, `infra-taskiq`, `domain-tenancy`, `domain-identity`, `integration`, `deps`, `release`

**Breaking changes:** Use `feat!:` or `fix!:` suffix, or add a `BREAKING CHANGE:` footer in the commit body.

### Release Process

Releases are triggered via the **Release** workflow (`workflow_dispatch`) on GitHub Actions:

1. Select bump type (patch / minor / major)
2. Workflow runs the full quality gate
3. `cz bump` updates all version files, generates CHANGELOG.md, creates commit and tag
4. Optionally generates a release blog post for the docs site
5. Tag push triggers the Publish workflow (build packages + create GitHub Release)

Local preview: `make changelog-preview` shows unreleased changes.

## Adding a New Package

When adding a new package to the monorepo, update the following locations:

1. **Create the package directory** following the layout convention above
2. **Root `pyproject.toml`** — update four sections:
   - `[project] dependencies` — add the new package name
   - `[tool.uv.sources]` — add `package-name = { workspace = true }`
   - `[tool.mypy] mypy_path` — append `packages/{name}/src` to the colon-separated path
   - `[tool.commitizen] version_files` — add `packages/{name}/pyproject.toml:^version`
3. **This file** — add the package to the Packages table above
4. **Verify** — run `make verify` to confirm lint, types, boundaries, and tests all pass
