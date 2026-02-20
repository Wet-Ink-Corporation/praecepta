# Dimension 2: Domain Model Quality

**RAG Status:** AMBER
**Average Maturity:** 3.8/5
**Date:** 2026-02-18

## Executive Summary

The Praecepta domain model demonstrates solid fundamentals across its three constituent areas -- foundation primitives, tenancy bounded context, and identity bounded context. The foundation layer (Layer 0) provides a well-designed set of base classes, value objects, an exemplary exception hierarchy, and protocol-based ports that are consistently consumed by the two domain packages. The Tenant aggregate in the tenancy context stands out as a reference-grade DDD event-sourced aggregate with a rigorous four-state lifecycle, comprehensive idempotency, and rich audit metadata. The identity context implements faithful renditions of PADR-prescribed patterns including JIT user provisioning with race condition handling and projection-based agent authentication.

However, the model has meaningful gaps that prevent a GREEN rating. The most significant finding is that the integration package (`praecepta-integration-tenancy-identity`) is a complete stub with no implementation, no entry points, and no tests -- meaning the cross-domain orchestration layer that should bridge tenancy and identity does not exist. Additionally, a recurring theme of validation inconsistency surfaces across the foundation: TenantId, TenantSlug, and BaseEvent enforce different rules for the same logical concept, and the split between `BaseEvent` metadata fields and the eventsourcing library's `@event`-generated inner event classes creates a gap in correlation/causation tracking. Several Medium-severity findings relate to incomplete implementations (cascade deletion stub, missing lifecycle terminal events) and subtle correctness issues (nondeterministic timestamp in Agent event replay, blocking sleep in async-eligible provisioning code).

Overall, the model is well-structured with strong conventions (PADR-114 lifecycle pattern, PADR-113 two-tier validation, PADR-119 separate applications) that are consistently followed where implemented. The primary risk is incompleteness rather than poor design -- the architecture is sound but several pieces remain scaffolded rather than fully realized. The codebase's exceptional documentation quality and thorough unit test coverage (178+ foundation tests, 85+ tenancy tests, 51+ identity tests) provide a strong base for closing these gaps.

## Consolidated Checklist

| # | Area | Item | Rating | Severity | Source |
|---|------|------|--------|----------|--------|
| 1 | Foundation | BaseAggregate Design | 3/5 | Medium | 2A |
| 2 | Foundation | Event System | 4/5 | Low | 2A |
| 3 | Foundation | Value Objects | 4/5 | Low | 2A |
| 4 | Foundation | Identifier Types | 3/5 | Medium | 2A |
| 5 | Foundation | Exception Hierarchy | 5/5 | None | 2A |
| 6 | Foundation | Port Definitions | 4/5 | Low | 2A |
| 7 | Foundation | Config Defaults | 3/5 | Medium | 2A |
| 8 | Foundation | Aggregate Lifecycle | 4/5 | Low | 2A |
| 9 | Foundation | Two-Tier Validation | 3/5 | Medium | 2A |
| 10 | Foundation | Event Sourcing Primitives | 3/5 | Medium | 2A |
| 11 | Foundation | Type Discrimination | 2/5 | Low | 2A |
| 12 | Foundation | `__all__` Exports | 4/5 | Low | 2A |
| 13 | Foundation | Test Coverage | 4/5 | Low | 2A |
| 14 | Tenancy | Tenant Aggregate | 5/5 | None | 2B |
| 15 | Tenancy | TenantApplication | 3/5 | Medium | 2B |
| 16 | Tenancy | Slug Registry | 5/5 | None | 2B |
| 17 | Tenancy | Tenant Configuration | 4/5 | Low | 2B |
| 18 | Tenancy | Projections | 4/5 | Low | 2B |
| 19 | Tenancy | Cascade Deletion | 2/5 | Medium | 2B |
| 20 | Tenancy | Tenant Repository | 4/5 | Low | 2B |
| 21 | Tenancy | Event Lifecycle | 5/5 | None | 2B |
| 22 | Tenancy | Validation Rules | 4/5 | Low | 2B |
| 23 | Tenancy | Error Handling | 4/5 | Low | 2B |
| 24 | Tenancy | `__all__` Exports | 4/5 | None | 2B |
| 25 | Tenancy | Test Coverage | 5/5 | Low | 2B |
| 26 | Tenancy | PADR Alignment | 4/5 | None | 2B |
| 27 | Identity | User Aggregate | 4/5 | Low | 2C |
| 28 | Identity | Agent Aggregate | 4/5 | Medium | 2C |
| 29 | Identity | UserApplication | 4/5 | None | 2C |
| 30 | Identity | AgentApplication | 4/5 | None | 2C |
| 31 | Identity | JIT Provisioning | 4/5 | Medium | 2C |
| 32 | Identity | OIDC Sub Registry | 4/5 | Low | 2C |
| 33 | Identity | User Profile Projection | 4/5 | Medium | 2C |
| 34 | Identity | Agent API Key Projection | 4/5 | Low | 2C |
| 35 | Identity | User Profile Repository | 4/5 | Low | 2C |
| 36 | Identity | Integration Package | 1/5 | High | 2C |
| 37 | Identity | Event Coverage | 3/5 | Medium | 2C |
| 38 | Identity | Validation & Errors | 4/5 | Low | 2C |
| 39 | Identity | Test Coverage | 4/5 | Medium | 2C |

### RAG Calculation

- **Total checklist items:** 39
- **Sum of ratings:** 147
- **Average maturity:** 147 / 39 = **3.77 (rounds to 3.8)**
- **Critical findings:** 0
- **High findings:** 1 (Item 36: Integration Package stub)
- **Items at 4+:** 28 / 39 = **71.8%**
- **Items at 3+:** 36 / 39 = **92.3%**

Applying RAG criteria:
- GREEN requires: no Critical/High, avg >= 4.0, >= 80% at 4+. **FAILS** (1 High, avg 3.77, 71.8% at 4+)
- AMBER requires: no Critical, <= 2 High, avg >= 3.0, >= 60% at 3+. **PASSES** (0 Critical, 1 High, avg 3.77, 92.3% at 3+)

**Result: AMBER**

## Critical & High Findings

### High Severity

**H-1. Integration package is a complete stub** (Source: 2C, Item 10)
The `praecepta-integration-tenancy-identity` package contains only an empty `__init__.py` with a docstring. No cross-domain sagas, event subscriptions, routers, or tests exist. This is the Layer 3 package intended to bridge tenancy and identity contexts (e.g., "tenant provisioned -> create admin user" workflows).
- `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1`
- `packages/integration-tenancy-identity/pyproject.toml:1-24` (no entry points registered)

## Medium Findings

**M-1. TenantId / TenantSlug / BaseEvent validation inconsistency** (Source: 2A, Items 4 & 9)
Three separate validation implementations exist for the same logical concept (tenant identifier format) with divergent rules:
- `TenantId`: pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`, no length constraint -- `packages/foundation-domain/src/praecepta/foundation/domain/identifiers.py:47`
- `TenantSlug`: pattern `^[a-z0-9][a-z0-9-]*[a-z0-9]$`, 2-63 chars -- `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:46`
- `BaseEvent.tenant_id`: pattern `^[a-z0-9][a-z0-9-]*[a-z0-9]$`, 2-63 chars -- `packages/foundation-domain/src/praecepta/foundation/domain/events.py:126`

A `TenantId("a")` is valid but cannot be used in events. This creates a data integrity gap at boundaries.

**M-2. BaseEvent metadata absent from @event-generated inner event classes** (Source: 2A, Item 10)
The `BaseEvent` class defines `correlation_id`, `causation_id`, and `user_id` metadata fields, plus `tenant_id` validation. However, aggregate events generated via the eventsourcing library's `@event` decorator (e.g., `Tenant.Provisioned`, `Agent.Registered`) do NOT extend `BaseEvent` and therefore lack these metadata fields entirely.
- `packages/foundation-domain/src/praecepta/foundation/domain/events.py:117-122` (BaseEvent metadata)
- `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:60` (inner event class, not extending BaseEvent)

**M-3. BaseAggregate does not enforce tenant_id assignment** (Source: 2A, Item 1)
The `tenant_id: str` annotation exists on `BaseAggregate` but there is no runtime verification that subclasses actually set it. No `__init_subclass__` hook or post-init check exists.
- `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:104`
- Neither `User.__init__` nor `Agent.__init__` validates tenant_id through a value object: `packages/domain-identity/src/praecepta/domain/identity/user.py:57`, `packages/domain-identity/src/praecepta/domain/identity/agent.py:59`

**M-4. Config value constraint metadata not enforced** (Source: 2A, Item 7)
`IntegerConfigValue` and `FloatConfigValue` accept optional `min_value`/`max_value` bounds but do not validate that `value` falls within those bounds. `EnumConfigValue` has an `allowed_values` list but does not validate that `value` is a member.
- `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:59-74` (Integer/Float)
- `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:92-97` (Enum)

**M-5. Tier 2 (semantic) validation not codified** (Source: 2A, Item 9)
PADR-113 describes a `ValidationResult` type for semantic/business rule validation, but no such type exists in the foundation package. Aggregates perform business rule validation inline via exception raising.
- PADR-113 pattern reference only; no implementation in foundation-domain.

**M-6. Cascade deletion is a stub** (Source: 2B, Item 6)
`CascadeDeletionService.delete_tenant_data()` logs start/completion and sets flags but performs no actual projection table deletion. The "Phase 1" extension point is empty. Decommissioned tenant data persists in projection tables indefinitely.
- `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/cascade_deletion.py:76-84`

**M-7. TenantApplication adds minimal domain service value** (Source: 2B, Item 2)
The application service is a bare subclass of `Application[UUID]` with only a snapshotting interval. No orchestration methods (e.g., `provision_tenant()`, `get_by_slug()`) exist.
- `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant_app.py:17-27`

**M-8. Nondeterministic timestamp in Agent event mutator** (Source: 2C, Item 2)
`_apply_api_key_rotated` calls `datetime.now(UTC).isoformat()` for the new key's `created_at`. Event replay would produce different timestamps on each reconstitution, violating event sourcing determinism.
- `packages/domain-identity/src/praecepta/domain/identity/agent.py:196`

**M-9. Blocking `time.sleep()` in provisioning retry loop** (Source: 2C, Item 5)
The `UserProvisioningService` race condition retry uses `time.sleep()`, which would block the event loop if called from an async context. Per PADR-118, provisioning is called from middleware which could be async.
- `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:113`

**M-10. Display name derivation logic duplicated** (Source: 2C, Item 7)
The User aggregate and the UserProfileProjection both independently implement the `name -> email prefix -> "User"` fallback chain. Changes to one must be manually synchronized with the other.
- `packages/domain-identity/src/praecepta/domain/identity/user.py:60-65`
- `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:66-73`

**M-11. Missing lifecycle terminal events for identity aggregates** (Source: 2C, Item 11)
User has no deactivation/deletion event. Agent has no deregistration event. Neither aggregate has a terminal lifecycle state, limiting audit trail completeness.
- `packages/domain-identity/src/praecepta/domain/identity/user.py:17-100`
- `packages/domain-identity/src/praecepta/domain/identity/agent.py:23-199`

**M-12. No integration tests across any domain package** (Source: 2C, Item 13; also 2B, Item 12)
All tests are unit tests with mocks. No tests verify PostgreSQL-level behavior (unique constraints, UPSERT conflict resolution, RLS policies, slug registry concurrency). Repository classes in the identity context have no direct tests at all.
- `packages/domain-identity/tests/` (all `@pytest.mark.unit`)
- `packages/domain-tenancy/tests/` (all `@pytest.mark.unit`)

## Low & Info Findings

The following Low-severity findings were identified across all three collectors. They represent minor gaps, nice-to-have improvements, or stylistic concerns rather than risks requiring immediate action.

**Foundation (2A):**
- `BaseEvent.to_dict()` does not automatically include subclass fields; requires override boilerplate (`events.py:216-275`).
- `APIKeyMetadata` lacks field validation (no checks on key_id, status, created_at) (`agent_value_objects.py:80-83`).
- Pydantic dependency at Layer 0 creates transitive coupling, though it is explicitly declared and not on the exclusion list.
- Lifecycle state machine pattern not codified as a mixin/protocol in foundation; enforced by convention only.
- Type discrimination pattern (PADR-111) documented but not implemented; not yet needed by current aggregates.
- Sub-modules lack individual `__all__` lists (top-level `__init__.py` curates the public API).
- No tests for `SYSTEM_DEFAULTS`, `PolicyType` extensibility, or `BaseEvent` interaction with `@event` decorator.

**Tenancy (2B):**
- RLS documentation mismatch in ConfigRepository: docstring says "RLS-aware" but queries use explicit `WHERE tenant_id` (`config_repository.py:5`).
- Both projections access `self._repo._session_factory()` directly in `clear_read_model()`, breaking repository encapsulation.
- `TenantRepository.list_all()` returns all tenants without pagination (`tenant_repository.py:64`).
- Repository methods return `dict[str, Any]` rather than typed DTOs.
- No tenant-specific NotFoundError or SlugAlreadyTakenError subclasses.
- SuspensionCategory enum exists but aggregate accepts any string for suspension category.

**Identity (2C):**
- User immutability (oidc_sub, email, tenant_id) enforced by convention only, not programmatically.
- Initial `name` parameter at User creation not validated via `DisplayName` value object, though updates are (`user.py:60-61` vs `:81`).
- No stale reservation cleanup logic in OidcSubRegistry (index exists but no cleanup job) (`oidc_sub_registry.py:40-42`).
- `AgentAPIKeyRepository.truncate()` uses `DELETE FROM` instead of `TRUNCATE TABLE`, inconsistent with UserProfileRepository (`agent_api_key_repository.py:116`).
- Missing `get_by_oidc_sub` async read method on UserProfileRepository.
- `AgentAPIKeyRepository` lacks `ensure_table_exists` classmethod, inconsistent with other repositories.
- Non-atomic rotation handler in AgentAPIKeyProjection (revoke + upsert not in single transaction) (`agent_api_key.py:64-79`).
- `active_keys` on Agent uses `list[dict[str, str]]` instead of typed value objects (`agent.py:62`).
- Inconsistent use of `ValueError` (User) vs `ValidationError` (Agent) for creation validation.
- SQLAlchemy is a direct dependency of the domain-identity package, placing infrastructure concerns at the domain layer (`pyproject.toml:14`).

## Cross-Cutting Themes

### 1. Validation Rule Fragmentation
A persistent theme across all three collectors is the duplication and divergence of validation logic. TenantId, TenantSlug, and BaseEvent enforce different rules for the same concept. Display name derivation is duplicated between aggregate and projection. The two-tier validation pattern (PADR-113) has Tier 1 well-implemented but Tier 2 (`ValidationResult`) remains unimplemented. This fragmentation creates risk of subtle data integrity bugs at module boundaries and increases the maintenance burden when validation rules evolve.

### 2. Incomplete Scaffolding at the Edges
The core aggregates and their immediate infrastructure are mature (average 4.0+ in tenancy), but components at the system edges remain stubbed. The integration package (Layer 3) has no implementation. Cascade deletion is a stub. Application services are minimal type aliases without orchestration methods. This pattern suggests the team has correctly prioritized core domain modeling but has not yet addressed the orchestration and lifecycle completion work needed for production readiness.

### 3. Event Sourcing Library Tension
Multiple findings reflect friction between the framework's custom domain model (`BaseEvent`, `BaseAggregate`) and the eventsourcing library's own patterns (`@event` decorator, dynamic inner event classes). `BaseEvent` metadata fields are absent from `@event`-generated events. Nondeterministic timestamps in event mutators violate replay determinism. The `to_dict()` method only serializes base fields. This tension needs a deliberate reconciliation strategy -- either threading `BaseEvent` metadata into the library's event generation, or accepting and documenting the two-tier event class hierarchy.

### 4. Unit-Only Test Strategy
All three packages exclusively use `@pytest.mark.unit` tests with mocked dependencies. While unit coverage is strong (314+ tests total), no integration tests verify PostgreSQL-level behavior (unique constraints, RLS policies, UPSERT conflict resolution) or end-to-end workflows (provisioning, decommission orchestration). Given that the domain model relies heavily on database-level guarantees (slug uniqueness, OIDC sub uniqueness, RLS tenant isolation), this represents a meaningful confidence gap.

## Strengths

1. **Exemplary aggregate design in the Tenant bounded context.** The Tenant aggregate is a reference-grade implementation of PADR-114 with a rigorous four-state lifecycle, comprehensive idempotency on all transitions, rich audit metadata on events, and terminal state enforcement. It serves as the gold standard for all future aggregates.

2. **Exception hierarchy maturity (5/5).** The nine-class exception hierarchy rooted at `DomainError` provides complete coverage of standard domain error scenarios with error codes, structured context, inheritance (e.g., `InvalidStateTransitionError` extends `ConflictError`), and HTTP status mapping. It is the most mature component in the entire domain model.

3. **Concurrency-safe registration patterns.** Both the `SlugRegistry` (tenancy) and `OidcSubRegistry` (identity) implement the reserve-confirm-release three-phase pattern with PostgreSQL primary key uniqueness enforcement, compensating actions for saga rollback, and idempotent table creation. The JIT `UserProvisioningService` adds race condition retry with exponential backoff.

4. **Consistent PADR compliance.** The codebase faithfully follows its architectural decision records. PADR-114 (lifecycle state machine), PADR-113 (two-tier validation Tier 1), PADR-119 (separate applications per aggregate), PADR-118 (JIT provisioning), PADR-121 (projection-based auth), and PADR-109 (sync-first) are all correctly implemented where applicable.

5. **Documentation quality.** Every class and method in the foundation package includes detailed docstrings with purpose, attribute documentation, args/returns/raises, usage examples, and cross-references to PADRs. This investment in documentation significantly lowers the onboarding cost and reduces the risk of convention drift.

## Recommendations

**P1 -- Address before production:**

1. **Harmonize tenant identifier validation.** Align `TenantId` validation with `TenantSlug` and `BaseEvent.tenant_id` (2-63 chars, same regex pattern). Extract the canonical validation rule into a single shared constant or function to prevent future drift.
   - Refs: `identifiers.py:47`, `tenant_value_objects.py:46`, `events.py:126`

2. **Fix nondeterministic timestamp in Agent event mutator.** Move `datetime.now(UTC).isoformat()` from `_apply_api_key_rotated` into `request_rotate_api_key` and pass it as an event parameter to ensure replay determinism.
   - Ref: `packages/domain-identity/src/praecepta/domain/identity/agent.py:196`

3. **Add integration tests for database-level guarantees.** Create `@pytest.mark.integration` tests verifying: slug registry uniqueness under concurrent access, OIDC sub registry uniqueness, RLS tenant isolation in user profile repository, and UPSERT idempotency across all projections and repositories.

4. **Implement cascade deletion for projections.** Complete `CascadeDeletionService.delete_tenant_data()` to actually delete rows from `tenant_list`, `tenant_config`, `user_profiles`, and `agent_api_key_registry` tables for decommissioned tenants.
   - Ref: `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/cascade_deletion.py:76-84`

5. **Enforce config value constraints.** Add Pydantic `model_validator` to `IntegerConfigValue`, `FloatConfigValue`, and `EnumConfigValue` to validate that values respect their declared bounds and allowed sets.
   - Ref: `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:59-97`

**P2 -- Address for architectural completeness:**

6. **Resolve BaseEvent / @event-generated event class disconnect.** Document or implement a strategy for threading `correlation_id`, `causation_id`, and `user_id` into aggregate events created via `@event` decorator, possibly via custom event class configuration on the eventsourcing Application.

7. **Replace blocking `time.sleep()` in provisioning retry.** Use `asyncio.sleep()` or make the provisioning service explicitly sync-only with documentation. Alternatively, use a retry library with async support.
   - Ref: `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:113`

8. **Implement the integration package.** Begin with the most critical cross-domain saga (tenant provisioned -> create admin user) and register entry points for routers, projections, or lifespan hooks as appropriate.
   - Ref: `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1`

9. **Add tenant_id validation to identity aggregates.** Validate `tenant_id` through `TenantId` value object in both `User.__init__` and `Agent.__init__` to prevent empty or malformed tenant identifiers.
   - Refs: `packages/domain-identity/src/praecepta/domain/identity/user.py:57`, `agent.py:59`

10. **Extract display name derivation into a shared function.** Create a foundation-level or identity-domain utility function for the `name -> email prefix -> "User"` fallback chain, used by both the aggregate and projection.
    - Refs: `user.py:60-65`, `user_profile.py:66-73`

**P3 -- Nice-to-have improvements:**

11. **Implement `ValidationResult` per PADR-113.** Create a frozen dataclass in the foundation package for structured Tier 2 semantic validation results.

12. **Add `LifecycleAggregate` mixin or `@transition` decorator** to codify the PADR-114 lifecycle pattern in the foundation layer rather than relying on convention alone.

13. **Add lifecycle terminal events to identity aggregates.** Implement `User.Deactivated` and `Agent.Deregistered` events for audit trail completeness.

14. **Add `AgentId` identifier type** to the foundation package for type-safe agent identification, paralleling `TenantId` and `UserId`.

15. **Add pagination to `TenantRepository.list_all()`** and consider typed DTO return values instead of `dict[str, Any]`.

16. **Add `__all__` to individual foundation sub-modules** for completeness and static analysis tool support.
