# Package Structure Reference

## Overview

Hybrid model combining bounded contexts with feature slices.

## Directory Layout

```
src/
├── shared/                          # Cross-cutting concerns
│   ├── domain/
│   │   ├── value_objects.py         # Email, Money, etc.
│   │   └── exceptions.py            # Base domain exceptions
│   ├── infrastructure/
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   └── eventsourcing.py     # EventSourcingSettings (Pydantic)
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── postgres_parser.py   # DATABASE_URL parser
│   │   │   └── event_store.py       # EventStoreFactory
│   │   ├── neo4j_view.py            # Base Neo4j TrackingRecorder
│   │   └── observability.py         # OpenTelemetry setup
│   └── api/
│       ├── dependencies.py          # FastAPI DI providers
│       └── error_handlers.py        # Global exception handlers
│
├── dog_school/                      # Bounded Context
│   ├── __init__.py
│   ├── application.py               # DogSchoolApplication class
│   ├── _shared/                     # Context-internal shared code
│   │   ├── events.py                # DogRegistered, TrickAdded, etc.
│   │   ├── common.py                # Command/Query bases, app access
│   │   └── exceptions.py            # Context-specific exceptions
│   │
│   ├── slices/                      # Feature Slices
│   │   ├── register_dog/
│   │   │   ├── __init__.py
│   │   │   ├── cmd.py               # RegisterDog command
│   │   │   └── test_cmd.py
│   │   │
│   │   ├── add_trick/
│   │   │   ├── __init__.py
│   │   │   ├── cmd.py               # AddTrick command
│   │   │   └── test_cmd.py
│   │   │
│   │   ├── get_dog/
│   │   │   ├── __init__.py
│   │   │   ├── query.py             # GetDog query
│   │   │   └── test_query.py
│   │   │
│   │   └── list_dogs/
│   │       ├── __init__.py
│   │       ├── query.py             # ListDogs with projection
│   │       └── test_query.py
│   │
│   ├── projections/                 # Materialised view projections
│   │   └── graph_projection.py      # Neo4j graph projection
│   │
│   └── infrastructure/
│       ├── api.py                   # FastAPI router
│       ├── graph_view.py            # Neo4j view implementation
│       └── run_graph_projection.py  # Projection runner entrypoint
│
├── counters/                        # Another Bounded Context
│   ├── application.py
│   ├── _shared/
│   │   └── ...
│   └── ...
│
├── main.py                          # FastAPI application factory
└── system.py                        # eventsourcing System definition
```

## Import Rules (import-linter)

```ini
[importlinter]
root_packages =
    dog_school
    counters
    shared

[importlinter:contract:1]
name = Domain has no external dependencies
type = forbidden
source_modules =
    dog_school._shared.events
    counters._shared.events
forbidden_modules =
    fastapi
    sqlalchemy
    redis
    neo4j
    taskiq

[importlinter:contract:2]
name = Feature slices are independent
type = independence
modules =
    dog_school.slices.register_dog
    dog_school.slices.add_trick
    dog_school.slices.get_dog
    dog_school.slices.list_dogs

[importlinter:contract:3]
name = Bounded contexts cannot import each other internals
type = forbidden
source_modules = dog_school
forbidden_modules = counters._shared
```

## Naming Conventions

| Location | Pattern | Example |
|----------|---------|---------|
| Commands | `slices/<action>/cmd.py` | `slices/register_dog/cmd.py` |
| Queries | `slices/<action>/query.py` | `slices/get_dog/query.py` |
| Events | `_shared/events.py` | `DogRegistered`, `TrickAdded` |
| Exceptions | `_shared/exceptions.py` | `DogAlreadyRegisteredError` |
| Projections | `projections/<name>_projection.py` | `graph_projection.py` |

## See Also

- [Architecture Layers](con-layers.md) - Layer responsibilities
- [Domain Modeling](con-domain-modeling.md) - Event and command patterns
