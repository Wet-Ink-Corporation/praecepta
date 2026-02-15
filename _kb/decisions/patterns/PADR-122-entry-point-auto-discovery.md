# PADR-122: Entry-Point Auto-Discovery

**Status:** Accepted
**Date:** 2026-02-14
**Deciders:** Architecture Team
**Categories:** Pattern, Application Composition, Convention over Configuration

---

## Context

In the source project, the `create_app()` factory manually wires every router, middleware, error handler, and lifespan hook:

```python
# Manual wiring in main.py
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(tenant_router)
app.add_middleware(TenantStateMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AuthMiddleware, jwks_provider=..., issuer=...)
register_exception_handlers(app)
```

As praecepta extracts these capabilities into independent, composable packages, this manual approach breaks down:

- Consumer apps must know every package's router, middleware class, and initialization order
- Adding a package requires editing the composition root — violating open/closed principle
- Testing requires reproducing the full wiring; no way to activate a package in isolation
- The "install and use" promise of composable packages is defeated by manual wiring boilerplate

The question was: **How should packages declare their contributions so that installing a package is sufficient to activate it?**

---

## Decision

**We will use Python's standard entry points mechanism (PEP 621 / `importlib.metadata`) for package auto-discovery.** Each package declares what it contributes in its `pyproject.toml`. The `create_app()` factory discovers and wires everything automatically.

### Entry Point Groups

| Group | Value Type | Consumer |
|-------|-----------|----------|
| `praecepta.routers` | `FastAPI APIRouter` | `infra-fastapi` |
| `praecepta.middleware` | `MiddlewareContribution` | `infra-fastapi` |
| `praecepta.error_handlers` | `ErrorHandlerContribution` or `Callable[[FastAPI], None]` | `infra-fastapi` |
| `praecepta.lifespan` | `LifespanContribution` or async context manager factory | `infra-fastapi` |
| `praecepta.applications` | `eventsourcing.Application` subclass | `infra-eventsourcing` |
| `praecepta.projections` | `BaseProjection` subclass | `infra-eventsourcing` |
| `praecepta.subscriptions` | `Callable[[], None]` (registration function) | Integration packages |

### Package Declaration

```toml
# praecepta-domain-tenancy/pyproject.toml
[project.entry-points."praecepta.routers"]
tenancy = "praecepta.domain.tenancy.api:router"

[project.entry-points."praecepta.applications"]
tenancy = "praecepta.domain.tenancy.application:TenantApplication"
```

### Discovery Utility

A generic `discover()` function in `foundation-application` wraps `importlib.metadata.entry_points()` with logging, error handling, and exclusion filtering:

```python
from praecepta.foundation.application import discover

contributions = discover("praecepta.routers", exclude_names=frozenset({"debug"}))
for contrib in contributions:
    app.include_router(contrib.value)
```

### Contribution Dataclasses

Framework-agnostic dataclasses in `foundation-application` define the contract:

```python
@dataclass(frozen=True, slots=True)
class MiddlewareContribution:
    middleware_class: type[Any]
    priority: int = 500       # 0=outermost, 900=innermost
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class LifespanContribution:
    hook: Any                  # (app) -> AsyncContextManager[None]
    priority: int = 500        # Lower starts first, shuts down last
```

### Middleware Priority Bands

| Band | Range | Purpose | Examples |
|------|-------|---------|----------|
| Outermost | 0–99 | Request identity, tracing | RequestId, TraceContext |
| Security | 100–199 | Authentication | APIKeyAuth, JWTAuth |
| Context | 200–299 | Request context population | RequestContext, TenantState |
| Policy | 300–399 | Enforcement, rate limiting | CORS, ResourceLimits |
| Default | 500 | Unspecified priority | — |

### Consumer App

```python
from praecepta.infra.fastapi import create_app

app = create_app(title="My App")
# All installed praecepta packages auto-register. Zero manual wiring.
```

---

## Consequences

### Positive

- **Convention over configuration:** Install a package, it activates — no manual wiring
- **Open/closed:** New packages don't require editing the composition root
- **Standard mechanism:** PEP 621 entry points are used by pytest, Flask, OpenTelemetry — well-understood pattern
- **Testable:** `exclude_groups` / `exclude_names` isolate tests from unwanted discovery
- **Composable:** Consumer apps choose which packages to install; framework adapts automatically
- **Type-safe:** Contribution dataclasses enforce structure; consuming code validates at the call site

### Negative

- **Implicit wiring:** Harder to see "what's registered" by reading code alone (mitigated by startup logging)
- **Priority collisions:** Two packages with same middleware priority have undefined relative order (mitigated by non-overlapping band conventions)
- **Development mode dependency:** Entry points require package installation; `uv sync` must run after `pyproject.toml` changes

### Mitigations

| Risk | Mitigation |
|------|------------|
| Hidden registrations | `create_app()` logs every discovered contribution at INFO level |
| Priority conflicts | Documented band conventions; linter check possible in future |
| Missing `uv sync` | CI runs `uv sync --dev` before tests; documented in CLAUDE.md |

---

## Alternatives Considered

### Alternative 1: Manual Wiring (Status Quo)

```python
app.include_router(tenancy_router)
app.include_router(identity_router)
app.add_middleware(AuthMiddleware, ...)
```

**Rejected because:** Doesn't scale with composable packages. Every consumer must know every package's internals. Adding a package = editing `main.py`.

### Alternative 2: Decorator-Based Registration

```python
@register_router(prefix="/api/v1/tenants")
router = APIRouter()
```

**Rejected because:** Requires import-time side effects. Module must be imported for registration to happen, creating circular dependency risks and making the registration order dependent on import order.

### Alternative 3: Django-Style `INSTALLED_APPS`

```python
create_app(installed=["praecepta.domain.tenancy", "praecepta.infra.auth"])
```

**Rejected because:** Explicit configuration defeats convention-over-configuration. Consumer must maintain a list that duplicates what's already in `pyproject.toml` dependencies. Doesn't leverage Python packaging metadata.

---

## Related

- [PADR-110: Application Lifecycle](PADR-110-application-lifecycle.md) — Singleton creation via `Depends()`; `create_app()` replaces manual `app.state` wiring
- [PADR-103: Error Handling](PADR-103-error-handling.md) — Error handlers now auto-discovered via `praecepta.error_handlers` group
- [PADR-120: Multi-Auth Middleware Sequencing](PADR-120-multi-auth-middleware-sequencing.md) — Middleware ordering now expressed via priority bands
- [ref-app-factory.md](../../domains/api-framework/references/ref-app-factory.md) — Detailed API reference

---

## Key Files

- `packages/foundation-application/src/praecepta/foundation/application/discovery.py` — `discover()` utility
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py` — Contribution dataclasses
- `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py` — `create_app()` factory
- `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py` — `AppSettings`, `CORSSettings`
- `packages/infra-fastapi/src/praecepta/infra/fastapi/lifespan.py` — Lifespan composition
