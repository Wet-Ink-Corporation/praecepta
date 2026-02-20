# Foundation Primitives Audit

**Dimension:** Domain Model Quality
**Collector:** 2A -- Foundation Primitives
**Date:** 2026-02-18
**Package:** `praecepta-foundation-domain` (Layer 0)
**Version:** 0.3.0

---

## Summary Statistics

| # | Checklist Item | Maturity | Confidence |
|---|----------------|----------|------------|
| 1 | BaseAggregate Design | 3 | High |
| 2 | Event System | 4 | High |
| 3 | Value Objects | 4 | High |
| 4 | Identifier Types | 3 | High |
| 5 | Exception Hierarchy | 5 | High |
| 6 | Port Definitions | 4 | High |
| 7 | Config Defaults | 3 | Medium |
| 8 | Aggregate Lifecycle | 4 | High |
| 9 | Two-Tier Validation | 3 | High |
| 10 | Event Sourcing Primitives | 3 | High |
| 11 | Type Discrimination | 2 | High |
| 12 | `__all__` Exports | 4 | High |
| 13 | Test Coverage | 4 | High |

**Overall Maturity:** 3.5 (Defined, trending toward Managed)
**Test Suite:** 178 tests, all passing, 1.07s execution time

---

## Detailed Findings

### 1. BaseAggregate Design -- Maturity: 3 (Defined)

**Findings:**

- BaseAggregate extends `eventsourcing.domain.Aggregate` which provides `id`, `version`, `created_on`, `modified_on`, `collect_events()`, and snapshot support.
  - `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26`
- Multi-tenancy is enforced via a `tenant_id: str` annotation but there is no runtime enforcement at the BaseAggregate level. Subclasses must set `self.tenant_id` in their decorated `__init__`, but nothing in BaseAggregate validates this was done.
  - `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:104`
- No lifecycle state attribute or pattern at the base level. Each domain aggregate (Tenant, Agent) independently implements lifecycle state as a `str` field with StrEnum values. This is documented as a convention in PADR-114 but not enforced by the base class.
- No abstract methods or template method hooks to guide subclass authors (e.g., no enforced `_validate_invariants()` hook).
- The class body is essentially empty beyond the `tenant_id` annotation and extensive docstrings. The docstrings are exemplary -- detailed usage patterns, command pattern example, and cross-references.
  - `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:27-101`

**Severity:** Medium -- The thin base class is a deliberate choice that avoids fighting the eventsourcing library's metaclass, but it means multi-tenancy enforcement is convention-only.

**Improvement Opportunities:**
- Consider a `__init_subclass__` hook or `__post_init__` style verification that `tenant_id` was set.
- Consider extracting a `LifecycleAggregate` mixin or intermediate class that provides `status`, `request_*`, `_apply_*` scaffolding per PADR-114.

---

### 2. Event System -- Maturity: 4 (Managed)

**Findings:**

- `BaseEvent` extends `eventsourcing.domain.DomainEvent` as a frozen kw_only dataclass. Immutability is verified by test.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:63-64`
- Required metadata fields are well-defined: `tenant_id` (required), `correlation_id`, `causation_id`, `user_id` (optional).
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:117-122`
- `tenant_id` validation uses regex with DNS-compatible format (2-63 chars, lowercase alphanumeric + hyphens). Validation is thorough with clear error messages.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:126-188`
- `get_topic()` provides fully-qualified event topic for routing/deserialization.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:191-214`
- `to_dict()` handles serialization of base fields with UUID and datetime conversion. However, it only serializes base event fields -- subclass fields are excluded by design, requiring overrides.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:216-275`
- Event schema evolution strategy is comprehensively documented in the module docstring, covering backward-compatible changes and upcaster patterns.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:22-51`

**Severity:** Low -- The system is well-designed. Minor gap in `to_dict()` not including subclass fields automatically.

**Improvement Opportunities:**
- Consider making `to_dict()` introspect all dataclass fields (via `dataclasses.fields()`) so subclass fields are included without override boilerplate.
- The `__post_init__` override on a frozen dataclass works here because the eventsourcing library likely handles this, but this is a fragile coupling point worth documenting.

---

### 3. Value Objects -- Maturity: 4 (Managed)

**Findings:**

- All value objects are frozen dataclasses with `slots=True` for memory efficiency and immutability enforcement.
  - `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:49` (TenantSlug)
  - `packages/foundation-domain/src/praecepta/foundation/domain/user_value_objects.py:14` (OidcSub)
  - `packages/foundation-domain/src/praecepta/foundation/domain/user_value_objects.py:39` (Email)
  - `packages/foundation-domain/src/praecepta/foundation/domain/user_value_objects.py:66` (DisplayName)
  - `packages/foundation-domain/src/praecepta/foundation/domain/agent_value_objects.py:31` (AgentTypeId)
  - `packages/foundation-domain/src/praecepta/foundation/domain/agent_value_objects.py:66` (APIKeyMetadata)
- Construction-time validation is consistent across all VOs. TenantSlug validates length (2-63) and regex pattern. TenantName strips whitespace and checks emptiness/length. Email allows empty string as valid (optional OIDC claim). OidcSub validates non-empty and length. DisplayName strips whitespace. AgentTypeId validates length and pattern.
- TenantName and DisplayName use `object.__setattr__` to strip whitespace on frozen dataclasses -- correct pattern.
  - `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:102`
  - `packages/foundation-domain/src/praecepta/foundation/domain/user_value_objects.py:90`
- StrEnum types (TenantStatus, SuspensionCategory, AgentStatus, PrincipalType) provide type-safe enumerations with native JSON serialization.
- APIKeyMetadata stores no plaintext secrets -- only key_id, key_hash, created_at, status. This is a good security practice explicitly documented.
  - `packages/foundation-domain/src/praecepta/foundation/domain/agent_value_objects.py:67-83`
- APIKeyMetadata lacks validation on its fields (no checks that key_id is non-empty, status is a valid value, created_at is ISO format). It is purely a structural container.
  - `packages/foundation-domain/src/praecepta/foundation/domain/agent_value_objects.py:80-83`

**Severity:** Low -- Minor gap in APIKeyMetadata lacking field validation.

**Improvement Opportunities:**
- Add validation to `APIKeyMetadata` (non-empty `key_id`, constrained `status` values, ISO 8601 `created_at` format).
- Consider adding `__str__` methods to value objects for consistent serialization (currently only TenantId and UserId have them).

---

### 4. Identifier Types -- Maturity: 3 (Defined)

**Findings:**

- Two identifier types are defined: `TenantId` (wraps str with slug validation) and `UserId` (wraps UUID).
  - `packages/foundation-domain/src/praecepta/foundation/domain/identifiers.py:23-84`
- Both are frozen dataclasses with equality semantics and `__str__` methods.
- TenantId uses a different regex pattern than TenantSlug: `^[a-z0-9]+(?:-[a-z0-9]+)*$` vs `^[a-z0-9][a-z0-9-]*[a-z0-9]$`. This means TenantId allows single-character values ("a") while TenantSlug requires minimum 2 characters. The patterns also differ in hyphen handling -- TenantId rejects consecutive hyphens via the `(?:-[a-z0-9]+)*` group, while TenantSlug's pattern technically allows them but enforces min length 2.
  - `packages/foundation-domain/src/praecepta/foundation/domain/identifiers.py:47`
  - `packages/foundation-domain/src/praecepta/foundation/domain/tenant_value_objects.py:46`
- **Critical inconsistency**: TenantId has no length constraint while TenantSlug enforces 2-63 chars, and BaseEvent.tenant_id validation enforces 2-63 chars. A TenantId("a") is valid but cannot be used in events.
  - `packages/foundation-domain/src/praecepta/foundation/domain/identifiers.py:47-56` (no length check)
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:174` (length 2-63)
- Type safety is partial -- TenantId and UserId are distinct types and cannot be accidentally swapped. However, the actual domain aggregates store `tenant_id` as plain `str`, not as `TenantId`. The identifier wrapper types are available but not used consistently.
  - `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:104` (`tenant_id: str`)
- No AgentId type exists despite Agent aggregate being a first-class entity.

**Severity:** Medium -- The inconsistency between TenantId validation and TenantSlug/BaseEvent validation is a real gap. The lack of consistent usage of typed identifiers across the codebase weakens their value.

**Improvement Opportunities:**
- Align TenantId validation with TenantSlug (2-63 chars, same regex pattern).
- Add AgentId identifier type.
- Consider using TenantId/UserId in aggregate attribute types (at least via type aliases) to strengthen type safety beyond the wrapper.

---

### 5. Exception Hierarchy -- Maturity: 5 (Optimizing)

**Findings:**

- Comprehensive exception hierarchy rooted at `DomainError(Exception)` with error_code, message, and structured context.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:33-73`
- Nine concrete exception types covering all standard domain error scenarios:
  - `DomainError` (base), `NotFoundError` (404), `ValidationError` (422), `ConflictError` (409), `InvalidStateTransitionError` (409, subclass of ConflictError), `FeatureDisabledError` (403), `AuthenticationError` (401), `AuthorizationError` (403), `ResourceLimitExceededError` (429).
- Each exception has a distinct `error_code` string for machine-readable client handling.
- `NotFoundError` and `ResourceLimitExceededError` accept `**extra_context` kwargs for extensible debugging data.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:99`, `335`
- `InvalidStateTransitionError` correctly inherits from `ConflictError` (HTTP 409) creating a natural type hierarchy for error handlers.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:201`
- `AuthenticationError` supports RFC 6750 `auth_error` field for WWW-Authenticate header generation.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:276-293`
- `__str__` includes context for logging; `__repr__` includes class name for debugging.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:64-73`
- HTTP status mapping documented in docstrings throughout.
- Comprehensive `__all__` export list.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:20-30`

**Severity:** None -- This is the most mature component of the foundation package.

---

### 6. Port Definitions -- Maturity: 4 (Managed)

**Findings:**

- Two protocol-based ports defined: `LLMServicePort` and `APIKeyGeneratorPort`.
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/llm_service.py:23`
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/api_key_generator.py:20`
- Both use `@runtime_checkable` Protocol for isinstance() verification in tests and DI validation.
- `LLMServicePort` defines `complete()` (unstructured) and `complete_structured()` (Pydantic-validated) methods with proper type parameters.
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/llm_service.py:38-98`
- `APIKeyGeneratorPort` defines `generate_api_key()`, `extract_key_parts()`, and `hash_secret()` -- complete lifecycle for key management.
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/api_key_generator.py:45-75`
- Ports package has clean `__init__.py` with `__all__` export.
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/__init__.py:1-10`
- The `LLMServicePort` imports Pydantic's `BaseModel` directly (not under TYPE_CHECKING) because it's needed at runtime for the TypeVar bound. This technically makes the foundation package depend on Pydantic at runtime, though Pydantic is listed as a direct dependency.
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/llm_service.py:17`
- Tests verify protocol conformance with fake implementations and non-conforming rejection.
  - `packages/foundation-domain/tests/test_ports.py:16-112`

**Severity:** Low -- Pydantic dependency at the foundation level is documented in `pyproject.toml:11` as an explicit dependency. However, the CLAUDE.md states "Foundation packages must never import infrastructure frameworks (fastapi, sqlalchemy, httpx, structlog, opentelemetry, taskiq, redis)." Pydantic is not in this exclusion list but its presence at Layer 0 creates a coupling concern.

**Improvement Opportunities:**
- Consider whether `LLMServicePort.complete_structured()` response_type bound to `BaseModel` should use a simpler protocol instead of Pydantic directly, to keep foundation truly framework-free.
- The port set is limited to two. As the system grows, additional ports (e.g., EventPublisher, NotificationPort) may be needed.

---

### 7. Config Defaults -- Maturity: 3 (Defined)

**Findings:**

- `SYSTEM_DEFAULTS` is an empty mutable dict at the module level, intended to be populated at startup by consuming applications.
  - `packages/foundation-domain/src/praecepta/foundation/domain/config_defaults.py:29`
- `ConfigValue` is a Pydantic discriminated union of six typed config variants (Boolean, Integer, Float, String, Percentage, Enum).
  - `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:100-108`
- `ConfigKey` is an empty StrEnum base class for extensibility.
  - `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:31-49`
- `PolicyType` is an empty StrEnum base class similarly designed for extensibility.
  - `packages/foundation-domain/src/praecepta/foundation/domain/policy_types.py:28-46`
- PercentageConfigValue enforces 0-100 range via Pydantic Field validators.
  - `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:89`
- IntegerConfigValue and FloatConfigValue have optional `min_value`/`max_value` bounds but do NOT validate that `value` falls within those bounds at construction time -- the bounds are metadata only.
  - `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:59-74`
- EnumConfigValue has `allowed_values` list but does NOT validate that `value` is within `allowed_values` at construction time.
  - `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:92-97`
- No actual default values are shipped with the foundation package (by design -- consumers populate).

**Severity:** Medium -- The lack of constraint enforcement on IntegerConfigValue/FloatConfigValue/EnumConfigValue means invalid config values can be constructed without error.

**Improvement Opportunities:**
- Add Pydantic `model_validator` to IntegerConfigValue/FloatConfigValue to enforce `min_value <= value <= max_value` when bounds are present.
- Add Pydantic `model_validator` to EnumConfigValue to enforce `value in allowed_values`.
- Consider shipping a small set of common/canonical defaults or at least documenting the expected startup initialization pattern more prominently.

---

### 8. Aggregate Lifecycle -- Maturity: 4 (Managed)

**Findings:**

- PADR-114 defines the Aggregate Lifecycle State Machine Convention with: public `request_*()` methods (idempotency check, state validation, delegation), private `_apply_*()` mutators with `@event`, StrEnum.value storage, terminal state handling.
- The Tenant aggregate faithfully implements this pattern with 4-state machine (PROVISIONING -> ACTIVE <-> SUSPENDED -> DECOMMISSIONED).
  - `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:30-399`
- The Agent aggregate implements a 2-state machine (ACTIVE <-> SUSPENDED) following the same pattern.
  - `packages/domain-identity/src/praecepta/domain/identity/agent.py:23-199`
- The User aggregate has no lifecycle states (no status field) -- appropriate for its simpler domain.
  - `packages/domain-identity/src/praecepta/domain/identity/user.py:17-100`
- Idempotency is consistently implemented: calling a transition on an already-target-state aggregate is a silent no-op.
  - e.g., `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:122-123`
- Status is stored as `str` (StrEnum.value), not enum instances, ensuring event serialization compatibility per PADR-114 section 3.
  - `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:96`
- **Gap**: The lifecycle state machine pattern is not codified in the foundation layer. Each aggregate independently implements the request/apply pattern. There is no base class, mixin, or abstract contract enforcing the convention.

**Severity:** Low -- The convention is well-documented and consistently followed, but enforcement is purely by developer discipline.

**Improvement Opportunities:**
- Consider a `LifecycleAggregate` mixin or protocol in foundation that declares the pattern contract (e.g., `status: str` attribute, `_valid_transitions` class variable).
- Consider a `@transition(from_states, to_state)` decorator that encapsulates the idempotency/validation/delegation pattern to reduce boilerplate.

---

### 9. Two-Tier Validation -- Maturity: 3 (Defined)

**Findings:**

- PADR-113 defines the Two-Tier Validation Pattern: Tier 1 (format/structural) raises `ValueError` in constructors, Tier 2 (semantic/business rules) returns `ValidationResult`.
- Tier 1 validation is consistently implemented across all value objects:
  - TenantSlug: regex + length in `__post_init__` (`tenant_value_objects.py:65-77`)
  - TenantName: strip + empty/length in `__post_init__` (`tenant_value_objects.py:93-102`)
  - OidcSub: empty + length in `__post_init__` (`user_value_objects.py:30-36`)
  - Email: format regex + length in `__post_init__` (`user_value_objects.py:55-63`)
  - DisplayName: strip + empty/length in `__post_init__` (`user_value_objects.py:82-90`)
  - AgentTypeId: length + regex in `__post_init__` (`agent_value_objects.py:53-63`)
  - TenantId: regex in `__post_init__` (`identifiers.py:49-56`)
  - BaseEvent.tenant_id: regex + length in `__post_init__` (`events.py:128-137`)
- Tier 2 validation (semantic/business rules via `ValidationResult`) is NOT implemented in the foundation package. The PADR-113 pattern describes a `ValidationResult` dataclass, but no such type exists in the foundation-domain codebase.
- Domain aggregates that need business rule validation do it inline in `request_*()` methods, raising `InvalidStateTransitionError` or `ValidationError` directly.
  - e.g., `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:124-128`
  - e.g., `packages/domain-identity/src/praecepta/domain/identity/agent.py:121-125`

**Severity:** Medium -- Tier 1 is solid. Tier 2 remains at the pattern documentation stage; no `ValidationResult` type is available for consumers. The pattern describes a future capability that has not been codified into reusable primitives.

**Improvement Opportunities:**
- Implement `ValidationResult` as a frozen dataclass in the foundation package per PADR-113.
- Consider a `validate_semantic()` protocol or function signature convention.

---

### 10. Event Sourcing Primitives -- Maturity: 3 (Defined)

**Findings:**

- Events extend `eventsourcing.domain.DomainEvent` which natively supports replay and aggregate reconstruction via the library.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:64`
- BaseAggregate extends `eventsourcing.domain.Aggregate` which provides version tracking, optimistic concurrency, snapshotting, and event collection.
  - `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26`
- Event schema evolution is well-documented but no upcaster infrastructure exists in the foundation package.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:22-51`
- No custom transcoder or serialization override is defined at the foundation level. The framework relies on the eventsourcing library's default JSON transcoding.
- `BaseEvent.to_dict()` provides manual serialization but only for base fields; this is supplementary to the library's built-in serialization.
  - `packages/foundation-domain/src/praecepta/foundation/domain/events.py:216-275`
- The `@event` decorator from eventsourcing library handles event creation from method calls. Inner event classes (e.g., `Tenant.Provisioned`, `Tenant.Activated`) are dynamically generated -- these do NOT extend `BaseEvent`. This is a critical observation: the event hierarchy is split between `BaseEvent` subclasses (standalone events) and library-generated inner event classes (aggregate events).
- No explicit snapshot configuration or policy is defined in the foundation layer. PADR-001 mentions `snapshotting_intervals` but this is configured at the Application level, not at the aggregate level.
  - `_kb/decisions/strategic/PADR-001-event-sourcing.md:136-137`

**Severity:** Medium -- The split between `BaseEvent` subclasses and library-generated inner event classes means that the metadata fields (correlation_id, causation_id, user_id) defined on BaseEvent are NOT automatically present on aggregate events created via `@event` decorator. The tenant_id validation on BaseEvent does not apply to Tenant.Provisioned, Tenant.Activated, etc.

**Improvement Opportunities:**
- Document or resolve the disconnect between BaseEvent and @event-generated inner event classes. Consider whether BaseEvent's metadata fields need to be threaded into aggregate events (possibly via custom event class configuration on the eventsourcing Application).
- Provide foundation-level upcaster base class or registry for event schema evolution.
- Add snapshotting guidance or configuration helpers.

---

### 11. Type Discrimination -- Maturity: 2 (Initial)

**Findings:**

- PADR-111 describes the ClassVar-based aggregate type discrimination pattern in detail, with implementation examples and testing guidance.
  - `_kb/decisions/patterns/PADR-111-classvar-aggregate-type-discrimination.md:1-260`
- The pattern is NOT implemented in BaseAggregate. There is no `BLOCK_TYPE`, `TYPE_DISCRIMINATOR`, or equivalent ClassVar on the base class.
  - `packages/foundation-domain/src/praecepta/foundation/domain/aggregates.py:26-110` (no ClassVar)
- No concrete aggregate in the current codebase uses the ClassVar discrimination pattern. The Tenant, User, and Agent aggregates are standalone types without subtype hierarchies requiring discrimination.
- The PADR references `{Project}` context which appears to be a separate/prior project from which Praecepta was derived. The pattern may not yet be needed in the current domain.

**Severity:** Low (currently) -- No aggregate hierarchy currently requires type discrimination. The pattern is documented for future use but not yet needed.

**Improvement Opportunities:**
- When an aggregate hierarchy with subtypes is introduced (e.g., different agent types), implement the ClassVar pattern per PADR-111 and add it to BaseAggregate or a dedicated mixin.
- Consider proactively adding a `TYPE_DISCRIMINATOR: ClassVar[str] = ""` to BaseAggregate to establish the convention even if unused.

---

### 12. `__all__` Exports -- Maturity: 4 (Managed)

**Findings:**

- The main `__init__.py` has a comprehensive `__all__` list with 38 exports, alphabetically sorted.
  - `packages/foundation-domain/src/praecepta/foundation/domain/__init__.py:54-93`
- All imports at the top of `__init__.py` match the `__all__` entries. Every public symbol is both imported and exported.
  - `packages/foundation-domain/src/praecepta/foundation/domain/__init__.py:8-52`
- Sub-module `exceptions.py` has its own `__all__` with 9 exception classes.
  - `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:20-30`
- Sub-module `ports/__init__.py` has its own `__all__` with 2 port types.
  - `packages/foundation-domain/src/praecepta/foundation/domain/ports/__init__.py:10`
- Not all sub-modules have explicit `__all__` (e.g., `identifiers.py`, `tenant_value_objects.py`, `user_value_objects.py`, `agent_value_objects.py`, `config_value_objects.py`, `config_defaults.py`, `policy_types.py`, `principal.py`, `aggregates.py`, `events.py`). These rely on the top-level `__init__.py` to curate the public API.
- `Principal` is exported from the package but it is defined in `principal.py` which has no `__all__`.
  - `packages/foundation-domain/src/praecepta/foundation/domain/__init__.py:41`

**Severity:** Low -- The top-level `__all__` is the primary public API surface and it is well-maintained. Sub-module `__all__` lists are nice-to-have for direct imports.

**Improvement Opportunities:**
- Add `__all__` to each sub-module for completeness and to support static analysis tools that use per-module `__all__`.

---

### 13. Test Coverage -- Maturity: 4 (Managed)

**Findings:**

- 178 tests across 8 test files, all passing in 1.07 seconds.
- Test files cover all major components:
  - `test_aggregates.py`: 7 tests -- BaseAggregate creation, versioning, events, inheritance. (`packages/foundation-domain/tests/test_aggregates.py:1-60`)
  - `test_events.py`: 20 tests -- tenant_id validation (valid/invalid), get_topic(), to_dict() serialization, immutability. (`packages/foundation-domain/tests/test_events.py:1-153`)
  - `test_exceptions.py`: 38 tests -- all 9 exception types with error_code, message format, context, inheritance. (`packages/foundation-domain/tests/test_exceptions.py:1-222`)
  - `test_identifiers.py`: 24 tests -- TenantId valid/invalid, UserId wrapping, immutability, equality. (`packages/foundation-domain/tests/test_identifiers.py:1-122`)
  - `test_value_objects.py`: 51 tests -- TenantSlug, TenantName, TenantStatus, OidcSub, Email, DisplayName, AgentStatus, AgentTypeId, APIKeyMetadata. (`packages/foundation-domain/tests/test_value_objects.py:1-303`)
  - `test_config_value_objects.py`: 20 tests -- all config value types, discriminated union deserialization, ConfigKey extensibility. (`packages/foundation-domain/tests/test_config_value_objects.py:1-171`)
  - `test_ports.py`: 9 tests -- protocol conformance for both ports with fake implementations. (`packages/foundation-domain/tests/test_ports.py:1-113`)
  - `test_principal.py`: 9 tests -- construction, immutability, equality. (`packages/foundation-domain/tests/test_principal.py:1-77`)
- All tests are marked `@pytest.mark.unit`.
- Edge cases well-covered: boundary values (min/max lengths), invalid formats (uppercase, special chars, leading/trailing hyphens), immutability enforcement, enum value checks.
- Tests for `config_value_objects.py` do not test the discriminated union via the actual `ConfigValue` type alias (they construct the TypeAdapter inline instead).
  - `packages/foundation-domain/tests/test_config_value_objects.py:142-164`

**Gaps identified:**
- No test for `BaseEvent.__post_init__` behavior when used with eventsourcing library's @event decorator (inner event classes). Tests only cover standalone BaseEvent subclasses.
- No test for `SYSTEM_DEFAULTS` dictionary or its interaction with config values.
- No test for `PolicyType` extensibility (ConfigKey extensibility is tested at line 28-35).
- No negative test for `TenantId` length limits (no max length enforcement exists, so no test needed -- but the inconsistency with TenantSlug/BaseEvent is untested).
- No test for `APIKeyMetadata` equality or hashing behavior (only construction and immutability tested).
- No integration-style test verifying that BaseAggregate subclasses work end-to-end with the eventsourcing library's Application class and event store.

**Severity:** Low -- Coverage is strong for unit tests. The main gaps are at the integration boundary with the eventsourcing library.

---

## Additional Observations

### Framework Dependencies at Layer 0

The foundation-domain package has two runtime dependencies declared in `pyproject.toml:10-12`:
- `eventsourcing>=9.5` -- Core to the aggregate and event base classes. This is unavoidable for the event sourcing pattern.
- `pydantic>=2.0` -- Used in `config_value_objects.py` (ConfigValue models) and `ports/llm_service.py` (BaseModel bound on TypeVar).

While the CLAUDE.md exclusion list does not mention Pydantic, its presence at Layer 0 means all downstream packages transitively depend on Pydantic. This is pragmatic (Pydantic is used pervasively for validation) but worth noting for architectural purity.

### Validation Pattern Inconsistency

Three separate implementations of tenant_id/slug validation exist with subtly different rules:

| Component | Pattern | Min Length | Max Length | Location |
|-----------|---------|-----------|-----------|----------|
| TenantId | `^[a-z0-9]+(?:-[a-z0-9]+)*$` | 1 | unlimited | `identifiers.py:47` |
| TenantSlug | `^[a-z0-9][a-z0-9-]*[a-z0-9]$` | 2 | 63 | `tenant_value_objects.py:46` |
| BaseEvent.tenant_id | `^[a-z0-9][a-z0-9-]*[a-z0-9]$` | 2 | 63 | `events.py:126` |

TenantId is the outlier -- it allows single-character values and has no max length. This should be harmonized.

### Documentation Quality

The foundation package has exceptionally thorough docstrings. Every class and method includes:
- Description of purpose
- Attribute documentation
- Args/Returns/Raises sections
- Usage examples (often with doctests)
- Cross-references to related components and PADRs

This is a significant strength and should be maintained as the codebase evolves.

### Consumer Adoption

All three domain aggregates (Tenant, User, Agent) successfully use foundation primitives:
- `BaseAggregate` as base class
- Value objects (TenantSlug, TenantName, OidcSub, Email, DisplayName, AgentTypeId) for validation
- Exceptions (InvalidStateTransitionError, ValidationError) for error handling
- StrEnum types (TenantStatus, AgentStatus) for lifecycle states

This validates that the foundation primitives are usable and well-designed for their intended purpose.

### Missing Primitives

Compared to a full DDD foundation, the following primitives are absent:
- **Repository port/protocol** -- No base repository interface (each domain defines its own)
- **Unit of Work** -- Handled by the eventsourcing library implicitly
- **Domain Service** base -- Follows PADR-108 protocol pattern, no base needed
- **Specification pattern** -- Not implemented
- **Domain Event publisher** -- Handled by eventsourcing library's notification log
- **ValidationResult** -- Described in PADR-113 but not implemented

---

## Risk Summary

| Risk | Severity | Likelihood | Impact |
|------|----------|------------|--------|
| TenantId/TenantSlug/BaseEvent validation inconsistency | Medium | High | Data integrity bugs at boundaries |
| BaseEvent metadata not present on @event-generated classes | Medium | Medium | Missing correlation/causation tracking on aggregate events |
| No enforcement of tenant_id on BaseAggregate | Medium | Low | Possible aggregates without tenant isolation |
| Config value constraint metadata not enforced | Medium | Medium | Invalid config values stored silently |
| PADR-113 ValidationResult not implemented | Low | Low | Manual error handling instead of structured results |
