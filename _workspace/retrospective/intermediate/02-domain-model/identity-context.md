# Domain Model Audit: Identity Bounded Context & Integration

**Collector ID:** 2C
**Dimension:** 02-domain-model
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6

---

## Checklist Item 1: User Aggregate

**Maturity: 4 (Managed)**

### Findings

The User aggregate is a well-structured DDD aggregate with proper lifecycle management and event emission.

- **Aggregate inheritance:** `User` extends `BaseAggregate` which extends `eventsourcing.domain.Aggregate`, following the framework's prescribed pattern.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:17`

- **Creation event:** The `@event("Provisioned")` decorator on `__init__` correctly records a `User.Provisioned` domain event on creation.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:30-31`

- **Value object validation:** OIDC sub and email are validated through dedicated value objects (`OidcSub`, `Email`) from the foundation layer, enforcing invariants at construction time.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:51-52`

- **Display name derivation:** The aggregate correctly implements a fallback chain (name -> email prefix -> "User") for display_name derivation. This logic is duplicated in the projection handler, which is a maintenance risk.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:60-65`
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:66-73`

- **Immutable vs mutable separation:** The docstring and code clearly distinguish immutable properties (oidc_sub, email, tenant_id) from mutable ones (display_name, preferences). However, immutability is only enforced by convention -- there is no programmatic enforcement preventing direct attribute mutation.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:18-26`

- **Command methods:** `request_update_display_name` and `request_update_preferences` follow the `request_*` naming convention and delegate to private `@event` mutators.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:72-82`
  `packages/domain-identity/src/praecepta/domain/identity/user.py:84-90`

- **Display name validation on update:** The `DisplayName` value object is used in `request_update_display_name`, providing consistent validation. However, the initial `name` parameter during creation is NOT validated through `DisplayName` -- it is assigned directly if provided.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:60-61` (raw assignment)
  `packages/domain-identity/src/praecepta/domain/identity/user.py:81` (validated via `DisplayName`)

- **Missing lifecycle events:** There is no User deactivation/deletion event. The aggregate has no terminal state in its lifecycle -- users can only be created and have their profile updated. This may be intentional for OIDC-provisioned users but limits the domain model.

**Severity:** Low (display_name derivation duplication), Low (no immutability enforcement)
**Confidence:** High

---

## Checklist Item 2: Agent Aggregate

**Maturity: 4 (Managed)**

### Findings

The Agent aggregate implements a well-defined state machine with comprehensive API key lifecycle management.

- **State machine:** The docstring at the module level documents the state machine: `(creation) -> ACTIVE`, `ACTIVE <-> SUSPENDED`. Transitions are properly enforced by guard clauses.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:1-6`

- **Value object validation:** `AgentTypeId` and `DisplayName` value objects validate creation inputs. `AgentStatus` enum is used for lifecycle states.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:55-56`

- **Idempotent state transitions:** Both `request_suspend` and `request_reactivate` are idempotent -- calling suspend on an already-suspended agent is a no-op, and vice versa. This is excellent for event-sourced systems.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:79-80` (suspend idempotency)
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:96-97` (reactivate idempotency)

- **Domain exceptions:** `InvalidStateTransitionError` is raised for invalid transitions, and `ValidationError` for API key operations on non-active agents. Good use of distinct exception types.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:82-84`
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:122-125`

- **API key lifecycle:** The aggregate tracks active and revoked keys. `request_issue_api_key` adds a key, `request_rotate_api_key` atomically revokes the old and issues a new key in a single event.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:105-126`
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:128-154`

- **Nondeterministic timestamp in event mutator:** The `_apply_api_key_rotated` mutator calls `datetime.now(UTC).isoformat()` for the new key's `created_at`. This is problematic for event sourcing because event replay would produce different timestamps each time the aggregate is reconstituted. The timestamp should come from the command method parameter instead.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:196`

- **Missing explicit revoke command:** There is no `request_revoke_api_key` command for individual key revocation (only rotation). PADR-121 discusses this trade-off. Suspending an agent does not invalidate keys (acknowledged trade-off in PADR-121).

- **active_keys as list of dicts:** The `active_keys` field uses `list[dict[str, str]]` which is a weakly-typed structure. A dedicated value object (e.g., `APIKeyEntry`) would provide better type safety and encapsulation.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:62`

**Severity:** Medium (nondeterministic timestamp in event mutator), Low (no explicit revoke command), Low (weak typing for active_keys)
**Confidence:** High

---

## Checklist Item 3: UserApplication

**Maturity: 4 (Managed)**

### Findings

The UserApplication follows PADR-119's separate application per aggregate type pattern.

- **Separate application:** `UserApplication` extends `Application[UUID]` as a dedicated service for User aggregates, matching PADR-119's decision.
  `packages/domain-identity/src/praecepta/domain/identity/user_app.py:17`

- **Snapshotting configured:** Snapshots are taken every 50 events for the User aggregate, which is a reasonable interval for this aggregate's expected event frequency.
  `packages/domain-identity/src/praecepta/domain/identity/user_app.py:27`

- **Entry point registered:** The application is registered as an entry point under `praecepta.applications` for auto-discovery per PADR-122.
  `packages/domain-identity/pyproject.toml:23`

- **Minimal implementation:** The class is intentionally minimal (only snapshotting configuration), delegating all persistence logic to the eventsourcing library. This is the correct pattern.

- **No custom command methods:** The application service does not add any domain-specific command orchestration methods (e.g., `provision_user`). The provisioning flow is handled separately by `UserProvisioningService`, which is a clean separation.

**Severity:** None
**Confidence:** High

---

## Checklist Item 4: AgentApplication

**Maturity: 4 (Managed)**

### Findings

The AgentApplication mirrors UserApplication's pattern, consistent with PADR-119.

- **Separate application:** `AgentApplication` extends `Application[UUID]` as a dedicated service for Agent aggregates.
  `packages/domain-identity/src/praecepta/domain/identity/agent_app.py:17`

- **Snapshotting configured:** Snapshots every 50 events for Agent aggregates.
  `packages/domain-identity/src/praecepta/domain/identity/agent_app.py:27`

- **Entry point registered:** Registered under `praecepta.applications` as `identity_agent`.
  `packages/domain-identity/pyproject.toml:24`

- **Missing orchestration:** There is no service-level orchestration for agent registration workflows (e.g., generate key_id + key_hash, then call `request_issue_api_key`). The hash generation and key_id creation would need to happen at the API layer or in a separate service. This is not necessarily a deficiency -- it depends on the intended architecture.

**Severity:** None
**Confidence:** High

---

## Checklist Item 5: JIT Provisioning

**Maturity: 4 (Managed)**

### Findings

The `UserProvisioningService` implements the JIT user provisioning flow described in PADR-118 with proper race condition handling.

- **Fast-path/slow-path:** The service implements the two-path strategy: fast-path registry lookup (line 81-93), slow-path reserve-create-confirm (line 96-137).
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:81-93`
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:96-137`

- **Race condition handling:** On `ConflictError` during reserve, the service retries lookup up to 5 times with exponential backoff (50ms increments). This handles the case where two concurrent requests try to provision the same user.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:104-114`

- **Compensating action:** If aggregate creation or save fails after reservation, the reservation is released. This is a proper saga compensation pattern.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:139-145`

- **Cross-tenant protection:** The fast-path checks that an existing user's tenant_id matches the requested tenant_id, raising `ConflictError` if mismatched.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:84-88`

- **Blocking sleep in async context:** The `time.sleep()` call in the race condition retry loop is a blocking call that would block the event loop if called from an async context. Per PADR-118, provisioning is called from middleware which could be async. The service should use an async-aware retry mechanism or be explicitly documented as sync-only.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:113`

- **Structured logging:** Appropriate logging at debug, warning, info, and exception levels throughout the flow.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:89-91, 105-108, 129-136, 141-144`

**Severity:** Medium (blocking sleep in potentially async context)
**Confidence:** High

---

## Checklist Item 6: OIDC Sub Registry

**Maturity: 4 (Managed)**

### Findings

The `OidcSubRegistry` implements a three-phase reservation pattern for idempotent user provisioning.

- **Three-phase lifecycle:** reserve -> confirm -> release (compensating action). The SQL statements are clearly separated and well-documented.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:45-64`

- **Uniqueness enforcement:** The `oidc_sub` column is the PRIMARY KEY, providing database-level uniqueness. The `reserve()` method catches `UniqueViolation`/`IntegrityError` and re-raises as domain `ConflictError`.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:31-38`
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:119-123`

- **Release safety:** The `release()` SQL only deletes rows where `confirmed = FALSE`, preventing accidental deletion of confirmed registrations.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:57-59`

- **Lookup fast-path:** The `lookup()` method only returns `user_id` for confirmed entries, correctly filtering out pending reservations.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:61-64`

- **Table creation:** `ensure_table_exists()` is a classmethod that handles both PostgreSQL (creates table) and in-memory (no-op) environments gracefully.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:81-100`

- **Stale reservation cleanup:** The table has an index on `reserved_at WHERE confirmed = FALSE` to support cleanup of stale reservations, but no cleanup logic is implemented. Stale reservations (from crashed processes) would accumulate.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/oidc_sub_registry.py:40-42`

- **Direct SQL with psycopg placeholders:** Uses `%s` style placeholders (psycopg format), tightly coupling to the PostgreSQL driver. This is acceptable given the PostgreSQL-only target.

**Severity:** Low (no stale reservation cleanup)
**Confidence:** High

---

## Checklist Item 7: User Profile Projection

**Maturity: 4 (Managed)**

### Findings

The `UserProfileProjection` correctly materializes user events into the read model.

- **Topic subscription:** Subscribes to all three User event types: Provisioned, ProfileUpdated, PreferencesUpdated.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:34-38`

- **Event routing:** Uses `singledispatchmethod` with class name-based routing. Events are dispatched correctly to handler methods.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:44-57`

- **Display name derivation duplication:** The `_handle_provisioned` method replicates the User aggregate's display_name fallback logic (name -> email prefix -> "User"). This is a maintenance risk -- if the aggregate logic changes, the projection must be updated in sync.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:66-73`

- **UPSERT pattern:** The Provisioned event handler uses `upsert_full` for idempotent replay, which is the correct CQRS pattern.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:75-82`

- **Type ignore comments:** Multiple `# type: ignore[attr-defined]` comments indicate that domain event attribute access is not type-safe. This is an inherent limitation of the eventsourcing library's dynamic event classes.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:77, 80, 88, 95`

- **Unknown event handling:** Unknown events are silently ignored (the `policy` method falls through without raising). This is the correct behavior for projections.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:44-57`

- **Rebuild support:** The `clear_read_model` method delegates to `repository.truncate()`, supporting full projection rebuilds.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/user_profile.py:98-100`

- **Entry point registered:** Registered under `praecepta.projections` as `user_profile`.
  `packages/domain-identity/pyproject.toml:27`

**Severity:** Medium (display_name derivation logic duplication between aggregate and projection)
**Confidence:** High

---

## Checklist Item 8: Agent API Key Projection

**Maturity: 4 (Managed)**

### Findings

The `AgentAPIKeyProjection` implements projection-based authentication per PADR-121.

- **Topic subscription:** Subscribes to `Agent.APIKeyIssued` and `Agent.APIKeyRotated` events.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/agent_api_key.py:32-35`

- **Missing suspension events:** The projection does not subscribe to `Agent.Suspended` or `Agent.Reactivated`. This is an explicitly acknowledged trade-off in PADR-121 (suspending agent does not invalidate keys). However, there is no `agent_status` column in the projection at all.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/agent_api_key.py:32-35`

- **Rotation handling:** The `_handle_rotated` method correctly performs two operations: revoke old key status, then upsert new key. However, these are not in an atomic database transaction -- if the upsert fails after the status update, the read model would be inconsistent.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/agent_api_key.py:64-79`

- **UPSERT for idempotency:** API key issuance uses upsert with `ON CONFLICT (key_id)` for replay safety.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/agent_api_key.py:54-62`

- **Rebuild support:** The `clear_read_model` uses `DELETE FROM` instead of `TRUNCATE TABLE` (used in user profile). This inconsistency should be noted.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/agent_api_key_repository.py:116`
  Compare with `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:122`

- **Entry point registered:** Registered under `praecepta.projections` as `agent_api_key`.
  `packages/domain-identity/pyproject.toml:28`

**Severity:** Low (no atomic transaction in rotation handler), Low (DELETE vs TRUNCATE inconsistency)
**Confidence:** High

---

## Checklist Item 9: User Profile Repository

**Maturity: 4 (Managed)**

### Findings

The `UserProfileRepository` provides a clean separation of sync write and async read methods.

- **Sync/async split:** Write methods (upsert_full, update_display_name, update_preferences) are sync for use by the projection. Read methods (get_by_user_id) are async, wrapping sync implementation with `asyncio.to_thread`.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:52-117` (sync writes)
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:127-135` (async read)

- **DTO pattern:** `UserProfileRow` dataclass provides a typed interface for query results.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:27-36`

- **RLS tenant isolation:** The `ensure_table_exists` method creates RLS policies for tenant isolation using `app.current_tenant` session variable.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:188-204`

- **Indexed lookups:** The table has indices for `oidc_sub + tenant_id` and `tenant_id` for efficient queries.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:182-186`

- **Tenant filtering in reads:** The `get_by_user_id` method requires both `user_id` AND `tenant_id`, providing application-level tenant isolation in addition to RLS.
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:127`

- **Missing `get_by_oidc_sub` method:** There is no async read method to look up a user profile by OIDC sub. This might be needed for middleware or API endpoints that only have the OIDC sub (not user_id).

**Severity:** Low (missing get_by_oidc_sub read method)
**Confidence:** High

---

## Checklist Item 10: Integration Package

**Maturity: 1 (Not Implemented)**

### Findings

The integration package (`praecepta-integration-tenancy-identity`) is essentially a stub with no meaningful implementation.

- **Empty module:** The `__init__.py` contains only a docstring with no imports, classes, or functions.
  `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1`

- **No source files:** The entire package consists of a single `__init__.py` file with one docstring line.

- **No entry points:** The `pyproject.toml` does not register any entry points (no routers, projections, middleware, or lifespan hooks).
  `packages/integration-tenancy-identity/pyproject.toml:1-24`

- **No test files:** There are zero test files in `packages/integration-tenancy-identity/tests/`.

- **Dependencies declared:** The package correctly declares dependencies on both `praecepta-domain-tenancy` and `praecepta-domain-identity`, so the dependency graph is prepared for future integration logic.
  `packages/integration-tenancy-identity/pyproject.toml:11-13`

- **Expected integrations missing:** Per the project description, this package should bridge tenancy and identity contexts. Expected features such as cross-context sagas (e.g., tenant provisioned -> create admin user), event subscriptions, or cross-context queries are entirely absent.

**Severity:** High (entire integration layer is a stub)
**Confidence:** High

---

## Checklist Item 11: Event Coverage

**Maturity: 3 (Defined)**

### Findings

Events cover the core lifecycles but have gaps for completeness.

**User events (3 events):**
| Event | Trigger | Coverage |
|-------|---------|----------|
| `User.Provisioned` | `__init__` | Creation from OIDC claims |
| `User.ProfileUpdated` | `request_update_display_name` | Display name change |
| `User.PreferencesUpdated` | `request_update_preferences` | Preferences change |

- Missing: No deactivation, deletion, email update, or re-provisioning events.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:30, 94, 98`

**Agent events (5 events):**
| Event | Trigger | Coverage |
|-------|---------|----------|
| `Agent.Registered` | `__init__` | Agent creation |
| `Agent.Suspended` | `request_suspend` | ACTIVE -> SUSPENDED |
| `Agent.Reactivated` | `request_reactivate` | SUSPENDED -> ACTIVE |
| `Agent.APIKeyIssued` | `request_issue_api_key` | New key issuance |
| `Agent.APIKeyRotated` | `request_rotate_api_key` | Atomic key rotation |

- Missing: No explicit `Agent.APIKeyRevoked` event (only rotation-based revocation). No `Agent.DisplayNameUpdated` or `Agent.Deregistered` events.
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:37, 158, 162, 166, 177`

- **Event payload adequacy:** Events carry all necessary data for projection rebuilds. The `Provisioned` event carries raw `name` (not derived `display_name`), which is correctly handled by the projection.

**Severity:** Medium (missing lifecycle terminal events for both aggregates), Low (no explicit key revocation event)
**Confidence:** High

---

## Checklist Item 12: Validation & Errors

**Maturity: 4 (Managed)**

### Findings

The identity context uses a well-structured validation and error hierarchy.

- **Value objects for validation:** Foundation-layer value objects (`OidcSub`, `Email`, `DisplayName`, `AgentTypeId`, `AgentStatus`) enforce domain invariants at construction. All raise `ValueError` with descriptive messages.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:51-52`
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:55-56`

- **Domain exception hierarchy:** Three distinct exception types are used appropriately:
  - `ValidationError` (HTTP 422) for input validation failures (e.g., issuing key on non-active agent)
  - `ConflictError` (HTTP 409) for state conflicts (e.g., cross-tenant provisioning)
  - `InvalidStateTransitionError` (HTTP 409, extends ConflictError) for state machine violations
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:82-84, 122-125`
  `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_provisioning.py:85-88`

- **Contextual error messages:** Error messages include relevant context (aggregate ID, current state, expected state).
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:83-84`

- **Inconsistent validation approach:** The `User.__init__` uses `ValueError` from value objects for invalid oidc_sub/email, while `Agent` methods use the domain-specific `ValidationError` and `InvalidStateTransitionError`. The User aggregate should arguably use `ValidationError` for consistency, though `ValueError` from value objects is acceptable at the foundation level.

- **Missing tenant_id validation:** Neither `User.__init__` nor `Agent.__init__` validates the `tenant_id` parameter through a value object. An empty or malformed tenant_id would be accepted.
  `packages/domain-identity/src/praecepta/domain/identity/user.py:57`
  `packages/domain-identity/src/praecepta/domain/identity/agent.py:59`

**Severity:** Low (tenant_id not validated), Low (inconsistent ValueError vs ValidationError)
**Confidence:** High

---

## Checklist Item 13: Test Coverage

**Maturity: 4 (Managed)**

### Findings

The test suite is comprehensive with good coverage of aggregates, projections, provisioning, and edge cases.

**Test files (9 files):**
| File | Focus | Test Count |
|------|-------|------------|
| `test_user.py` | User aggregate creation, profile updates | 14 tests |
| `test_agent.py` | Agent creation, suspension, reactivation, API keys | 12 tests |
| `test_user_app.py` | UserApplication instantiation, save/retrieve | 3 tests |
| `test_agent_app.py` | AgentApplication instantiation, save/retrieve | 3 tests |
| `test_oidc_sub_registry.py` | Reserve, confirm, release, lookup, table creation | 6 tests |
| `test_user_profile_projection.py` | Projection topic subscription, event handling | 6 tests |
| `test_agent_api_key_projection.py` | Projection topic subscription, event handling | 3 tests |
| `test_user_provisioning.py` | Fast-path, slow-path, race conditions, compensation | 4 tests |
| `conftest.py` | Shared fixtures (user, agent) | N/A |

- **All tests marked `@pytest.mark.unit`:** Every test class uses the `unit` marker, consistent with the project's testing strategy.
  `packages/domain-identity/tests/test_user.py:23`

- **Aggregate tests:** Good coverage of creation, event emission, validation (empty oidc_sub, oversized oidc_sub, empty display name), display name derivation chains, and preferences.
  `packages/domain-identity/tests/test_user.py:24-144`
  `packages/domain-identity/tests/test_agent.py:13-234`

- **State machine tests:** Agent suspension idempotency, reactivation idempotency, and transitions are well tested.
  `packages/domain-identity/tests/test_agent.py:70-138`

- **Provisioning tests:** Cover fast-path (existing user), slow-path (new user), cross-tenant conflict, save failure compensation, and race condition retry.
  `packages/domain-identity/tests/test_user_provisioning.py:24-106`

- **Projection tests:** Cover event routing, unknown event handling, and correct repository method calls for both projections.
  `packages/domain-identity/tests/test_user_profile_projection.py:54-113`
  `packages/domain-identity/tests/test_agent_api_key_projection.py:49-88`

- **Missing integration tests:** There are no integration tests (all are unit tests with mocks). No tests verify actual PostgreSQL behavior, RLS policies, or end-to-end provisioning flows.

- **Missing tests for AgentAPIKeyRepository and UserProfileRepository:** The repository classes have no direct unit tests. They are only tested indirectly through projection tests (which mock the repository).

- **No integration package tests:** Zero tests for `praecepta-integration-tenancy-identity` (consistent with the stub implementation).

- **Missing negative tests for Agent.request_reactivate from non-SUSPENDED state:** The test only checks idempotent reactivation on an already-active agent. There is no test for reactivating from a hypothetical future state.

**Severity:** Medium (no integration tests), Medium (no repository tests), Low (no integration package tests)
**Confidence:** High

---

## Summary Statistics

| # | Checklist Item | Maturity | Severity |
|---|---------------|----------|----------|
| 1 | User Aggregate | 4 | Low |
| 2 | Agent Aggregate | 4 | Medium |
| 3 | UserApplication | 4 | None |
| 4 | AgentApplication | 4 | None |
| 5 | JIT Provisioning | 4 | Medium |
| 6 | OIDC Sub Registry | 4 | Low |
| 7 | User Profile Projection | 4 | Medium |
| 8 | Agent API Key Projection | 4 | Low |
| 9 | User Profile Repository | 4 | Low |
| 10 | Integration Package | 1 | High |
| 11 | Event Coverage | 3 | Medium |
| 12 | Validation & Errors | 4 | Low |
| 13 | Test Coverage | 4 | Medium |

**Average Maturity:** 3.7 / 5.0
**Items at Maturity 4+:** 10/13 (77%)
**Items at Maturity 1-2:** 1/13 (8%)

**Highest Severity Issues:**
1. Integration package is a stub (Item 10, High)
2. Nondeterministic timestamp in Agent event mutator (Item 2, Medium)
3. Blocking `time.sleep()` in provisioning retry loop (Item 5, Medium)
4. Display name derivation duplication between aggregate and projection (Item 7, Medium)
5. Missing lifecycle terminal events (Item 11, Medium)
6. No integration tests or repository tests (Item 13, Medium)

---

## Additional Observations

### Architecture Compliance

1. **Layer compliance:** The identity domain package (Layer 2) correctly depends only on foundation (Layer 0) and infra-eventsourcing (Layer 1), following the accepted exception documented in CLAUDE.md.
   `packages/domain-identity/pyproject.toml:11-14`

2. **PEP 420 namespace:** Intermediate namespace directories correctly lack `__init__.py` files. Only the leaf package `praecepta.domain.identity` has an `__init__.py`.

3. **Entry point auto-discovery:** Both applications and both projections are registered as entry points per PADR-122.
   `packages/domain-identity/pyproject.toml:22-28`

### Design Quality

4. **PADR-119 compliance:** The separate `UserApplication` and `AgentApplication` pattern is correctly implemented, with each managing exactly one aggregate type.

5. **PADR-118 compliance:** The JIT provisioning flow (fast-path/slow-path, three-phase reservation, compensating action) matches the decision record closely. The implementation in `UserProvisioningService` is a faithful implementation.

6. **PADR-121 compliance:** The projection-based authentication pattern is implemented for Agent API keys. The `AgentAPIKeyRepository.lookup_by_key_id()` provides the O(1) indexed lookup described in the decision record. The trade-off of not checking agent status during auth is explicitly documented.

7. **SQLAlchemy dependency in domain package:** The `domain-identity` package has a direct dependency on `sqlalchemy>=2.0` in its `pyproject.toml`. This places infrastructure concerns (SQL database access) in a domain-layer package, which is an architectural concern. The repositories and projections that use SQLAlchemy should arguably live in an infra-layer package.
   `packages/domain-identity/pyproject.toml:14`

8. **Missing `ensure_table_exists` on AgentAPIKeyRepository:** Unlike `UserProfileRepository` and `OidcSubRegistry`, the `AgentAPIKeyRepository` class does not have an `ensure_table_exists` classmethod. This means the `agent_api_key_registry` table must be created externally (perhaps via migrations), creating an inconsistency in the self-provisioning pattern.

9. **Projection constructor injection:** Both projections accept their repository via constructor injection, which is a clean dependency inversion pattern. However, the wiring of repository instances to projections is not visible in the identity package -- it must happen in the app factory or lifespan hooks.

10. **`agent_api_key_repository.truncate()` uses DELETE instead of TRUNCATE:** The method is named `truncate()` but executes `DELETE FROM agent_api_key_registry` instead of `TRUNCATE TABLE agent_api_key_registry`. `DELETE` is slower for full table clears and does not reset auto-increment counters (though there are none here). The `UserProfileRepository.truncate()` correctly uses `TRUNCATE TABLE`.
    `packages/domain-identity/src/praecepta/domain/identity/infrastructure/agent_api_key_repository.py:116`
    `packages/domain-identity/src/praecepta/domain/identity/infrastructure/user_profile_repository.py:122`
