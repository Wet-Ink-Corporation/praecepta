# Package Types and Dependencies

## Overview

Three distinct package types with strict dependency rules ensure clean architecture boundaries.

## Package Types

| Type | Purpose | Dependencies | Example |
|------|---------|--------------|---------|
| **Domain (Type 1)** | Business logic, aggregates, events | Zero external deps | `dog_school_domain` |
| **Infrastructure (Type 2)** | Persistence, messaging, adapters | Domain + frameworks | `dog_school_postgres` |
| **Utility (Type 3)** | Cross-cutting, reusable | Zero domain knowledge | `shared_events`, `event_bus` |

## Dependency Hierarchy

```
Domain Packages (center - zero external deps)
    ^ imported by
Infrastructure Packages (depend on domain + frameworks)
    ^ imported by
Application Layer (composes everything)
```

**Critical Rule:** Never reverse these arrows. Infrastructure depends on domain, never the reverse.

## Why This Matters

- **Domain packages** contain pure business logic—no database, no HTTP, no external libraries
- **Infrastructure packages** implement ports defined in domain packages
- **Utility packages** provide cross-cutting functionality without domain knowledge

This separation means:

- Domain logic is testable without mocking infrastructure
- Infrastructure can be swapped without changing domain code
- Boundaries are enforced at compile time via import-linter

## Version Constraints

```toml
# Domain -> Domain (stable, trust semver)
dog-school-domain = "^1.0"

# Domain -> Infrastructure (conservative)
dog-school-postgres = "~1.0"

# Core dependencies (exact for reproducibility)
pydantic = "==2.10.0"
```

## Import Linter Enforcement

```ini
[importlinter:contract:1]
name = Domain has no external dependencies
type = forbidden
source_modules =
    dog_school._shared.events
forbidden_modules =
    fastapi
    sqlalchemy
    redis
    neo4j
    taskiq
```

## Key Points

- Domain packages have zero external dependencies
- Infrastructure implements domain ports
- Dependency arrows point inward (toward domain)
- import-linter enforces boundaries at build time

## Prerequisites

- [Philosophy](con-philosophy.md) - Why modular architecture

## Related

- [Architecture Layers](con-layers.md) - Layer responsibilities
- [Package Structure](ref-package-structure.md) - Directory layout
