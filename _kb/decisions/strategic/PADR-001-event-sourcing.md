<!-- Derived from {Project} PADR-001-event-sourcing -->
# PADR-001: Event Sourcing for State Management

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Strategic, Data Architecture

---

## Context

{Project} is an enterprise memory infrastructure for AI agents that requires:

- Complete audit trails for compliance
- Bitemporal queries (what was known at time T about time T')
- Ability to rebuild projections for different query patterns
- Temporal consistency across distributed read models

Traditional CRUD-based state management overwrites history, making these requirements difficult or impossible to fulfill.

## Decision

**We will use Event Sourcing as the primary state management pattern**, with the Python `eventsourcing` library (v9.5+) and PostgreSQL as the event store.

### Core Pattern

```python
from eventsourcing.domain import Aggregate, event

# Note: This example reflects the original membership-based model.
# The current architecture uses entry-based ownership (see ADR-015).
# The event sourcing pattern itself remains unchanged.
class Order(Aggregate):
    @event('Created')
    def __init__(self, title: str, owner_id: str, tenant_id: str):
        self.title = title
        self.owner_id = owner_id
        self.tenant_id = tenant_id
        self.memberships = []
        self.archived = False

    @event('MembershipAdded')
    def add_membership(self, content_id: UUID) -> None:
        if content_id not in self.memberships:
            self.memberships.append(content_id)

    @event('Archived')
    def archive(self) -> None:
        self.archived = True
```

### Event Store Schema

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    stream_id UUID NOT NULL,
    stream_type VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    global_position BIGSERIAL,
    event_type VARCHAR(255) NOT NULL,
    event_data BYTEA NOT NULL,
    metadata BYTEA,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stream_id, version)
);
```

## Rationale

### Why Event Sourcing?

| Requirement | How ES Addresses It |
|-------------|---------------------|
| **Audit Trail** | Events are immutable facts—complete history preserved |
| **Bitemporal Queries** | Event timestamp = Processing time; valid time in event payload |
| **Projection Rebuilds** | Replay events to create new read models |
| **Temporal Consistency** | Optimistic concurrency via version numbers |

### Why Python eventsourcing Library?

- Mature, well-documented (v9.5+)
- Native PostgreSQL support
- Built-in snapshotting for long-lived aggregates
- Notification log for async projections
- Transcoding support for event versioning

### Why Not Alternatives?

| Alternative | Rejection Reason |
|-------------|------------------|
| **Traditional CRUD** | No history, no audit trail, no temporal queries |
| **Soft deletes + timestamps** | Partial solution; complex queries, no replay |
| **Change Data Capture (CDC)** | Infrastructure overhead; doesn't model domain events |
| **EventStoreDB** | Additional infrastructure; Python support less mature |

## Consequences

### Positive

1. **Complete Audit Trail:** Every state change recorded as immutable event
2. **Bitemporal Alignment:** Events naturally support Processing time; valid time in payload
3. **Projection Flexibility:** Can create specialized read models (vector, graph, summary)
4. **Testing Clarity:** Test behavior via expected events
5. **Debugging:** Replay events to reproduce issues

### Negative

1. **Learning Curve:** Team must understand ES patterns
2. **Event Schema Evolution:** Versioning/upcasting required for breaking changes
3. **Eventual Consistency:** Projections lag behind event store
4. **Storage Growth:** Events accumulate (mitigated by snapshots)

### Mitigations

| Risk | Mitigation |
|------|------------|
| Learning curve | Training, pair programming, code reviews |
| Schema evolution | Upcasting patterns, avoid breaking changes |
| Eventual consistency | Document consistency model, sync projections for critical paths |
| Storage growth | Snapshots every 50 events, archival strategy |

## Implementation Notes

### Aggregate Design

- Keep aggregates small (single responsibility)
- Aggregate = consistency boundary
- Cross-aggregate operations via domain events

### Snapshots

```python
class CoreApplication(Application):
    snapshotting_intervals = {Order: 50}  # Snapshot every 50 events
```

### Event Versioning

```python
class EventUpcaster:
    def upcast(self, event_type: str, data: dict) -> dict:
        if event_type == 'EntityCreatedV1':
            return {**data, 'tenant_id': self._lookup_tenant(data['owner_id'])}
        return data
```

### Projections

```python
class BlockSummaryProjection:
    async def handle(self, event: DomainEvent) -> None:
        match event:
            case OrderPlaced():
                await self._insert_summary(event)
            case MembershipAdded():
                await self._increment_count(event)
```

## Related Decisions

- PADR-002: Modular Monolith Architecture
- [ADR-009: Three-Category Taxonomy](./ADR-009-three-category-taxonomy.md) (supersedes ADR-003)
- PADR-004: Security Trimming Model
- [ADR-013: Session Memory Contains No Cached Context](./ADR-013-session-no-cached-context.md) -- Session Memory is event-sourced; events represent session activity
- [ADR-015: Entry-Level Abstractions](./ADR-015-entry-level-abstractions.md) (entry-based ownership model)
- [ADR-115: Reinforcement Metrics as Projections](../patterns/ADR-115-reinforcement-metrics-projection.md) -- Reinforcement metrics derived from event stream (COUNT/MAX over reinforcement events)

## References

- [Python eventsourcing Library](https://eventsourcing.readthedocs.io/)
- [Greg Young - CQRS and Event Sourcing](http://codebetter.com/gregyoung/2010/02/13/cqrs-and-event-sourcing/)
- [Martin Fowler - Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- Research: `event-sourcing-patterns.md`

## Changelog

### 2026-02-05: Terminology Alignment (F-100-004)

- Updated Order example to note legacy membership-based model; added forward-reference to ADR-015 (entry-based ownership)
- Updated Related Decisions: ADR-003 reference replaced with ADR-009 (three-category taxonomy) and ADR-015 (entry-level abstractions)
- Added cross-references to ADR-013 (session is event-sourced) and ADR-115 (reinforcement metrics derived from event stream)
- Core decision unchanged; status remains Draft
