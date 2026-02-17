<!-- Derived from {Project} PADR-112-module-level-registry -->
# PADR-112: Module-Level Registry Pattern

**Status:** Proposed
**Date:** 2026-02-06
**Deciders:** Architecture Team
**Categories:** Pattern, Domain Design
**Proposed by:** docs-enricher (feature F-100-002)

---

## Context

Domain registries provide lookup services for static data like namespace mappings, controlled vocabularies, validation rules, and type discrimination tables. Traditional approaches use class-based singletons:

```python
class TagRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_data()
        return cls._instance

    def get_category(self, namespace: str) -> TagCategory | None:
        return self._mapping.get(namespace)
```

This creates unnecessary complexity:

- Instance state for immutable static data
- Singleton pattern anti-pattern (global mutable state)
- Extra boilerplate (10+ lines for initialization)
- `self` parameter everywhere for stateless operations
- Test complexity (need to reset singleton state)

Feature F-100-002 (Tag System) introduced a tag namespace registry that needed:

- Static namespace-to-category mappings
- Controlled vocabulary lookups (agent-memory values, sensitivity levels)
- Pure validation functions with zero external dependencies
- Domain layer purity (no framework dependencies)

The question was: **Should we use a class-based singleton or a simpler alternative?**

---

## Decision

**We will use module-level constants and pure functions for domain registries** instead of class-based singletons.

**Pattern structure:**

1. **Data as module-level constants** (`dict`, `frozenset`, `tuple`)
2. **Logic as pure functions** (no `self`, no instance state)
3. **Module acts as namespace** (Python guarantees single initialization)
4. **TYPE_CHECKING imports** for type hints (avoid circular imports)

**Implementation example:**

```python
"""Tag namespace registry."""

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from {Project}.ordering.domain.value_objects import Tag

class TagCategory(StrEnum):
    ORGANIZATIONAL = "organizational"
    CLASSIFICATION = "classification"
    # ...

# Module-level constants
NAMESPACE_TO_CATEGORY: dict[str, TagCategory] = {
    "org": TagCategory.ORGANIZATIONAL,
    "topic": TagCategory.CLASSIFICATION,
    # ...
}

AGENT_MEMORY_VALUES: frozenset[str] = frozenset([
    "preference", "commitment", "pattern", "fact", "boundary"
])

# Pure functions
def get_category(namespace: str) -> TagCategory | None:
    """Look up category for namespace."""
    return NAMESPACE_TO_CATEGORY.get(namespace)

def get_allowed_values(namespace: str) -> frozenset[str] | None:
    """Get controlled vocabulary for namespace."""
    return _CONTROLLED_VOCABULARIES.get((namespace,))
```

**Usage:**

```python
from {Project}.ordering.domain import tag_registry

category = tag_registry.get_category("org")
allowed = tag_registry.get_allowed_values("agent-memory")
result = tag_registry.validate_tag(tag)
```

---

## Consequences

### Positive

- **Simplicity**: 2 lines (constant + function) vs 10+ lines (singleton class)
- **Pure Functions**: All operations are stateless with no side effects
- **Zero Overhead**: Direct function calls, no `self` indirection
- **Module Singleton**: Python guarantees module imports once
- **Type Safety**: Full static type checking with mypy
- **Testability**: Pure functions with no setup/teardown needed
- **Domain Purity**: No framework dependencies, stdlib only
- **Pythonic**: Modules are natural namespaces in Python

### Negative

- **No Inheritance**: Cannot extend via subclassing (but this is rarely needed for registries)
- **No Runtime Swapping**: Cannot replace implementation at runtime (use dependency injection if needed)
- **No Lazy Loading**: All data must be compile-time constants (but registries are typically static)
- **Module Mocking**: Harder to mock entire module (but individual functions can be mocked)

### Neutral

- Established convention for stateless registries across the codebase
- Aligns with functional programming principles (pure functions over objects)
- Clear signal: "This is static data, not runtime state"

---

## Implementation Notes

- **Feature:** F-100-002 Tag System
- **Story:** S-100-002-002 (namespace categories registry)
- **Key Files:**
  - `src/{Project}/ordering/domain/tag_registry.py` (reference implementation)
- **Pattern Doc:** [ref-domain-module-level-registry.md](../../domains/event-store-cqrs/references/ref-domain-module-level-registry.md)

**Convention applies to:**

- Domain registries (static lookup data)
- Controlled vocabularies
- Validation functions (pure logic)
- Type discrimination tables

**Convention does NOT apply to:**

- Services requiring database access (use repository pattern)
- Services requiring runtime configuration (use dependency injection)
- Services with memoization/caching (use class with `@lru_cache`)

---

## Alternatives Considered

### Alternative 1: Class-Based Singleton

**Structure:**

```python
class TagRegistry:
    _instance = None
    def __new__(cls): ...
    def get_category(self, namespace: str): ...
```

**Rejected because:**

- Unnecessary boilerplate (10+ lines for singleton pattern)
- Instance state for static data (violates pure domain principle)
- `self` parameter everywhere (no state, so why `self`?)
- Test complexity (need to reset singleton between tests)

### Alternative 2: Dependency Injection

**Structure:**

```python
class TagRegistry:
    def __init__(self, config: dict): ...
    def get_category(self, namespace: str): ...

# Inject registry into consumers
def create_block(registry: TagRegistry, ...): ...
```

**Rejected because:**

- Over-engineering for static data
- Increases API surface (registry must be passed everywhere)
- No runtime variation needed (data is truly static)
- Domain layer should minimize dependencies

### Alternative 3: Pydantic Settings

**Structure:**

```python
from pydantic_settings import BaseSettings

class TagRegistryConfig(BaseSettings):
    namespace_mapping: dict[str, str]
```

**Rejected because:**

- Adds Pydantic dependency to pure domain layer
- Configuration is not runtime-configurable (it's code, not config)
- Namespace mapping is part of domain logic, not infrastructure config

---

## Related

- [PADR-108: Domain Service Protocols](PADR-108-domain-service-protocols.md) — Pure function protocols
- [PADR-113: Two-Tier Validation Pattern](PADR-113-two-tier-validation.md) — Uses validate_tag() from registry
- [ref-domain-module-level-registry.md](../../domains/event-store-cqrs/references/ref-domain-module-level-registry.md) — Detailed pattern reference

---

## Acceptance Criteria

- [ ] Human review approved
- [ ] Status changed from "Proposed" to "Accepted"
- [ ] Convention documented in KB references
- [ ] Future registries follow this pattern
