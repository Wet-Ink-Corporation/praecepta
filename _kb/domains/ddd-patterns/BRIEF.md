# DDD Patterns Domain

Domain-Driven Design patterns used across all bounded contexts.

## Mental Model

Modular monolith (PADR-002) with bounded contexts. Each context follows hexagonal architecture (PADR-102) with vertical slices (PADR-101). Domain layer is pure — no framework dependencies, enforced by lint-imports.

## Key Patterns

- **Vertical slices:** `slices/<action>/cmd.py` + `query.py` + `endpoint.py` (PADR-101)
- **Commands:** Pure handlers `handle(events) -> new_events` (sync, PADR-109)
- **Queries:** Read from projections (`async def`, PADR-109)
- **Aggregates:** EventSourced base, `trigger_event()` / `apply()` pattern
- **Events:** Immutable, past-tense naming (`OrderPlaced`), in `_shared/events.py`
- **Value objects:** Immutable, equality by value, self-validating
- **Facades:** Cross-context communication via explicit interfaces
- **Two-tier validation:** Structural (Pydantic) then semantic (domain rules) (PADR-113)
- **Ports/adapters:** Domain defines protocols, infrastructure implements (PADR-102)

## Layer Structure

```
context/
├── domain/           # Pure domain logic (NO external deps)
├── application/      # Use cases, facades
├── infrastructure/   # Adapters (DB, external)
├── api/              # FastAPI routes
└── slices/           # Vertical feature slices
```

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/strategic/PADR-002-modular-monolith.md` | Architecture rationale |
| `_kb/decisions/patterns/PADR-101-vertical-slices.md` | Slice organization |
| `_kb/decisions/patterns/PADR-102-hexagonal-ports.md` | Port/adapter patterns |
| `_kb/decisions/patterns/PADR-108-domain-service-protocols.md` | Service interfaces |
| `_kb/decisions/patterns/PADR-113-two-tier-validation.md` | Validation approach |
| `references/con-layers.md` | Layer responsibilities |
| `references/con-domain-modeling.md` | Domain modeling guide |
| `references/ref-package-structure.md` | Package layout rules |
| `references/con-domain-model.md` | Domain model overview |
| `references/ref-workspace-pep420-conventions.md` | Package structure, PEP 420 namespace conventions |
