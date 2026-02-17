# Entry-Point Discovery

Praecepta uses Python's standard entry points mechanism ([PEP 621](https://peps.python.org/pep-0621/) / `importlib.metadata`) so that installing a package is sufficient to activate it. No manual wiring required.

## How It Works

1. Each package declares what it contributes in its `pyproject.toml`
2. `create_app()` calls `importlib.metadata.entry_points()` to discover contributions
3. Contributions are sorted, validated, and wired into the FastAPI application

```python
from praecepta.infra.fastapi import create_app

app = create_app()
# All installed praecepta packages auto-register
```

## Entry Point Groups

| Group | Value Type | Purpose |
|-------|-----------|---------|
| `praecepta.routers` | `FastAPI APIRouter` | HTTP route handlers |
| `praecepta.middleware` | `MiddlewareContribution` | ASGI middleware |
| `praecepta.error_handlers` | `ErrorHandlerContribution` | Exception → HTTP status mappers |
| `praecepta.lifespan` | `LifespanContribution` | App startup/shutdown hooks |
| `praecepta.applications` | `Application` subclass | Event-sourced application singletons |
| `praecepta.projections` | `BaseProjection` subclass | Event projection handlers |
| `praecepta.subscriptions` | `Callable` | Event subscription registrations |

## Declaring Entry Points

In your package's `pyproject.toml`:

```toml
[project.entry-points."praecepta.routers"]
orders = "my_app.api:router"

[project.entry-points."praecepta.middleware"]
order_context = "my_app.middleware:contribution"

[project.entry-points."praecepta.applications"]
orders = "my_app.application:OrderApplication"
```

The entry point value is a dotted path to a Python object. For middleware and lifespan, the object should be an instance of the appropriate contribution dataclass.

## Contribution Types

Defined in `praecepta.foundation.application`:

```python
@dataclass(frozen=True, slots=True)
class MiddlewareContribution:
    middleware_class: type[Any]       # ASGI middleware class
    priority: int = 500              # Lower = outermost in ASGI stack
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class LifespanContribution:
    hook: Any                         # (app) -> AsyncContextManager[None]
    priority: int = 500              # Lower starts first, shuts down last

@dataclass(frozen=True, slots=True)
class ErrorHandlerContribution:
    exception_class: type[BaseException]
    handler: Any                      # (Request, Exception) -> Response
```

## Middleware Priority Bands

Middleware is sorted by priority (lower = outermost in the ASGI stack):

| Band | Range | Purpose | Examples |
|------|-------|---------|----------|
| Outermost | 0–99 | Request identity, tracing | `RequestIdMiddleware`, `TraceContextMiddleware` |
| Security | 100–199 | Authentication | `APIKeyAuthMiddleware`, `JWTAuthMiddleware` |
| Context | 200–299 | Request context | `RequestContextMiddleware`, `TenantStateMiddleware` |
| Policy | 300–399 | Enforcement | Rate limiting, resource limits |
| Default | 500 | Unspecified | — |

## Discovery Sequence

`create_app()` wires contributions in this order:

1. **Lifespan hooks** — discovered and composed via `AsyncExitStack` (priority-sorted)
2. **FastAPI instance** — created with composed lifespan
3. **CORS middleware** — always added from `AppSettings.cors`
4. **Middleware** — discovered, sorted by priority ascending, added in reverse (LIFO)
5. **Error handlers** — discovered and registered
6. **Routers** — discovered and included

## Controlling Discovery

Override or exclude discovered contributions:

```python
app = create_app(
    # Add contributions beyond what's discovered
    extra_routers=[custom_router],
    extra_middleware=[my_middleware],

    # Skip entire groups
    exclude_groups=frozenset({"praecepta.middleware"}),

    # Skip specific entries by name
    exclude_names=frozenset({"debug_router", "auth"}),
)
```

## Using Discovery Directly

The `discover()` utility is available for custom use:

```python
from praecepta.foundation.application import discover

contributions = discover("praecepta.routers")
for contrib in contributions:
    print(contrib.name, contrib.value)
```

Entry points that fail to load are logged and skipped (fail-soft).
