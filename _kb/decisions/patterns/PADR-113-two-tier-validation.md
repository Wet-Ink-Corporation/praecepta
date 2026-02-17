<!-- Derived from {Project} PADR-113-two-tier-validation -->
# PADR-113: Two-Tier Validation Pattern

**Status:** Proposed
**Date:** 2026-02-06
**Deciders:** Architecture Team
**Categories:** Pattern, Domain Design
**Proposed by:** docs-enricher (feature F-100-002)

---

## Context

Domain value objects often require validation at multiple levels. Traditional single-stage validation mixes concerns and limits composability:

```python
class Tag:
    def __init__(self, tag_string: str):
        # Format validation
        if ":" not in tag_string:
            raise ValueError("Missing separator")

        # Semantic validation
        if namespace == "agent-memory" and value not in ALLOWED_VALUES:
            raise ValueError("Invalid agent-memory value")
```

**Problems with single-stage validation:**

1. **Coupling**: Format logic mixed with domain business rules
2. **Composability**: Cannot defer semantic validation to later stages
3. **Error Collection**: Exceptions short-circuit; cannot collect multiple errors
4. **Testing**: Cannot test format validation without domain context
5. **Layering**: API layer cannot distinguish format errors from semantic errors

Feature F-100-002 (Tag System) introduced a Tag value object with two distinct validation needs:

- **Format Validation**: `namespace:value[:subvalue]` regex pattern (structural integrity)
- **Semantic Validation**: Controlled vocabularies for `agent-memory` and `classification:sensitivity` (business rules)

The format check ensures the tag _can exist_ as a valid object. The semantic check ensures the tag _is meaningful_ in the domain. These are fundamentally different concerns with different error handling needs.

**Question:** Should we throw exceptions for both, or use a different error signaling mechanism?

---

## Decision

**We will separate validation into two tiers with different error signaling mechanisms:**

### Tier 1: Format Validation (Constructor)

- **Where:** Value object `__init__` or factory method
- **Scope:** Structural integrity only (regex, type checks, required fields)
- **Error Signaling:** **Raise `ValueError`** immediately
- **Philosophy:** "If format is invalid, the object cannot exist"

### Tier 2: Semantic Validation (Pure Function)

- **Where:** Separate pure function (e.g., `validate_tag()` in registry module)
- **Scope:** Business rules, controlled vocabularies, domain constraints
- **Error Signaling:** **Return `ValidationResult` dataclass**
- **Philosophy:** "Object is structurally valid but may not be semantically meaningful"

**ValidationResult structure:**

```python
@dataclass(frozen=True)
class ValidationResult:
    """Result of semantic validation."""
    is_valid: bool
    error_message: str | None = None
    tag: Tag | None = None  # The validated object
```

**Implementation example:**

```python
# Tier 1: Format Validation in Constructor
@dataclass(frozen=True)
class Tag:
    namespace: str
    value: str
    subvalue: str | None = None

    def __init__(self, tag_string: str) -> None:
        """Parse and validate tag format.

        Raises:
            ValueError: If format is invalid (immediate failure).
        """
        normalized = tag_string.strip().lower()

        if not _TAG_PATTERN.match(normalized):
            msg = f"Invalid tag format '{tag_string}'"
            raise ValueError(msg)

        parts = normalized.split(":", maxsplit=2)
        object.__setattr__(self, "namespace", parts[0])
        object.__setattr__(self, "value", parts[1])
        object.__setattr__(self, "subvalue", parts[2] if len(parts) == 3 else None)


# Tier 2: Semantic Validation in Separate Module
def validate_tag(tag: Tag) -> ValidationResult:
    """Perform semantic validation on a format-valid tag.

    Args:
        tag: A format-valid Tag instance.

    Returns:
        ValidationResult with is_valid=True if tag passes, or
        is_valid=False with descriptive error_message.
    """
    if tag.namespace == "agent-memory" and tag.value not in AGENT_MEMORY_VALUES:
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"Value '{tag.value}' is not in the allowed list for "
                f"namespace 'agent-memory'. Allowed: {sorted(AGENT_MEMORY_VALUES)}"
            ),
            tag=tag,
        )

    return ValidationResult(is_valid=True, tag=tag)
```

---

## Consequences

### Positive

- **Separation of Concerns**: Format logic decoupled from domain business rules
- **Composability**: ValidationResult objects can be chained, aggregated, or deferred
- **Error Collection**: Can gather multiple semantic errors before failing
- **Testability**: Format validation tests need no domain context
- **Type Safety**: ValidationResult is typed, errors are structured
- **Pure Functions**: Semantic validation has no side effects or I/O
- **Layering**: API layer can distinguish format errors (422) from semantic errors (domain-specific codes)

### Negative

- **Two Steps**: Caller must perform both format and semantic validation
- **Boilerplate**: ValidationResult dataclass adds code vs simple exceptions
- **Potential Inconsistency**: Developers might forget semantic validation step
- **Learning Curve**: Pattern is non-obvious to developers new to the codebase

### Neutral

- Established convention for multi-stage validation across the codebase
- Aligns with Railway-Oriented Programming principles (errors as values)
- Clear separation between "object cannot exist" vs "object is not meaningful"

---

## Implementation Notes

- **Feature:** F-100-002 Tag System
- **Stories:** S-100-002-001 (format validation), S-100-002-002 (semantic validation)
- **Key Files:**
  - `src/{Project}/ordering/domain/value_objects.py` (Tag.**init** with format validation)
  - `src/{Project}/ordering/domain/tag_registry.py` (validate_tag with semantic validation)
- **Pattern Doc:** [ref-domain-two-tier-validation.md](../../domains/ddd-patterns/references/ref-domain-two-tier-validation.md)

**Pattern applies to:**

- Value objects with controlled vocabularies
- Multi-stage validation pipelines
- Validation requiring domain context
- Scenarios needing error collection

**Pattern does NOT apply to:**

- Simple validation (just use ValueError)
- Validation requiring I/O (move to application layer)
- Trivial checks (use Pydantic field validators)

---

## Usage Example

### API Endpoint with Two-Tier Validation

```python
from fastapi import HTTPException

def create_block(request: CreateBlockRequest) -> BlockDTO:
    """Create a order with tag validation."""

    # Tier 1: Format validation (raises ValueError for invalid format)
    try:
        tags = [Tag(t) for t in request.tags]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Tier 2: Semantic validation (returns ValidationResult)
    for tag in tags:
        result = validate_tag(tag)
        if not result.is_valid:
            raise HTTPException(status_code=422, detail=result.error_message)

    # Proceed with business logic
    command = CreateBlockCommand(tags=tuple(tags))
    return execute_command(command)
```

### Collecting Multiple Validation Errors

```python
def validate_tags_batch(tag_strings: list[str]) -> dict[str, list[str]]:
    """Validate multiple tags and return all errors."""
    format_errors = []
    semantic_errors = []
    valid_tags = []

    # Tier 1: Format validation
    for tag_str in tag_strings:
        try:
            tag = Tag(tag_str)
            valid_tags.append(tag)
        except ValueError as e:
            format_errors.append(f"{tag_str}: {e}")

    # Tier 2: Semantic validation (only for format-valid tags)
    for tag in valid_tags:
        result = validate_tag(tag)
        if not result.is_valid:
            semantic_errors.append(f"{tag}: {result.error_message}")

    return {
        "format_errors": format_errors,
        "semantic_errors": semantic_errors,
    }
```

---

## Alternatives Considered

### Alternative 1: All Exceptions

**Structure:**

```python
def __init__(self, tag_string: str):
    # Format validation
    if not valid_format:
        raise ValueError("Format error")

    # Semantic validation
    if not valid_semantic:
        raise ValueError("Semantic error")
```

**Rejected because:**

- Cannot collect multiple errors (first exception short-circuits)
- Cannot defer semantic validation to later stages
- Mixes format concerns with domain concerns
- No way to distinguish error types programmatically

### Alternative 2: All ValidationResult

**Structure:**

```python
def create_tag(tag_string: str) -> ValidationResult:
    # Format validation returns ValidationResult
    if not valid_format:
        return ValidationResult(is_valid=False, error="Format error")
    # ...
```

**Rejected because:**

- Format errors prevent object construction (object _cannot exist_)
- Forces caller to check result even for simple format errors
- Loses Python's built-in exception handling for truly invalid inputs
- Inconsistent with standard library conventions (e.g., `datetime` raises on bad format)

### Alternative 3: Validation Context Object

**Structure:**

```python
class ValidationContext:
    def __init__(self):
        self.errors = []

    def validate(self, tag: Tag):
        if not valid:
            self.errors.append("error")

ctx = ValidationContext()
ctx.validate(tag)
if ctx.errors:
    # Handle errors
```

**Rejected because:**

- Stateful validation (not pure)
- More complex than needed for simple cases
- Harder to compose with functional pipelines
- Over-engineering for the common case

---

## Related

- [PADR-112: Module-Level Registry Pattern](PADR-112-module-level-registry.md) — Registry provides validate_tag() function
- [ref-domain-two-tier-validation.md](../../domains/ddd-patterns/references/ref-domain-two-tier-validation.md) — Detailed pattern reference
- [ref-domain-module-level-registry.md](../../domains/event-store-cqrs/references/ref-domain-module-level-registry.md) — Module-level validation functions

---

## Acceptance Criteria

- [ ] Human review approved
- [ ] Status changed from "Proposed" to "Accepted"
- [ ] Pattern documented in KB references
- [ ] Future value objects with controlled vocabularies follow this pattern
