<!-- Derived from {Project} PADR-002-modular-monolith -->
# PADR-002: Modular Monolith Architecture

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Strategic, System Architecture

---

## Context

{Project} is a new product requiring:

- Rapid iteration during early development
- Clear domain boundaries for maintainability
- Future optionality for service extraction
- Manageable operational complexity for a small team

We must choose an architectural approach that balances these needs.

## Decision

**We will build {Project} as a Modular Monolith**, organizing code into well-defined bounded contexts that communicate through explicit interfaces, deployed as a single application.

### Package Structure

```
src/{project}/
├── memory/                 # Bounded Context: Memory
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── api/
│   └── slices/
│
├── Processing/              # Bounded Context: Processing
│   ├── domain/
│   ├── application/
│   └── ...
│
├── query/                  # Bounded Context: Query
├── security/               # Bounded Context: Security
├── graph/                  # Bounded Context: Graph
├── Lifecycle/               # Bounded Context: Lifecycle
│
└── shared/                 # Shared Kernel
    ├── domain/             # Common value objects
    └── infrastructure/     # Common adapters
```

### Boundary Enforcement

Using `import-linter` to enforce module boundaries:

```ini
[importlinter]
root_package = {Project}

[importlinter:contract:memory-isolation]
name = domain context isolation
type = independence
modules =
    {Project}.memory
    {Project}.Processing
    {Project}.query
    {Project}.graph

[importlinter:contract:domain-purity]
name = Domain has no infrastructure dependencies
type = layers
layers =
    {Project}.ordering.api
    {Project}.ordering.application
    {Project}.ordering.domain
    {Project}.ordering.infrastructure
```

## Rationale

### Why Modular Monolith over Microservices?

| Factor | Modular Monolith | Microservices |
|--------|------------------|---------------|
| **Team Size** | Small team (1-5) | Multiple teams |
| **Domain Clarity** | Still discovering boundaries | Well-understood domains |
| **Operational Overhead** | Single deployment | Multiple services, networking |
| **Data Consistency** | Easier transactions | Distributed transactions |
| **Refactoring** | Local changes | Cross-service coordination |
| **Development Speed** | Faster iteration | Slower due to contracts |

**Our situation:** Small team, evolving domain, need for speed → Modular Monolith.

### Why Not Microservices from the Start?

Shopify's experience (referenced in research):
> "We moved from a distributed system back to a modular monolith because the coordination overhead was killing our velocity."

Premature distribution introduces:

- Network latency on every internal call
- Distributed transaction complexity
- Service discovery and deployment orchestration
- Cross-service debugging difficulty

### Future Service Extraction

Modular monolith preserves optionality:

1. Bounded contexts have explicit interfaces (facades, events)
2. No direct imports across contexts
3. Can extract a context to a service by replacing in-process calls with network calls

## Consequences

### Positive

1. **Simpler Deployment:** Single artifact to deploy and monitor
2. **Local Development:** Full system runs in one process
3. **Refactoring Freedom:** Can move code between contexts easily
4. **Transaction Simplicity:** Database transactions span contexts when needed
5. **Debugging Clarity:** Full stack traces, no network hops

### Negative

1. **Coupling Risk:** Without discipline, boundaries erode
2. **Scaling Constraints:** Must scale entire application together
3. **Technology Lock-in:** All contexts use same language/framework
4. **Large Codebase:** Single repo can become unwieldy

### Mitigations

| Risk | Mitigation |
|------|------------|
| Boundary erosion | `import-linter` in CI, code reviews |
| Scaling constraints | Horizontal scaling, read replicas, async processing |
| Technology lock-in | Python is suitable for all {Project} domains |
| Large codebase | Clear package structure, bounded context organization |

## Bounded Context Interactions

### Within the Monolith

```python
# Context Facade Pattern
class ProcessingFacade:
    """Public interface for Processing context."""

    async def ingest_document(self, source_id: UUID, content: bytes) -> UUID:
        """Ingest a document and return the document ID."""
        ...

    async def get_chunks(self, document_id: UUID) -> list[ChunkDTO]:
        """Get chunks for a document."""
        ...
```

### Event-Based Integration

```python
# domain context subscribes to Processing events
@event_handler(DocumentIngested)
async def on_document_ingested(event: DocumentIngested):
    await memory_service.process_new_document(event.document_id)
```

### Shared Kernel

Minimal shared code across all contexts:

- ACL primitives (`Principal`, `acl_principals`)
- Common value objects (`TenantId`, `UserId`)
- Shared infrastructure (database connection, logging)

## Implementation Notes

### Package Organization Rules

1. **Context Independence:** No imports between context `domain/` packages
2. **Facade Access Only:** Cross-context communication via facades or events
3. **Shared Kernel Minimal:** Only truly universal concepts
4. **Vertical Slices Within:** Feature-centric organization inside contexts

### CI Enforcement

```yaml
# GitHub Actions
- name: Check import boundaries
  run: |
    pip install import-linter
    lint-imports
```

## Related Decisions

- PADR-001: Event Sourcing for State Management
- ADR-101: Vertical Slice Architecture

## References

- [Shopify - Deconstructing the Monolith](https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity)
- [DHH - The Majestic Monolith](https://signalvnoise.com/svn3/the-majestic-monolith/)
- [Milan Jovanovic - Modular Monolith Architecture](https://www.milanjovanovic.tech/blog/what-is-a-modular-monolith)
- Research: `modular-monolith-patterns.md`
