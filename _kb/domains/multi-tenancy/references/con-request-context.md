# Request Context

> Cross-cutting request-scoped data propagation

---

## Overview

Request context provides a mechanism for propagating request-scoped data (tenant ID, user ID, correlation ID) across the call stack without explicit parameter passing. This enables proper audit trails, multi-tenancy isolation, and distributed tracing.

---

## Implementation

### ContextVar Pattern

Python's `contextvars` module provides async-safe context propagation:

```python
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True, slots=True)
class RequestContext:
    tenant_id: str
    user_id: UUID
    correlation_id: str

request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)
```

### Middleware Integration

The `RequestContextMiddleware` extracts headers and populates context:

```python
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = set_request_context(
            tenant_id=request.headers.get("X-Tenant-ID", ""),
            user_id=UUID(request.headers.get("X-User-ID", "")),
            correlation_id=request.headers.get("X-Correlation-ID") or str(uuid4()),
        )
        try:
            return await call_next(request)
        finally:
            clear_request_context(token)
```

### Accessor Functions

Safe accessors raise clear errors when context is unavailable:

```python
def get_current_user_id() -> UUID:
    ctx = request_context.get()
    if ctx is None:
        raise NoRequestContextError()
    return ctx.user_id
```

---

## Usage Patterns

### In Domain Event Handlers

```python
from {project}.shared.infrastructure.context import get_current_user_id

class UpdateBlockHandler:
    def handle(self, cmd: UpdateBlockCommand) -> None:
        block = self.repository.get(cmd.block_id)
        block.update_title(
            new_title=cmd.title,
            updated_by=get_current_user_id(),  # From context
        )
```

### In Audit Events

All mutation events should include user attribution:

```python
@dataclass(frozen=True)
class BlockUpdated(MemoryEvent):
    title: str
    updated_by: UUID  # Required for audit trail
    updated_at: datetime
```

---

## Required Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Tenant-ID` | Yes | Multi-tenancy isolation |
| `X-User-ID` | Yes | Audit trail attribution |
| `X-Correlation-ID` | No | Distributed tracing (auto-generated if missing) |

---

## Testing

### Unit Tests

Mock the context for unit testing:

```python
from {project}.shared.infrastructure.context import set_request_context, clear_request_context

def test_handler_uses_current_user():
    token = set_request_context(
        tenant_id="test-tenant",
        user_id=UUID("12345678-1234-1234-1234-123456789abc"),
        correlation_id="test-correlation",
    )
    try:
        result = handler.handle(command)
        assert result.updated_by == UUID("12345678-1234-1234-1234-123456789abc")
    finally:
        clear_request_context(token)
```

### Integration Tests

The middleware automatically populates context from headers:

```python
async def test_endpoint_with_context(client):
    response = await client.post(
        "/api/v1/blocks",
        headers={
            "X-Tenant-ID": "test-tenant",
            "X-User-ID": "12345678-1234-1234-1234-123456789abc",
        },
        json={"title": "Test Block"},
    )
    assert response.status_code == 201
```

---

## See Also

- [con-security-model.md](con-security-model.md) - Tenant isolation
- [con-observability.md](con-observability.md) - Correlation ID tracing
- [con-error-handling.md](con-error-handling.md) - NoRequestContextError handling
