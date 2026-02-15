# Event Store & CQRS Domain

Event sourcing infrastructure, projections, and command/query separation.

## Mental Model

All state changes are immutable events (PADR-001). Commands produce events; projections consume events to build read models. The event store (PostgreSQL) is the single source of truth. Read models (projections) are disposable and rebuildable.

Sync-first approach (PADR-109): command handlers are synchronous (FastAPI offloads to threadpool), query handlers are async, projections use sync repositories.

## Invariants

- Events are immutable and append-only
- Projections are rebuildable from events
- Event schema evolution via upcasting (not migration)
- Aggregate version enforces optimistic concurrency

## Key Patterns

- **Aggregate:** EventSourced base class with `trigger_event()` / `apply()`
- **Transcoder:** Custom JSON transcoder for event serialization
- **Module registry:** Event types registered per module (PADR-112)
- **Type discrimination:** ClassVar for aggregate type identification (PADR-111)
- **Lifecycle:** State machine for aggregate states (PADR-114)
- **Application:** Singleton via FastAPI Depends (PADR-110)

## Integration Points

- **→ All contexts:** Provides event sourcing infrastructure
- **→ Graph:** Events consumed by projection runners

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/strategic/PADR-001-event-sourcing.md` | Event sourcing rationale |
| `_kb/decisions/patterns/PADR-109-sync-first-eventsourcing.md` | Sync/async strategy |
| `_kb/decisions/patterns/PADR-110-application-lifecycle.md` | Singleton pattern |
| `_kb/decisions/patterns/PADR-111-classvar-aggregate-type-discrimination.md` | Type registry |
| `_kb/decisions/patterns/PADR-112-module-level-registry.md` | Event registration |
| `_kb/decisions/patterns/PADR-114-aggregate-lifecycle-state-machine.md` | State machines |
| `references/con-persistence-strategy.md` | Persistence overview |
| `references/ref-infra-eventsourcing-transcoder.md` | Transcoder details |
| `references/proc-event-flow.md` | Event propagation flow |
| `references/con-domain-modeling.md` | Domain modeling patterns |
