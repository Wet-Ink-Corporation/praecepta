<!-- Derived from {Project} PADR-108-domain-service-protocols -->
# PADR-108: Domain Service Protocol Pattern

**Status**: Accepted  
**Date**: 2026-01-31  
**Context**: Memory  
**Deciders**: Architecture Team  
**Related**: [PADR-102 Hexagonal Ports](./PADR-102-hexagonal-ports.md)

## Context and Problem Statement

Domain services that traverse aggregate relationships (e.g., tree hierarchy traversal for tag inheritance, ACL narrowing validation) need to query aggregate state without coupling to infrastructure (repositories, databases, event stores).

**Problem**: How do we keep domain services pure and testable while enabling them to query aggregate relationships?

## Decision Drivers

- **Testability**: Domain services must be unit-testable without database setup
- **Dependency Inversion**: Domain layer cannot depend on infrastructure
- **Performance**: Minimize query round-trips during graph traversal
- **Reusability**: Services work with event-sourced aggregates, projections, or in-memory data

## Considered Options

1. **Direct Repository Dependency**: Services depend on concrete repository implementations
2. **Protocol-Based Readers**: Services depend on protocol interfaces, adapters implement protocols
3. **Event-Based Queries**: Services emit query events, infrastructure responds

## Decision Outcome

**Chosen**: Protocol-Based Readers (Option 2)

Domain services accept protocol interfaces via constructor injection. Protocols define minimal query contracts. Infrastructure provides adapters implementing protocols.

### Pattern Structure

```python
# 1. Define protocol in domain/services.py
class BlockParentReader(Protocol):
    def get_parent_ids(self, block_id: UUID) -> tuple[UUID, ...] | None:
        ...

# 2. Implement domain service using protocol
class CycleDetectionService:
    def __init__(self, parent_reader: BlockParentReader) -> None:
        self._parent_reader = parent_reader
    
    def would_create_cycle(self, block_id: UUID, new_parent_id: UUID) -> bool:
        # Use self._parent_reader for queries
        ...

# 3. Create repository adapter in handler.py
class RepositoryBlockParentReader:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository
    
    def get_parent_ids(self, block_id: UUID) -> tuple[UUID, ...] | None:
        block = self._repository.get(block_id)
        return block.parent_block_ids if block else None

# 4. Inject adapter at handler level
class CreateBlockHandler:
    def handle(self, cmd: CreateBlockCommand) -> UUID:
        reader = RepositoryBlockParentReader(self._app.repository)
        service = CycleDetectionService(reader)
        # Use service...
```

## Examples

### Implemented in domain context

| Service | Protocol | Adapter | Purpose |
|---------|----------|---------|---------|
| `CycleDetectionService` | `BlockParentReader` | `RepositoryBlockParentReader` | Validate tree hierarchy (no cycles) |
| `TagInheritanceService` | `BlockTagReader` | `RepositoryBlockTagReader` | Compute tag union from ancestors |
| `ACLInheritanceService` | `BlockACLReader` | `RepositoryBlockACLReader` | Compute ACL intersection (security) |

### Performance Optimization

Protocols can combine multiple queries to reduce round-trips:

```python
# Instead of separate queries:
class BlockParentReader(Protocol):
    def get_parent_ids(self, block_id: UUID) -> tuple[UUID, ...] | None: ...

class BlockTagReader(Protocol):
    def get_tags(self, block_id: UUID) -> tuple[str, ...] | None: ...

# Combine into single query:
class BlockTagReader(Protocol):
    def get_block_tags_and_parents(
        self, block_id: UUID
    ) -> tuple[tuple[str, ...], tuple[UUID, ...]] | None:
        """Return (tags, parent_ids) in single query."""
        ...
```

## Consequences

### Positive

- **Fast Unit Tests**: In-memory protocol implementations enable sub-second test suites
- **Clear Boundaries**: Domain layer has zero infrastructure dependencies
- **Flexible Infrastructure**: Same service works with event store, projections, or cache
- **Type Safety**: Protocols enforce contracts at compile time (mypy)

### Negative

- **Boilerplate**: Each service requires protocol + repository adapter + in-memory test implementation
- **Indirection**: Extra layer between service and data source
- **Learning Curve**: Developers must understand protocol pattern

### Neutral

- **Testing Strategy**: Unit tests use in-memory implementations, integration tests use real repository
- **Performance**: Protocol overhead negligible compared to I/O cost

## Validation

**Success Metrics**:

- Domain service unit tests run in <100ms (no database)
- Zero infrastructure imports in domain/services.py
- Services reusable across event store, projections, cache

**Actual Results** (F-001-009):

- CycleDetectionService: 24 tests, 96% coverage, 0.08s
- TagInheritanceService: 27 tests, 100% coverage, 0.06s
- ACLInheritanceService: 38 tests, 100% coverage, 0.09s

## References

- [Hexagonal Architecture (PADR-102)](./PADR-102-hexagonal-ports.md)
- [Testing Strategy (PADR-104)](./PADR-104-testing-strategy.md)
- Implementation: `src/{Project}/ordering/domain/services.py`
- Tests: `tests/unit/ordering/domain/test_*_service.py`

## Changelog

### 2026-02-05: Terminology Alignment (F-100-004)

- Updated context description: "DAG traversal for cycle detection" changed to "tree hierarchy traversal for tag inheritance, ACL narrowing validation"
- Updated CycleDetectionService purpose: "Validate DAG acyclicity" changed to "Validate tree hierarchy (no cycles)"
- Aligned with D1 (DAG to strict tree for workspace hierarchy)
- Core protocol pattern unchanged; status remains Accepted

---

_This ADR documents the protocol-based reader pattern established in F-001-009 (Memory Taxonomy & DAG Hierarchy)._
