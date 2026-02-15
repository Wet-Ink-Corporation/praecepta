# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Praecepta is a composable Python framework for building DDD/ES (Domain-Driven Design / Event Sourcing) multi-tenant applications. It is a uv workspaces monorepo containing 11 packages, currently in pre-alpha (v0.1.0) with stub scaffolding in place.

## Commands

```bash
make install        # uv sync --dev
make verify         # Full check: lint + typecheck + boundaries + test
make test           # uv run pytest (all tests)
make test-unit      # uv run pytest -m unit
make test-int       # uv run pytest -m integration
make lint           # uv run ruff check packages/ tests/ --fix
make format         # uv run ruff format packages/ tests/
make typecheck      # uv run mypy (strict mode)
make boundaries     # uv run lint-imports (architecture boundary contracts)
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
