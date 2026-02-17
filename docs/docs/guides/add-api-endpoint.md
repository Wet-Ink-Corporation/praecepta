# Add an API Endpoint

Praecepta uses FastAPI for the HTTP layer. Endpoints follow a consistent pattern with Pydantic DTOs, dependency injection, and auto-discovered routers.

## Basic Endpoint

```python
# my_app/api.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from decimal import Decimal

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

class PlaceOrderRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=50)
    total: Decimal = Field(gt=0)

class PlaceOrderResponse(BaseModel):
    order_id: str
    status: str

@router.post("/", response_model=PlaceOrderResponse)
def place_order(request: PlaceOrderRequest) -> PlaceOrderResponse:
    # Command endpoints use sync def (PADR-109)
    # ... business logic ...
    return PlaceOrderResponse(order_id=request.order_id, status="placed")
```

## Register the Router

In your package's `pyproject.toml`:

```toml
[project.entry-points."praecepta.routers"]
orders = "my_app.api:router"
```

The router is discovered and included automatically by `create_app()`.

## Sync vs Async

| Endpoint Type | Style | Rationale |
|---------------|-------|-----------|
| **Commands** (writes) | `def` (sync) | Event store operations are synchronous |
| **Queries** (reads) | `async def` | Database reads benefit from async I/O |

```python
# Command — sync
@router.post("/")
def place_order(request: PlaceOrderRequest) -> PlaceOrderResponse:
    ...

# Query — async
@router.get("/{order_id}")
async def get_order(order_id: str) -> OrderResponse:
    ...
```

## Error Handling

Domain exceptions map to HTTP status codes automatically via registered error handlers:

| Exception | HTTP Status |
|-----------|-------------|
| `ValidationError` | 400 Bad Request |
| `AuthenticationError` | 401 Unauthorized |
| `AuthorizationError` | 403 Forbidden |
| `NotFoundError` | 404 Not Found |
| `ConflictError` | 409 Conflict |

Raise domain exceptions in your business logic, and the framework handles the HTTP response:

```python
from praecepta.foundation.domain import NotFoundError

@router.get("/{order_id}")
async def get_order(order_id: str) -> OrderResponse:
    order = await find_order(order_id)
    if not order:
        raise NotFoundError(f"Order {order_id} not found")
    return OrderResponse.from_domain(order)
```

Error responses follow [RFC 7807 Problem Details](https://tools.ietf.org/html/rfc7807):

```json
{
  "type": "https://praecepta.dev/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Order ORD-123 not found"
}
```

## Request Context

The middleware stack propagates tenant and principal information through request context:

```python
from praecepta.foundation.application import (
    get_current_tenant_id,
    get_current_principal,
)

@router.get("/")
async def list_orders() -> list[OrderResponse]:
    tenant_id = get_current_tenant_id()   # Set by TenantStateMiddleware
    principal = get_current_principal()     # Set by auth middleware
    # Query scoped to current tenant...
```
