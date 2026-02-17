# Architecture Decisions

Praecepta's architecture is documented through **Praecepta Architecture Decision Records (PADRs)**. This page highlights the decisions most relevant to consumers of the framework.

## Strategic Decisions

### PADR-001: Event Sourcing

**Status:** Accepted

Praecepta uses event sourcing as its primary persistence pattern. Instead of storing current state, the system stores immutable events. Current state is derived by replaying events from the event store.

**Key consequences:**

- Complete audit trail for all state changes
- Temporal queries — reconstruct state at any point in time
- Events are the integration backbone between bounded contexts
- Projections provide read-optimized views

### PADR-002: Modular Monolith

**Status:** Accepted

Praecepta is organized as a modular monolith with bounded contexts. Each context is a separate package that can be developed, tested, and deployed independently while sharing a single process.

**Key consequences:**

- Clear boundaries between domains, enforced by `import-linter`
- Packages are composable — install only what you need
- Cross-context communication via explicit facades and integration packages
- Future extraction to microservices is possible per-context

## Pattern Decisions

### PADR-101: Vertical Slices

**Status:** Accepted

Feature code is organized by use case (vertical slices) rather than by technical layer. Each slice contains its command/query handler, endpoint, and tests.

```
slices/
├── place_order/
│   ├── cmd.py         # Command handler
│   ├── endpoint.py    # FastAPI route
│   └── test_cmd.py    # Tests
└── get_order/
    ├── query.py       # Query handler
    ├── endpoint.py
    └── test_query.py
```

### PADR-102: Hexagonal Architecture (Ports & Adapters)

**Status:** Accepted

Domain logic defines ports (Python protocols). Infrastructure implements adapters. This keeps the domain layer pure and swappable.

```python
# Port (in foundation-domain)
class LLMServicePort(Protocol):
    def generate(self, prompt: str) -> str: ...

# Adapter (in infrastructure)
class OpenAILLMService:
    def generate(self, prompt: str) -> str:
        return openai.chat(prompt)
```

### PADR-109: Sync-First Event Sourcing

**Status:** Accepted

Commands use synchronous execution (`def`), queries use async (`async def`), and projections process events synchronously. This avoids complexity from async event store operations while allowing async I/O for reads.

| Operation | Style | Rationale |
|-----------|-------|-----------|
| Commands | `def` | Event store writes are sync |
| Queries | `async def` | DB reads benefit from async |
| Projections | `def` | Sequential event processing |

### PADR-113: Two-Tier Validation

**Status:** Accepted

Validation is split into two tiers:

1. **Structural** — Pydantic validates data shapes at the API boundary
2. **Semantic** — Domain logic validates business rules inside aggregates

This separates "is the data well-formed?" from "does this operation make business sense?"

### PADR-122: Entry-Point Auto-Discovery

**Status:** Accepted

Packages declare their contributions (routers, middleware, projections, etc.) via Python entry points in `pyproject.toml`. The `create_app()` factory discovers and wires everything automatically.

**Key consequence:** Installing a package is sufficient to activate it. No manual wiring required.

See [Entry-Point Discovery](architecture/entry-points.md) for the full reference.

---

## Full Decision Index

The complete set of 25 PADRs (4 strategic + 21 pattern) is maintained in the project's internal knowledge base. The decisions above are the subset most relevant to framework consumers.
