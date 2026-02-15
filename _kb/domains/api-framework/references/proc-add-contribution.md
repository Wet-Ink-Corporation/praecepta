# Adding Contributions Procedure

## Overview

Praecepta uses PEP 621 entry points for auto-discovery of routers, middleware, lifespan hooks, and error handlers. Packages declare contributions in their `pyproject.toml`; `create_app()` discovers them at runtime via `importlib.metadata`. Installing a package is sufficient to activate its contributions -- zero manual wiring required.

Contribution types are defined in `praecepta.foundation.application.contributions` (Layer 0), keeping them framework-agnostic.

See [PADR-122](../../../decisions/patterns/PADR-122-entry-point-auto-discovery.md) for the design rationale.

---

## Procedure: Adding a Router

1. **Create a module** with a module-level `APIRouter` instance:

   ```python
   # praecepta/domain/tenancy/api.py
   from fastapi import APIRouter

   router = APIRouter(prefix="/tenants", tags=["tenancy"])

   @router.get("/healthz")
   async def healthz() -> dict[str, str]:
       return {"status": "ok"}
   ```

2. **Declare the entry point** in the package's `pyproject.toml`:

   ```toml
   [project.entry-points."praecepta.routers"]
   tenancy = "praecepta.domain.tenancy.api:router"
   ```

   The key (`tenancy`) is the entry point name. The value is `module.path:attribute`.

3. **Re-register** by running:

   ```bash
   uv sync --dev
   ```

4. **Verify**: start the app and check `/docs` for the new routes.

---

## Procedure: Adding Middleware

1. **Create the middleware class** (ASGI or `BaseHTTPMiddleware`):

   ```python
   # praecepta/infra/fastapi/middleware/request_id.py
   from starlette.middleware.base import BaseHTTPMiddleware

   class RequestIdMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request, call_next):
           # ... middleware logic
           response = await call_next(request)
           return response
   ```

2. **Add a module-level `contribution`** using `MiddlewareContribution`:

   ```python
   from praecepta.foundation.application import MiddlewareContribution

   contribution = MiddlewareContribution(
       middleware_class=RequestIdMiddleware,
       priority=10,  # Outermost band (0-99)
   )
   ```

3. **Choose the correct priority band**:

   | Band | Range | Purpose | Examples |
   |------|-------|---------|----------|
   | Outermost | 0-99 | Request identity, tracing | `RequestIdMiddleware` (10) |
   | Security | 100-199 | Authentication, API keys | `AuthMiddleware` (150) |
   | Context | 200-299 | Request context population | `RequestContextMiddleware` (200) |
   | Policy | 300-399 | Enforcement, rate limiting | Resource limit checks |
   | Default | 500 | Unspecified | -- |

4. **Declare the entry point** in `pyproject.toml`:

   ```toml
   [project.entry-points."praecepta.middleware"]
   request_id = "praecepta.infra.fastapi.middleware.request_id:contribution"
   ```

5. **Re-register**: `uv sync --dev`

6. **Verify**: check startup logs for discovery messages at DEBUG level.

---

## Procedure: Adding a Lifespan Hook

1. **Create an async context manager** that accepts the FastAPI app:

   ```python
   from contextlib import asynccontextmanager
   from collections.abc import AsyncIterator
   from fastapi import FastAPI

   @asynccontextmanager
   async def observability_hook(app: FastAPI) -> AsyncIterator[None]:
       # Startup logic
       configure_tracing(app)
       configure_logging()
       try:
           yield
       finally:
           # Shutdown logic
           shutdown_tracing()
   ```

2. **Wrap in a `LifespanContribution`**:

   ```python
   from praecepta.foundation.application import LifespanContribution

   lifespan_contribution = LifespanContribution(
       hook=observability_hook,
       priority=10,  # Lower priority starts first, shuts down last
   )
   ```

3. **Declare the entry point** in `pyproject.toml`:

   ```toml
   [project.entry-points."praecepta.lifespan"]
   observability = "praecepta.infra.observability:lifespan_contribution"
   ```

4. **Re-register**: `uv sync --dev`

Hooks are composed via `AsyncExitStack` -- lower priority starts first and shuts down last (stack semantics).

---

## Procedure: Adding an Error Handler

### Option A: Single Handler via ErrorHandlerContribution

1. **Create the handler function**:

   ```python
   from fastapi import Request
   from fastapi.responses import JSONResponse

   async def my_error_handler(request: Request, exc: MyCustomError) -> JSONResponse:
       return JSONResponse(status_code=400, content={"detail": str(exc)})
   ```

2. **Wrap in an `ErrorHandlerContribution`**:

   ```python
   from praecepta.foundation.application import ErrorHandlerContribution

   contribution = ErrorHandlerContribution(
       exception_class=MyCustomError,
       handler=my_error_handler,
   )
   ```

3. **Declare the entry point**:

   ```toml
   [project.entry-points."praecepta.error_handlers"]
   my_error = "my_package.error_handlers:contribution"
   ```

### Option B: Registration Function for Multiple Handlers

For packages that register many related handlers (like RFC 7807 error mapping):

1. **Create a registration function**:

   ```python
   def register_exception_handlers(app: FastAPI) -> None:
       app.add_exception_handler(NotFoundError, not_found_handler)
       app.add_exception_handler(ValidationError, validation_error_handler)
       app.add_exception_handler(ConflictError, conflict_error_handler)
       # ... more handlers
   ```

2. **Declare the entry point** pointing to the function:

   ```toml
   [project.entry-points."praecepta.error_handlers"]
   rfc7807 = "praecepta.infra.fastapi.error_handlers:register_exception_handlers"
   ```

   When `create_app()` discovers a callable (not an `ErrorHandlerContribution`), it calls it with the app instance.

---

## Procedure: Adding a New Package

1. **Create the directory structure**:

   ```
   packages/{name}/
   +-- pyproject.toml
   +-- src/
   |   +-- praecepta/                    # NO __init__.py (PEP 420)
   |       +-- {layer}/                  # NO __init__.py (PEP 420)
   |           +-- {name}/
   |               +-- __init__.py       # Leaf package only
   |               +-- py.typed          # PEP 561 marker
   +-- tests/
   ```

   Intermediate directories (`praecepta/`, `praecepta/{layer}/`) must **not** have `__init__.py`.

2. **Create `pyproject.toml`** with workspace dependencies:

   ```toml
   [project]
   name = "praecepta-{layer}-{name}"
   version = "0.1.0"
   dependencies = ["praecepta-foundation-domain"]

   [tool.uv.sources]
   praecepta-foundation-domain = { workspace = true }

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [tool.hatch.build.targets.wheel]
   packages = ["src/praecepta"]
   ```

3. **Add to root `pyproject.toml`**:

   ```toml
   # In [project] dependencies:
   "praecepta-{layer}-{name}",

   # In [tool.uv.sources]:
   praecepta-{layer}-{name} = { workspace = true }
   ```

   The `[tool.uv.workspace] members = ["packages/*"]` glob auto-discovers the new directory.

4. **Sync**: `uv sync --dev`

5. **Verify**: `uv run python -c "import praecepta.{layer}.{name}"`

---

## See Also

- [ref-app-factory.md](ref-app-factory.md) -- Full `create_app()` API and discovery sequence
- [ref-workspace-pep420-conventions.md](../../ddd-patterns/references/ref-workspace-pep420-conventions.md) -- Namespace package conventions
- PADR-122 -- Entry-point auto-discovery design decision
