# App Factory & Auto-Discovery Reference

## Overview

`create_app()` is the composition root for praecepta applications. It discovers contributions from installed packages via Python entry points (`importlib.metadata`) and wires them into a FastAPI application. Installing a praecepta package is sufficient to activate it — zero manual wiring required.

See [PADR-122](../../../decisions/patterns/PADR-122-entry-point-auto-discovery.md) for the design rationale.

---

## create_app() API

```python
from praecepta.infra.fastapi import create_app, AppSettings

app = create_app(
    settings=AppSettings(title="My App"),
    extra_routers=[custom_router],           # Manual additions
    extra_middleware=[my_middleware],
    extra_lifespan_hooks=[my_hook],
    extra_error_handlers=[my_handler],
    exclude_groups=frozenset({"praecepta.middleware"}),  # Skip groups
    exclude_names=frozenset({"debug_router"}),           # Skip specific entries
)
```

**Parameters:**

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `settings` | `AppSettings \| None` | From env | FastAPI + CORS + discovery config |
| `extra_routers` | `list[APIRouter] \| None` | `None` | Additional routers beyond discovered |
| `extra_middleware` | `list[MiddlewareContribution] \| None` | `None` | Additional middleware |
| `extra_lifespan_hooks` | `list[LifespanContribution] \| None` | `None` | Additional lifespan hooks |
| `extra_error_handlers` | `list[ErrorHandlerContribution] \| None` | `None` | Additional error handlers |
| `exclude_groups` | `frozenset[str] \| None` | `None` | Entry point groups to skip |
| `exclude_names` | `frozenset[str] \| None` | `None` | Entry point names to skip |

---

## Discovery Sequence

`create_app()` wires contributions in this order:

1. **Lifespan hooks** discovered → composed via `AsyncExitStack` (priority-sorted)
2. **FastAPI instance** created with composed lifespan
3. **CORS middleware** always added (from `AppSettings.cors`)
4. **Middleware** discovered → sorted by priority ascending → added in reverse (LIFO)
5. **Error handlers** discovered → registered on app
6. **Routers** discovered → included on app

---

## Entry Point Groups

| Group | Value Type | Consumer Package |
|-------|-----------|-----------------|
| `praecepta.routers` | `FastAPI APIRouter` | `infra-fastapi` |
| `praecepta.middleware` | `MiddlewareContribution` | `infra-fastapi` |
| `praecepta.error_handlers` | `ErrorHandlerContribution` or `Callable[[FastAPI], None]` | `infra-fastapi` |
| `praecepta.lifespan` | `LifespanContribution` or async CM factory | `infra-fastapi` |
| `praecepta.applications` | `eventsourcing.Application` subclass | `infra-eventsourcing` |
| `praecepta.projections` | `BaseProjection` subclass | `infra-eventsourcing` |
| `praecepta.subscriptions` | `Callable[[], None]` | Integration packages |

---

## Contribution Types

All defined in `praecepta.foundation.application.contributions`:

```python
@dataclass(frozen=True, slots=True)
class MiddlewareContribution:
    middleware_class: type[Any]       # ASGI middleware class
    priority: int = 500              # Lower = outermost
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ErrorHandlerContribution:
    exception_class: type[BaseException]
    handler: Any                      # (Request, Exception) -> Response

@dataclass(frozen=True, slots=True)
class LifespanContribution:
    hook: Any                         # (app) -> AsyncContextManager[None]
    priority: int = 500              # Lower starts first, shuts down last
```

---

## Middleware Priority Bands

| Band | Range | Purpose | Examples |
|------|-------|---------|----------|
| Outermost | 0–99 | Request identity, tracing | `RequestIdMiddleware`, `TraceContextMiddleware` |
| Security | 100–199 | Authentication | `APIKeyAuthMiddleware`, `AuthMiddleware` |
| Context | 200–299 | Request context population | `RequestContextMiddleware`, `TenantStateMiddleware` |
| Policy | 300–399 | Enforcement, rate limiting | CORS (built-in), resource limits |
| Default | 500 | Unspecified | — |

Middleware with lower priority numbers execute first (outermost in the ASGI stack). CORS is always added by `create_app()` directly from settings, not via entry points.

---

## Declaring Entry Points

In a package's `pyproject.toml`:

```toml
[project.entry-points."praecepta.routers"]
tenancy = "praecepta.domain.tenancy.api:router"

[project.entry-points."praecepta.middleware"]
tenant_state = "praecepta.domain.tenancy.infrastructure.middleware:contribution"

[project.entry-points."praecepta.lifespan"]
observability = "praecepta.infra.observability:lifespan_hook"
```

The entry point value must be a dotted path to the Python object. For middleware and lifespan, the loaded object should be a `MiddlewareContribution` or `LifespanContribution` instance (module-level constant).

**Example middleware module:**

```python
# praecepta/infra/auth/middleware.py
from praecepta.foundation.application import MiddlewareContribution

contribution = MiddlewareContribution(
    middleware_class=AuthMiddleware,
    priority=150,
    kwargs={"issuer": "..."},
)
```

---

## Discovery Utility

The generic `discover()` function (in `praecepta.foundation.application`) is available to any package:

```python
from praecepta.foundation.application import discover, DiscoveredContribution

results: list[DiscoveredContribution] = discover(
    "praecepta.routers",
    exclude_names=frozenset({"debug"}),
)

for contrib in results:
    print(contrib.name, contrib.group, contrib.value)
```

Entry points that fail to load are logged and skipped (fail-soft). Discovery logs every loaded contribution at DEBUG and a summary at INFO.

---

## Testing

Suppress discovery in tests with `exclude_groups`:

```python
app = create_app(
    settings=AppSettings(),
    exclude_groups=frozenset({
        "praecepta.routers",
        "praecepta.middleware",
        "praecepta.error_handlers",
        "praecepta.lifespan",
    }),
    extra_routers=[test_router],  # Only your test-specific contributions
)
```

Or exclude specific entry points by name:

```python
app = create_app(exclude_names=frozenset({"auth", "tenant_state"}))
```

---

## See Also

- [PADR-122: Entry-Point Auto-Discovery](../../../decisions/patterns/PADR-122-entry-point-auto-discovery.md) — Design decision
- [PADR-110: Application Lifecycle](../../../decisions/patterns/PADR-110-application-lifecycle.md) — Depends singleton pattern
- [PADR-103: Error Handling](../../../decisions/patterns/PADR-103-error-handling.md) — Error handler conventions
- [PADR-120: Multi-Auth Middleware Sequencing](../../../decisions/patterns/PADR-120-multi-auth-middleware-sequencing.md) — Middleware ordering rationale
