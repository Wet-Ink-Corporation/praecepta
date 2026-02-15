# Architecture Layers

## Overview

Four distinct layers with clear responsibilities and dependency rules.

## Layer Diagram

```
+-------------------------------------------------------------+
|                         API Layer                           |
|  FastAPI routes, request/response DTOs, authentication      |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                    Application Layer                        |
|  Commands, Queries, Handlers, Use case orchestration        |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                      Domain Layer                           |
|  Aggregates, Entities, Value Objects, Domain Events         |
|  PURE PYTHON - No framework dependencies                    |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                   Infrastructure Layer                      |
|  Repositories, Event Store, External Services, Projections  |
+-------------------------------------------------------------+
```

## Layer Responsibilities

### API Layer

- FastAPI routes and endpoint definitions
- Request/response DTOs (Pydantic models)
- Authentication and authorization middleware
- Input validation and error response formatting

### Application Layer

- Command handlers (write operations)
- Query handlers (read operations)
- Use case orchestration
- Transaction boundaries

### Domain Layer

- Aggregates and entities
- Value objects
- Domain events
- Business rules and invariants
- **Pure Python only** - no framework dependencies

### Infrastructure Layer

- Repository implementations
- Event store configuration
- External service adapters
- Projection runners
- Database connections

## Dependency Rules

| Layer | Can Depend On |
|-------|---------------|
| **Domain** | Nothing (pure Python, dataclasses, eventsourcing.domain only) |
| **Application** | Domain |
| **Infrastructure** | Domain, Application, external libraries |
| **API** | Application, Infrastructure (via dependency injection) |

## Why Pure Domain?

The domain layer is pure Python because:

- **Testability** - No mocking required for unit tests
- **Portability** - Domain logic is framework-agnostic
- **Clarity** - Business rules aren't obscured by infrastructure concerns
- **Longevity** - Frameworks change; business logic shouldn't

## Key Points

- Four layers: API, Application, Domain, Infrastructure
- Domain is pure Python with zero external dependencies
- Dependencies point inward toward domain
- Infrastructure implements ports defined by domain

## Prerequisites

- [Package Types](con-package-types.md) - How packages relate to layers

## Related

- [Package Structure](ref-package-structure.md) - Directory organization
- [Domain Modeling](con-domain-modeling.md) - Events, commands, queries
