<!-- Derived from {Project} PADR-119-separate-user-application -->
# PADR-119: Separate UserApplication Per Aggregate Type

**Status:** Proposed
**Date:** 2026-02-08
**Deciders:** Architecture Team
**Categories:** Pattern, Event-Store-CQRS
**Proposed by:** docs-enricher (feature F-102-003)

---

## Context

The shared bounded context now has two event-sourced aggregates:

1. **Tenant** — manages tenant lifecycle (provisioning, activation, suspension, decommissioning)
2. **User** — manages user identity and profile (JIT provisioning, display_name, preferences)

Per PADR-110 (Application Lifecycle), each aggregate requires an eventsourcing `Application` instance to manage its event store persistence. The question is: should both aggregates share one `SharedApplication`, or should each have its own (`TenantApplication`, `UserApplication`)?

### Existing Pattern

Before F-102-003, the shared context had only `TenantApplication`:

```python
# src/{Project}/shared/application/__init__.py
class TenantApplication(Application[UUID]):
    def __init__(self) -> None:
        super().__init__(env=get_eventsourcing_env())
```

The `Application` class from the eventsourcing library uses the aggregate's `__name__` to route events to the correct aggregate class. All `Tenant.*` events are routed to `Tenant.__init__` and `Tenant.trigger_event()`.

### Options Considered

#### Option 1: Single SharedApplication (DRY)

```python
class SharedApplication(Application[UUID]):
    """Single application managing both Tenant and User aggregates."""
    pass

# Usage
app.state.shared_app = SharedApplication()
```

**Pro:** One application instance, less boilerplate, simpler lifespan management

**Con:**
- Violates Single Responsibility Principle (one Application manages two unrelated aggregate types)
- Event routing relies on global aggregate class registry (PADR-112: Module-Level Registry), making it unclear which aggregates this Application manages
- Couples Tenant and User lifecycle (decommissioning one aggregate type affects the other)
- Makes testing harder (must import both Tenant and User to initialize the Application)

#### Option 2: Separate TenantApplication + UserApplication (SRP)

```python
class TenantApplication(Application[UUID]):
    """Manages Tenant aggregates only."""
    pass

class UserApplication(Application[UUID]):
    """Manages User aggregates only."""
    pass

# Usage
app.state.tenant_app = TenantApplication()
app.state.user_app = UserApplication()
```

**Pro:**
- Clear separation of concerns (each Application manages one aggregate type)
- Easier testing (test User without importing Tenant)
- Explicit ownership (TenantApplication → Tenant, UserApplication → User)
- Follows existing convention from domain context (`CoreApplication` manages only `Order`)

**Con:**
- Two application instances instead of one (minimal overhead, <1MB RAM each)
- Slight duplication (two lifespan initialization blocks)

---

## Decision

We use **separate Application classes per aggregate type** (Option 2):

```python
# src/{Project}/shared/application/__init__.py
class TenantApplication(Application[UUID]):
    """Manages Tenant aggregate lifecycle."""
    pass

# src/{Project}/shared/application/user_app.py
class UserApplication(Application[UUID]):
    """Manages User aggregate lifecycle."""
    pass
```

Both are initialized during FastAPI lifespan:

```python
# src/{Project}/main.py
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.tenant_app = TenantApplication()
    app.state.user_app = UserApplication()
    # ... registry tables, provisioning service, etc. ...
    yield
```

### Rationale

1. **Single Responsibility** — Each Application manages exactly one aggregate type, matching the pattern from Memory and Lifecycle contexts
2. **Clear ownership** — `TenantApplication.save(tenant)` is unambiguous; `SharedApplication.save(tenant)` is not
3. **Testability** — Unit tests for User do not require Tenant imports
4. **Future-proof** — If we add a third aggregate (e.g., `Organization`), we add `OrganizationApplication`, not a mega-SharedApplication
5. **Consistency** — Matches existing pattern: `CoreApplication` (domain context), `ProcessingApplication` (Processing context), `CurationApplication` (Lifecycle context)

The overhead of two Application instances is negligible (~1MB RAM each). The eventsourcing library is designed for this pattern (multiple Applications in one process).

---

## Consequences

### Positive

- **Clear ownership** — Each aggregate has its own Application (no ambiguity)
- **SRP compliance** — Each Application has one reason to change (its aggregate evolves)
- **Easier testing** — Test UserApplication without TenantApplication
- **Consistent pattern** — Follows Memory, Processing, Lifecycle contexts

### Negative

- **Two singletons** — `app.state.tenant_app` and `app.state.user_app` instead of one
- **Slight duplication** — Two lifespan initialization blocks (acceptable)
- **More imports** — Handlers must import the correct Application (mitigated by dependency injection)

### Neutral

- **Event store table isolation** — Each aggregate's events are stored in separate tables (`tenant_events`, `user_events`), managed by eventsourcing library
- **Connection pool sharing** — Both Applications share the same PostgreSQL connection pool (configured via environment variable)

---

## Implementation Notes

- **Feature:** F-102-003 User Provisioning (S-102-003-001)
- **Key files:**
  - `src/{Project}/shared/application/__init__.py` — TenantApplication
  - `src/{Project}/shared/application/user_app.py` — UserApplication
  - `src/{Project}/main.py` — Lifespan initialization (lines 118-126)
- **Decision:** [DD-2: Separate UserApplication Per Aggregate Type](../../_bklg/E-102-authentication-identity/F-102-003-user-provisioning/feature-architecture/decisions/DD-2-separate-userapplication-per-aggregate-type.md)

---

## Related

- [PADR-110: Application Lifecycle](PADR-110-application-lifecycle.md) — Lifespan-managed singletons
- [PADR-112: Module-Level Registry](PADR-112-module-level-registry.md) — Event routing to aggregate classes
- [con-domain-model.md](../../domains/ddd-patterns/references/con-domain-model.md) — Aggregate design principles
