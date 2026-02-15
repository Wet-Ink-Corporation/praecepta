# Request Context Reference

## Overview

`RequestContext` is the mechanism for propagating request-scoped data (tenant ID, user ID, correlation ID) across the call stack without explicit parameter passing. It lives in the foundation layer so that any package at any layer can read the current request context.

**Module:** `praecepta.foundation.application.context`
**Package:** `praecepta-foundation-application` (Layer 0)

---

## Why Foundation Layer?

`RequestContext` is consumed by packages across multiple layers:

- `praecepta.infra.fastapi` -- middleware populates context from HTTP headers
- `praecepta.infra.auth` -- auth middleware sets the principal context
- `praecepta.infra.persistence` -- database sessions can read tenant/user for audit
- `praecepta.domain.*` -- domain services read tenant and user IDs

Placing it in `praecepta.foundation.application` (Layer 0) avoids circular dependencies between Layer 1 infrastructure packages. All packages depend downward on foundation.

---

## RequestContext Dataclass

```python
@dataclass(frozen=True, slots=True)
class RequestContext:
    tenant_id: str
    user_id: UUID
    correlation_id: str
```

The dataclass is **frozen** (immutable) and uses **slots** for memory efficiency. Once set for a request, the context cannot be modified -- only replaced or cleared.

---

## ContextVar Mechanism

The context is stored in a Python `ContextVar`, which provides per-task (per-request in async) isolation:

```python
request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)
```

When no request is active, the value is `None`.

---

## Setting Context

```python
from praecepta.foundation.application.context import set_request_context

token = set_request_context(
    tenant_id="tenant-abc",
    user_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    correlation_id="req-12345",
)
```

The function creates a `RequestContext` instance and stores it in the `ContextVar`. It returns a `Token` that **must** be used later to reset the context:

```python
from praecepta.foundation.application.context import clear_request_context

clear_request_context(token)  # Resets ContextVar to previous value
```

---

## Reading Context

Accessor functions raise `NoRequestContextError` if called outside a request:

| Function | Returns | Description |
|----------|---------|-------------|
| `get_current_context()` | `RequestContext` | Full context object |
| `get_current_tenant_id()` | `str` | Tenant identifier |
| `get_current_user_id()` | `UUID` | Authenticated user UUID |
| `get_current_correlation_id()` | `str` | Distributed tracing ID |

```python
from praecepta.foundation.application.context import get_current_tenant_id

tenant = get_current_tenant_id()  # Raises NoRequestContextError if no context
```

---

## NoRequestContextError

Raised when any accessor is called outside of a request lifecycle:

```python
class NoRequestContextError(RuntimeError):
    """Raised when request context is accessed outside of a request."""
```

Message: `"No request context available. Ensure this code is called within an HTTP request with context middleware."`

---

## Middleware Population Flow

`RequestContextMiddleware` (priority 200, context band) reads HTTP headers and populates the context:

```python
# Headers read:
#   X-Tenant-ID  -> tenant_id (empty string if missing)
#   X-User-ID    -> user_id (nil UUID if missing/invalid)
#   X-Correlation-ID -> correlation_id (auto-generated UUID4 if missing)

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = set_request_context(tenant_id, user_id, correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            clear_request_context(token)
```

The middleware always clears context in the `finally` block, preventing leakage between requests.

---

## Principal Context

A **separate** `ContextVar` manages the authenticated principal, decoupled from `RequestContext`:

```python
_principal_context: ContextVar[Principal | None] = ContextVar(
    "principal_context", default=None
)
```

This separation exists because:

1. `RequestContext` is frozen -- adding principal would require a new object per auth step
2. Auth lifecycle is independent -- `AuthMiddleware` runs at priority 100-199, after `RequestContextMiddleware` at 200
3. Some endpoints are unauthenticated -- principal is `None` while request context is still valid

**Functions:**

| Function | Description |
|----------|-------------|
| `set_principal_context(principal)` | Set by AuthMiddleware after JWT validation |
| `clear_principal_context(token)` | Clear in middleware finally block |
| `get_current_principal()` | Raises `NoRequestContextError` if no principal |
| `get_optional_principal()` | Returns `None` instead of raising |

---

## Testing Patterns

**Direct setup** (unit tests):

```python
from uuid import uuid4
from praecepta.foundation.application.context import (
    set_request_context,
    clear_request_context,
)

token = set_request_context(
    tenant_id="test-tenant",
    user_id=uuid4(),
    correlation_id="test-corr-id",
)
try:
    # ... test code that reads context
    pass
finally:
    clear_request_context(token)
```

**Via TestClient** (integration tests):

```python
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get(
    "/items",
    headers={
        "X-Tenant-ID": "test-tenant",
        "X-User-ID": str(uuid4()),
        "X-Correlation-ID": "test-123",
    },
)
```

---

## See Also

- [ref-app-factory.md](ref-app-factory.md) -- App factory wiring and middleware ordering
- PADR-110 -- Application lifecycle and context design
