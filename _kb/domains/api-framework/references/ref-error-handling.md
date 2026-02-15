# Error Handling Reference

## Overview

Domain exception hierarchy with HTTP status mapping and Result types for explicit error handling.

## Domain Exception Hierarchy

```python
# src/shared/domain/exceptions.py
class DomainError(Exception):
    """Base class for all domain errors."""
    pass

class AggregateNotFoundError(DomainError):
    def __init__(self, aggregate_type: str, aggregate_id: UUID):
        self.aggregate_type = aggregate_type
        self.aggregate_id = aggregate_id
        super().__init__(f"{aggregate_type} {aggregate_id} not found")

class BusinessRuleViolationError(DomainError):
    pass

class ConcurrencyError(DomainError):
    pass
```

## Context-Specific Exceptions

```python
# src/dog_school/_shared/exceptions.py
class DogSchoolError(DomainError):
    pass

class DogAlreadyRegisteredError(DogSchoolError):
    def __init__(self, dog_id: UUID):
        super().__init__(f"Dog {dog_id} is already registered")

class DogAlreadyKnowsTrickError(DogSchoolError):
    def __init__(self, dog_id: UUID, trick: str):
        super().__init__(f"Dog {dog_id} already knows '{trick}'")
```

## HTTP Status Mapping

```python
# src/shared/api/error_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def setup_error_handlers(app: FastAPI):

    @app.exception_handler(AggregateNotFoundError)
    async def handle_not_found(request: Request, exc: AggregateNotFoundError):
        return JSONResponse(status_code=404, content={"error": str(exc)})

    @app.exception_handler(BusinessRuleViolationError)
    async def handle_business_rule(request: Request, exc: BusinessRuleViolationError):
        return JSONResponse(status_code=422, content={"error": str(exc)})

    @app.exception_handler(ConcurrencyError)
    async def handle_concurrency(request: Request, exc: ConcurrencyError):
        return JSONResponse(status_code=409, content={"error": str(exc)})
```

## Exception to HTTP Mapping

| Exception Type | HTTP Status | Meaning |
|----------------|-------------|---------|
| `AggregateNotFoundError` | 404 | Resource not found |
| `BusinessRuleViolationError` | 422 | Unprocessable entity |
| `ConcurrencyError` | 409 | Conflict (optimistic lock) |
| `ValidationError` (Pydantic) | 422 | Invalid input |

## Result Types

For explicit error handling without exceptions:

```python
from result import Ok, Err, Result

def register_dog(command: RegisterDog) -> Result[UUID, DogSchoolError]:
    if not command.name.strip():
        return Err(InvalidDogNameError("Name cannot be empty"))

    notification_id = command.execute()
    return Ok(command.dog_id)

# Usage with pattern matching
match register_dog(command):
    case Ok(dog_id):
        return {"id": str(dog_id)}
    case Err(error):
        raise error
```

## Key Points

- Domain exceptions inherit from `DomainError`
- Context-specific exceptions extend context base class
- Global exception handlers map to HTTP status codes
- Result types for explicit, type-safe error handling

## See Also

- [Domain Modeling](con-domain-modeling.md) - Where exceptions are raised
- [Testing](ref-testing.md) - Testing error scenarios
