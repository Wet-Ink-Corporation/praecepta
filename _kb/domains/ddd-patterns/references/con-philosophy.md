# Philosophy and Principles

## Overview

This architecture combines event sourcing with a modular monolith structure. Event sourcing treats state as a sequence of immutable facts; the modular monolith provides bounded contexts without network overhead.

## Why Event Sourcing?

Event sourcing provides:

| Benefit | Description |
|---------|-------------|
| **Complete audit trail** | Every change is recorded; nothing is lost |
| **Temporal queries** | Reconstruct state at any point in time |
| **Debugging superpowers** | Replay events to reproduce bugs exactly |
| **Decoupled read models** | Project events into optimized query stores |
| **Natural CQRS fit** | Commands produce events; queries read projections |

## Why a Modular Monolith?

We reject the false dichotomy of "monolith vs. microservices." A modular monolith provides:

| Benefit | Description |
|---------|-------------|
| **Bounded contexts** | Logical separation without network overhead |
| **Single deployment** | One artifact, one process, simpler operations |
| **Refactoring safety** | Move boundaries without distributed system complexity |
| **Extraction path** | Modules can become services when genuinely needed |

## The "Changes Together" Principle

Code that changes for the same reason should live in the same place. This manifesto embraces vertical slices _within_ bounded contexts, not as a replacement for domain modeling.

## Trade-offs We Accept

This architecture accepts these trade-offs consciously:

| Trade-off | Impact |
|-----------|--------|
| **Eventual consistency** | Read models may lag behind event store |
| **Increased complexity** | Event sourcing requires more infrastructure than CRUD |
| **Learning curve** | Team must understand DDD, CQRS, and event-driven patterns |
| **Operational overhead** | Event store, projections, and message infrastructure need monitoring |

## Key Points

- Event sourcing = state as immutable facts, not mutable snapshots
- Modular monolith = bounded contexts without microservice overhead
- Vertical slices within bounded contexts, not across them
- Accept eventual consistency in exchange for audit trails and temporal queries

## Prerequisites

None - this is the foundational document.

## Related

- [Technology Stack](ref-tech-stack.md) - What implements these principles
- [Architecture Layers](con-layers.md) - How layers are structured
- [Package Types](con-package-types.md) - Dependency rules
