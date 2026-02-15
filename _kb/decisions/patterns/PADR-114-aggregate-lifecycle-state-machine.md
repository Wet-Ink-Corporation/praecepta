<!-- Derived from {Project} PADR-114-aggregate-lifecycle-state-machine -->
# PADR-114: Aggregate Lifecycle State Machine Convention

**Status:** Proposed
**Date:** 2026-02-06
**Deciders:** Architecture Team
**Categories:** Pattern, Domain
**Proposed by:** docs-enricher (feature F-101-001)

---

## Context

With the implementation of F-101-001 (Tenant Lifecycle), {Project} now has two event-sourced aggregates with multi-state lifecycle machines:

1. **Order** (3 states: ACTIVE, ARCHIVED, DELETED) — introduced in F-100-001
2. **Tenant** (4 states: PROVISIONING, ACTIVE, SUSPENDED, DECOMMISSIONED) — introduced in F-101-001

Both aggregates independently arrived at the same pattern for managing state transitions:

- Public `request_*()` methods that validate invariants and check idempotency
- Private `_apply_*()` methods decorated with `@event` that perform state mutation
- Idempotent same-state transitions that return without recording events
- Terminal states that block all further transitions

This pattern emerged organically but is not formally documented as a convention. Future aggregates (e.g., ProcessingJob, LifecycleRule) will need lifecycle state machines. Without a formal convention, each implementation may diverge in naming, idempotency behavior, and error handling.

The existing `con-domain-model.md` describes aggregate design principles and mentions the two-method pattern, but does not specify the idempotency convention, naming standards, or terminal state handling.

## Decision

All event-sourced aggregates with 3 or more lifecycle states MUST follow the **Aggregate Lifecycle State Machine Pattern**:

1. **Public command methods** named `request_{action}()` that:
   - Check idempotency first (target state already reached → return silently)
   - Validate source state (invalid → raise `InvalidStateTransitionError`)
   - Delegate to private `_apply_{action}()` method

2. **Private event methods** named `_apply_{action}()` decorated with `@event("{PastTenseVerb}")` that:
   - Only perform state mutation (no validation)
   - Use past-tense event names (Activated, Suspended, Archived)

3. **Status storage** as `StrEnum.value` strings (not enum instances) for event serialization compatibility.

4. **Terminal states** that raise `InvalidStateTransitionError` for any transition attempt (except idempotent same-state check).

## Consequences

### Positive

- Consistent aggregate API across all bounded contexts
- Safe retries built in (idempotent by design)
- Events only recorded for valid transitions (no invalid event pollution)
- Clear separation of validation logic from event recording

### Negative

- Two methods per transition increases boilerplate
- Idempotent no-ops may hide caller bugs (silent success on invalid calls)
- Empty string convention for optional `@event` parameters is non-obvious

### Neutral

- Each bounded context may define its own `InvalidStateTransitionError` subclass for context-specific error codes
- Aggregates with only 2 states (create/delete) are not required to follow this pattern

## Implementation Notes

- **Feature:** F-101-001 (Tenant), F-100-001 (Order)
- **Key files:**
  - `src/{Project}/shared/domain/tenant.py` — Tenant aggregate (4-state)
  - `src/{Project}/ordering/domain/aggregates.py` — Order aggregate (3-state)
- **Pattern:** [ref-domain-aggregate-lifecycle.md](../../architecture-bible/08-crosscutting/ref-domain-aggregate-lifecycle.md)

## Related

- [PADR-001: Event Sourcing](../strategic/PADR-001-event-sourcing.md) — Core event sourcing pattern
- [PADR-109: Sync-First Event Sourcing](PADR-109-sync-first-eventsourcing.md) — Async strategy for commands
- [con-domain-model.md](../../architecture-bible/08-crosscutting/con-domain-model.md) — Aggregate design principles
