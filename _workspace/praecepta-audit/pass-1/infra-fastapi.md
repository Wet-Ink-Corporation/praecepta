# infra-fastapi -- Library Usage Audit

**Upstream Library:** FastAPI >=0.115, Starlette (transitive), pydantic-settings >=2.0
**RAG Status:** AMBER
**Checklist:** 14/19 passed

## Findings

| ID | Severity | Checklist | Description | File:Line | Recommendation |
|----|----------|-----------|-------------|-----------|----------------|
| F-01 | HIGH | FA-5 | CORS defaults allow all origins (`["*"]`), all methods, all headers. Combined with `allow_credentials=False` this is safe, but if a downstream consumer sets `allow_credentials=True` while leaving `allow_origins=["*"]`, Starlette's CORSMiddleware silently downgrades to no CORS (per spec, `*` + credentials is forbidden). No validator prevents this misconfiguration. | `settings.py:24-28` | Add a `model_validator(mode="after")` on `CORSSettings` that raises if `allow_credentials=True` and `allow_origins == ["*"]`. |
| F-02 | MEDIUM | FA-7 | `unhandled_exception_handler` reads debug mode from `os.environ.get("DEBUG")` at request time instead of from `AppSettings.debug` which is already wired into the app. This bypasses the settings abstraction and means the debug flag is not governed by `APP_` prefix or pydantic validation. | `error_handlers.py:513` | Accept `debug` from `app.debug` (already set at line 89 of `app_factory.py`) via `request.app.debug` instead of raw `os.environ`. |
| F-03 | MEDIUM | FA-11 | Because debug mode for the 500 handler is read from a raw env var (`DEBUG`), it is possible for a production deployment to accidentally leak exception details if `DEBUG=true` is set in the environment without the `APP_` prefix. The `AppSettings.debug` field uses `APP_DEBUG` prefix which is safer. | `error_handlers.py:513` | Same fix as F-02: use `request.app.debug`. |
| F-04 | MEDIUM | FA-15 | Health check endpoint returns a trivial `{"status": "ok"}` with no actual health probing (database connectivity, event store reachability, etc.). The module docstring acknowledges this is a stub ("will be replaced by a full health endpoint in Step 6") but it currently provides no meaningful readiness signal. | `_health.py:14-17` | Implement a readiness check that verifies critical dependencies (event store connection, projection currency) or at minimum expose `/readyz` vs `/healthz` distinction. |
| F-05 | MEDIUM | FA-16 | All three middleware classes (`RequestIdMiddleware`, `RequestContextMiddleware`, `TenantStateMiddleware`) use `BaseHTTPMiddleware` which is known to have issues: it creates a new `anyio` task per request (breaks `contextvars` in some edge cases), does not support streaming responses well, and has poor WebSocket support. FastAPI/Starlette maintainers recommend pure ASGI middleware for production. | `request_id.py:69`, `request_context.py:34`, `tenant_state.py:44` | Migrate to pure ASGI middleware pattern (`async def __call__(self, scope, receive, send)`) for all three. This also resolves FA-18. |
| F-06 | MEDIUM | FA-17 | Middleware priority bands (0-99 = outermost, 200-299 = context) are implied by comments in individual module files but not enforced programmatically. A misconfigured contribution could use any integer. No validation rejects out-of-band priorities. | `request_id.py:156`, `request_context.py:91`, `tenant_state.py:143` | Add a `field_validator` or range constant on `MiddlewareContribution.priority` in the foundation package, or validate in `create_app` before sorting. |
| F-07 | LOW | FA-18 | `BaseHTTPMiddleware` does not properly handle WebSocket connections. If a WebSocket route is added, the middleware will fail silently or raise. None of the middleware implementations check `scope["type"]`. | `request_id.py:69`, `request_context.py:34`, `tenant_state.py:44` | Either migrate to pure ASGI middleware (see F-05) or add explicit WebSocket scope checks in `dispatch()`. |
| F-08 | LOW | FA-12 | `AppSettings.version` defaults to `"0.1.0"` which is distinct from the actual package version (`0.3.0`). There is no mechanism to auto-populate the OpenAPI schema version from the package metadata. | `settings.py:58` | Default to `importlib.metadata.version("praecepta-infra-fastapi")` or require explicit setting. |
| F-09 | LOW | FA-14 | `compose_lifespan` uses `AsyncExitStack` which provides correct cleanup on failure (already-entered hooks will be exited in reverse). However, there is no logging or structured error reporting when a hook fails during startup. The exception propagates raw. | `lifespan.py:38-49` | Wrap `stack.enter_async_context(ctx)` in a try/except that logs which hook failed before re-raising, aiding operational debugging. |

## Passed Checklist Items

| ID | Checklist | Evidence |
|----|-----------|----------|
| FA-1 | Lifespan protocol | `create_app()` passes `lifespan=composed_lifespan` to `FastAPI()` constructor (`app_factory.py:90`). No use of deprecated `on_event`. `compose_lifespan` returns an `@asynccontextmanager`-decorated factory. Correct. |
| FA-2 | Middleware LIFO ordering | `app_factory.py:117-118` sorts by priority ascending then iterates in `reversed()` order for `app.add_middleware()`. This correctly produces LIFO execution where lowest priority = outermost. |
| FA-3 | Error handlers | `error_handlers.py:535-612` uses `app.add_exception_handler()` for all exception types. No middleware-based exception catching. Correct. |
| FA-4 | Dependency injection | `require_feature` and `check_resource_limit` return closures used with `Depends()`. They read tenant context from `ContextVar` (request-scoped) and checker from `app.state` (app-scoped). Correct scoping. |
| FA-6 | Router inclusion | `app_factory.py:152-153` uses `app.include_router(router)`. The health stub sets `tags=["health"]` (`_health.py:11`). Routers discovered via entry points are included without prefix override (delegating to the router's own prefix). Correct. |
| FA-8 | Background tasks | No background tasks are used in this package. N/A -- Pass. |
| FA-9 | TestClient lifespan | Tests use `TestClient(app)` as a context manager where lifespan matters (`test_app_factory.py:122`) and directly where it does not. `TestClient` in Starlette handles lifespan correctly by default. |
| FA-10 | Pydantic Settings | `AppSettings` and `CORSSettings` both use `model_config = SettingsConfigDict(env_prefix=..., extra="ignore")`, `Field()` defaults, and `field_validator` for comma parsing. Correct v2 patterns. |
| FA-13 | Lifespan composition order | `compose_lifespan` sorts by `priority` ascending (`lifespan.py:36`), enters via `AsyncExitStack` (LIFO shutdown). Tests verify ordering (`test_lifespan.py:29-55`). Correct. |
| FA-19 | Middleware exception handling | All three middleware use `try/finally` to reset context vars regardless of exceptions (`request_id.py:119-126`, `request_context.py:78-85`). Exceptions propagate to the error handler layer. Correct. |

## Narrative

The `infra-fastapi` package demonstrates solid architectural design. The app factory's entry-point auto-discovery, contribution-based wiring, and LIFO middleware ordering are all correctly implemented against FastAPI 0.115+ APIs. Error handlers properly use `add_exception_handler()` with RFC 7807 problem details, and the sanitization layer prevents sensitive data leakage.

The most significant concern is the use of `BaseHTTPMiddleware` for all three middleware components (F-05/F-07). While functional for HTTP requests, this base class is deprecated in spirit by the Starlette maintainers due to `contextvars` leakage under concurrent requests, broken streaming responses, and lack of WebSocket support. Since this framework is designed for multi-tenant production use, migrating to pure ASGI middleware is recommended before GA.

The second notable issue is the debug mode detection in the unhandled exception handler (F-02/F-03), which bypasses the `AppSettings` abstraction by reading directly from `os.environ["DEBUG"]`. This creates a risk of accidentally exposing exception internals in production if the wrong environment variable name is used.

The CORS validator gap (F-01) is a latent safety issue: while the current defaults are safe, no guardrail prevents a downstream configuration from enabling `allow_credentials=True` with wildcard origins, which would be silently broken by the browser CORS spec.

All test files demonstrate correct `TestClient` usage patterns and good coverage of the middleware, dependency, and error handler layers.
