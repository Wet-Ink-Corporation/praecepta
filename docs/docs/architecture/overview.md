# Architecture Overview

Praecepta organizes code into four layers with strict dependency boundaries enforced by [`import-linter`](https://import-linter.readthedocs.io/).

## Layer Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: Integration         praecepta.integration.*        │
│  Cross-domain sagas and orchestration                        │
│  Example: praecepta-integration-tenancy-identity             │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: Domain              praecepta.domain.*             │
│  Reusable bounded contexts (aggregates, applications)        │
│  Examples: praecepta-domain-tenancy, praecepta-domain-identity│
├──────────────────────────────────────────────────────────────┤
│  Layer 1: Infrastructure      praecepta.infra.*              │
│  Adapter implementations (FastAPI, PostgreSQL, auth, etc.)   │
│  Examples: praecepta-infra-fastapi, praecepta-infra-auth     │
├──────────────────────────────────────────────────────────────┤
│  Layer 0: Foundation          praecepta.foundation.*         │
│  Pure domain primitives — NO framework dependencies          │
│  Examples: praecepta-foundation-domain, foundation-application│
└──────────────────────────────────────────────────────────────┘
```

## Dependency Rules

Dependencies flow **strictly downward**:

- **Integration** may import from Domain, Infrastructure, and Foundation
- **Domain** may import from Infrastructure and Foundation
- **Infrastructure** may import from Foundation
- **Foundation** may **not** import from any higher layer or external frameworks

These rules are enforced at CI time by `import-linter` contracts defined in the root `pyproject.toml`:

```toml
[[tool.importlinter.contracts]]
name = "Foundation layer is pure (no infrastructure deps)"
type = "forbidden"
source_modules = [
    "praecepta.foundation.domain",
    "praecepta.foundation.application",
]
forbidden_modules = [
    "fastapi", "sqlalchemy", "httpx",
    "structlog", "opentelemetry", "taskiq", "redis",
]

[[tool.importlinter.contracts]]
name = "Package layers are respected"
type = "layers"
layers = [
    "praecepta.integration",
    "praecepta.domain",
    "praecepta.infra",
    "praecepta.foundation",
]
```

## Why Layering Matters

| Benefit | How |
|---------|-----|
| **Testable domain logic** | Foundation has zero external dependencies — unit tests need no mocks |
| **Swappable infrastructure** | Domain defines ports (protocols); infrastructure implements them |
| **Composable packages** | Install only the packages you need; each is independently versioned |
| **Enforced boundaries** | CI fails if someone adds an import that violates layer rules |

## Accepted Exception

Domain packages (Layer 2) may depend on `praecepta-infra-eventsourcing` (Layer 1) for `Application` and `BaseProjection` base classes. These are structural dependencies required by the event sourcing pattern — application services extend `Application[UUID]` and projections extend `BaseProjection`. Extracting these into separate packages would create excessive proliferation without meaningful benefit.
