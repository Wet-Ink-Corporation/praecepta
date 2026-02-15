<!-- Derived from {Project} PADR-111-classvar-aggregate-type-discrimination -->
# PADR-111: ClassVar Pattern for Aggregate Type Discrimination

**Status:** Proposed
**Date:** 2026-02-06
**Author:** docs-enricher agent
**Tags:** #pattern #domain #eventsourcing #aggregate

---

## Context

{Project} uses the `python-eventsourcing` library (v9.5+) for domain aggregates. The library's metaclass automatically generates a dataclass `__init__` for every aggregate class based on the aggregate's attributes. When creating aggregate subtypes (e.g., `WorkspaceBlock`, `SessionBlock` extending `Order`), we need a way for each subtype to declare its discriminator value (`block_type`) without:

1. **Creating a dataclass field** that would be included in the eventsourcing auto-generated `__init__`
2. **Passing it as a constructor parameter** (repetitive, error-prone)
3. **Hardcoding strings** in the base class `__init__` (loses type safety)

The naive approach fails:

```python
class Order(BaseAggregate):
    block_type: str = ""  # Treated as a dataclass field by eventsourcing metaclass

    @event("Created")
    def __init__(self, *, tenant_id: str) -> None:
        self.block_type = type(self).BLOCK_TYPE  # ERROR: field already exists
```

The eventsourcing metaclass sees `block_type: str = ""` and creates a constructor parameter `block_type: str`, breaking the design.

## Decision

**Use `ClassVar[str]` to declare the type discriminator on each subtype.** The base class reads `type(self).BLOCK_TYPE` in its `__init__` to set the instance attribute.

### Pattern Structure

```python
from typing import ClassVar
from eventsourcing.domain import event
from {Project}.shared.domain.aggregates import BaseAggregate

class Order(BaseAggregate):
    """Base aggregate for all resources."""

    BLOCK_TYPE: ClassVar[str] = ""  # ClassVar prevents dataclass field creation

    @event("Created")
    def __init__(self, *, tenant_id: str) -> None:
        self.block_type: str = type(self).BLOCK_TYPE  # Read from subtype's ClassVar
        self.tenant_id: str = tenant_id
        # ... other fields


class WorkspaceBlock(Order):
    """Workspace order."""

    BLOCK_TYPE: ClassVar[str] = EntityType.WORKSPACE.value

    @event("Created")
    def __init__(self, *, tenant_id: str) -> None:
        super().__init__(tenant_id=tenant_id)


class SessionBlock(Order):
    """Session order."""

    BLOCK_TYPE: ClassVar[str] = EntityType.SESSION.value

    @event("Created")
    def __init__(self, *, tenant_id: str, session_id: str, agent_instance_id: str) -> None:
        super().__init__(tenant_id=tenant_id)
        self.session_id: str = session_id
        self.agent_instance_id: str = agent_instance_id
```

### How It Works

1. **ClassVar annotation** signals to the dataclass machinery (and eventsourcing metaclass) that `BLOCK_TYPE` is a class-level constant, not an instance field
2. **Each subtype overrides** the ClassVar with its specific type value
3. **Base **init** reads** `type(self).BLOCK_TYPE` to get the concrete subtype's discriminator
4. **Instance attribute** `self.block_type` is set at runtime using the ClassVar value

### Why Each Subtype Needs @event("Created")

The eventsourcing metaclass auto-generates a dataclass `__init__` **per class**. If a subtype does not define its own `@event("Created")` constructor, the library generates one that:

- Accepts only fields defined on that class
- Does NOT call `super().__init__()`
- Overwrites the parent's `__init__` entirely

Therefore, **every subtype must define its own `@event("Created")` `__init__`** that calls `super().__init__()` to ensure the base aggregate initialization logic runs.

## Consequences

### Positive

- **Type-safe**: EntityType enum values are used, not magic strings
- **DRY**: Subtypes don't repeat `block_type=EntityType.X` in every constructor call
- **Eventsourcing-compatible**: No conflicts with metaclass field generation
- **Autocomplete-friendly**: IDEs suggest the ClassVar attribute
- **Refactoring-safe**: Renaming EntityType.WORKSPACE updates all subtypes automatically

### Negative

- **Non-obvious**: Developers unfamiliar with ClassVar may not understand why it's needed
- **Boilerplate**: Every subtype must define `BLOCK_TYPE: ClassVar[str] = ...` and `@event("Created") __init__`
- **Runtime coupling**: Base class depends on subtype's ClassVar existing (mitigated by base class default `BLOCK_TYPE: ClassVar[str] = ""`)

### Neutral

- **Alternative approaches rejected**:
  - **Pass block_type as parameter**: Repetitive, error-prone (caller must know the type)
  - **Factory pattern**: Loses subtype constructors, harder to test
  - **Metaclass intervention**: Too complex, fragile across eventsourcing updates

## Alternatives Considered

### Alternative 1: Pass block_type as Constructor Parameter

```python
class Order(BaseAggregate):
    @event("Created")
    def __init__(self, *, block_type: str, tenant_id: str) -> None:
        self.block_type = block_type
        self.tenant_id = tenant_id

# Usage
block = WorkspaceBlock(
    block_type=EntityType.WORKSPACE.value,  # Repetitive!
    tenant_id="acme-corp",
)
```

**Rejected:** Caller must pass the correct block_type for each subtype, which is error-prone and defeats the purpose of subtypes.

### Alternative 2: Factory Pattern

```python
class Order(BaseAggregate):
    @classmethod
    def create(cls, block_type: str, tenant_id: str, **kwargs):
        if block_type == "WORKSPACE":
            return WorkspaceBlock(tenant_id=tenant_id)
        elif block_type == "SESSION":
            return SessionBlock(tenant_id=tenant_id, **kwargs)
        # ...

# Usage
block = Order.create(block_type="WORKSPACE", tenant_id="acme-corp")
```

**Rejected:** Loses direct subtype constructors, harder to test individual subtypes, factory method becomes a maintenance burden.

### Alternative 3: Metaclass Intervention

Create a custom metaclass that sets `block_type` after eventsourcing's metaclass runs.

**Rejected:** Too complex, fragile across eventsourcing library updates, harder to debug.

## Implementation Guidance

### Step 1: Define ClassVar on Base Aggregate

```python
from typing import ClassVar

class MyAggregate(BaseAggregate):
    TYPE_DISCRIMINATOR: ClassVar[str] = ""

    @event("Created")
    def __init__(self, *, tenant_id: str) -> None:
        self.type_discriminator = type(self).TYPE_DISCRIMINATOR
```

### Step 2: Override ClassVar on Each Subtype

```python
class ConcreteAggregate(MyAggregate):
    TYPE_DISCRIMINATOR: ClassVar[str] = "CONCRETE_TYPE"

    @event("Created")
    def __init__(self, *, tenant_id: str) -> None:
        super().__init__(tenant_id=tenant_id)
```

### Step 3: Verify Base ClassVar Has a Default

If the base ClassVar has no default (`BLOCK_TYPE: ClassVar[str]`), instantiating the base class directly will fail. Always provide a default:

```python
BLOCK_TYPE: ClassVar[str] = ""  # Default for base (never instantiated directly)
```

### Step 4: Document the Pattern in Subtype Docstrings

```python
class WorkspaceBlock(Order):
    """Workspace order.

    BLOCK_TYPE is set via ClassVar to avoid dataclass field creation
    by the eventsourcing metaclass. See PADR-111 for rationale.
    """
    BLOCK_TYPE: ClassVar[str] = EntityType.WORKSPACE.value
```

## Testing

```python
class TestClassVarPattern:
    def test_subtype_sets_correct_block_type(self) -> None:
        block = WorkspaceBlock(tenant_id="test-tenant")
        assert block.block_type == "WORKSPACE"

    def test_different_subtypes_have_different_types(self) -> None:
        ws = WorkspaceBlock(tenant_id="test")
        sess = SessionBlock(
            tenant_id="test",
            session_id="s1",
            agent_instance_id="a1"
        )
        assert ws.block_type == "WORKSPACE"
        assert sess.block_type == "SESSION"

    def test_classvar_not_in_instance_dict(self) -> None:
        block = WorkspaceBlock(tenant_id="test")
        # ClassVar is not an instance attribute
        assert "BLOCK_TYPE" not in block.__dict__

    def test_classvar_accessible_via_class(self) -> None:
        assert WorkspaceBlock.BLOCK_TYPE == "WORKSPACE"
```

## Impact

- **Scope:** All aggregate hierarchies with type discrimination
- **Affected contexts:** Memory (Order), future contexts with similar patterns
- **Migration required:** No (pattern established in initial implementation)
- **Breaking changes:** None

## Related Decisions

- [PADR-109: Sync-First Event Sourcing](PADR-109-sync-first-eventsourcing.md) — Eventsourcing library integration
- [PADR-101: Vertical Slices](PADR-101-vertical-slices.md) — Aggregate design within slices
- [ADR-015: Entry-Level Abstractions](../strategic/ADR-015-entry-level-abstractions.md) — Domain model structure

## References

- **Implementation:** `src/{Project}/ordering/domain/aggregates.py` lines 80, 221, 242, etc.
- **Tests:** `tests/unit/ordering/domain/test_aggregates.py`
- **Feature:** F-100-001 (Domain Model Implementation)
- **Python typing.ClassVar:** <https://docs.python.org/3/library/typing.html#typing.ClassVar>
- **Eventsourcing library:** <https://eventsourcing.readthedocs.io/>

---

**Next Actions:**

- [ ] Review and finalize status (Proposed → Accepted)
- [ ] Communicate pattern to all engineers
- [ ] Update aggregate design template
