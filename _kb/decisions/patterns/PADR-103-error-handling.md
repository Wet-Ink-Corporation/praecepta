<!-- Derived from {Project} PADR-103-error-handling -->
# PADR-103: Error Handling Strategy

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Pattern, Error Handling

---

## Context

{Project} needs a consistent error handling strategy that:

- Distinguishes between expected and unexpected errors
- Provides clear error information for debugging
- Enables appropriate HTTP responses
- Supports logging and monitoring
- Maintains clean domain code

## Decision

**We will use a layered exception hierarchy** with domain exceptions, application exceptions, and API error handling middleware.

### Exception Hierarchy

```
BaseError (abstract)
├── DomainError (business rule violations)
│   ├── EntityNotFoundError
│   ├── ValidationError
│   ├── BusinessRuleViolationError
│   └── Context-specific errors
│
├── ApplicationError (use case failures)
│   ├── AuthorizationError
│   ├── ConcurrencyError
│   └── IntegrationError
│
└── InfrastructureError (technical failures)
    ├── DatabaseError
    ├── ExternalServiceError
    └── NetworkError
```

### Domain Exceptions

```python
# shared/exceptions.py
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

@dataclass
class ErrorDetail:
    """Structured error detail."""
    code: str
    message: str
    field: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

class BaseError(Exception):
    """Base class for all {Project} errors."""

    def __init__(self, message: str, code: str, details: list[ErrorDetail] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "details": [d.__dict__ for d in self.details]
        }

# Domain errors (business rule violations)
class DomainError(BaseError):
    """Base class for domain/business errors."""
    pass

class EntityNotFoundError(DomainError):
    """Raised when an entity cannot be found."""

    def __init__(self, entity_type: str, entity_id: UUID):
        super().__init__(
            message=f"{entity_type} with ID {entity_id} not found",
            code="ENTITY_NOT_FOUND",
            details=[ErrorDetail(
                code="NOT_FOUND",
                message=f"{entity_type} not found",
                metadata={"entity_type": entity_type, "entity_id": str(entity_id)}
            )]
        )
        self.entity_type = entity_type
        self.entity_id = entity_id

class BlockNotFoundError(EntityNotFoundError):
    """Raised when a order is not found."""

    def __init__(self, block_id: UUID):
        super().__init__("Order", block_id)

class ValidationError(DomainError):
    """Raised when validation fails."""

    def __init__(self, errors: list[ErrorDetail]):
        super().__init__(
            message="Validation failed",
            code="VALIDATION_ERROR",
            details=errors
        )

class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated."""

    def __init__(self, rule: str, message: str):
        super().__init__(
            message=message,
            code="BUSINESS_RULE_VIOLATION",
            details=[ErrorDetail(code=rule, message=message)]
        )
        self.rule = rule

class BlockAlreadyArchivedError(BusinessRuleViolationError):
    """Raised when trying to archive an already archived block."""

    def __init__(self, block_id: UUID):
        super().__init__(
            rule="BLOCK_ALREADY_ARCHIVED",
            message=f"Block {block_id} is already archived"
        )
```

### Application Exceptions

```python
# Application errors (use case failures)
class ApplicationError(BaseError):
    """Base class for application-level errors."""
    pass

class AuthorizationError(ApplicationError):
    """Raised when user lacks permission."""

    def __init__(self, user_id: str, permission: str, resource: str):
        super().__init__(
            message=f"User {user_id} lacks {permission} permission on {resource}",
            code="AUTHORIZATION_ERROR"
        )
        self.user_id = user_id
        self.permission = permission
        self.resource = resource

class ConcurrencyError(ApplicationError):
    """Raised when optimistic concurrency check fails."""

    def __init__(self, entity_type: str, entity_id: UUID, expected: int, actual: int):
        super().__init__(
            message=f"Concurrent modification of {entity_type} {entity_id}",
            code="CONCURRENCY_ERROR",
            details=[ErrorDetail(
                code="VERSION_MISMATCH",
                message=f"Expected version {expected}, found {actual}",
                metadata={"expected": expected, "actual": actual}
            )]
        )

class IntegrationError(ApplicationError):
    """Raised when integration with external service fails."""

    def __init__(self, service: str, operation: str, reason: str):
        super().__init__(
            message=f"Integration with {service} failed during {operation}: {reason}",
            code="INTEGRATION_ERROR"
        )
```

### Infrastructure Exceptions

```python
# Infrastructure errors (technical failures)
class InfrastructureError(BaseError):
    """Base class for infrastructure errors."""
    pass

class DatabaseError(InfrastructureError):
    """Raised for database-related failures."""

    def __init__(self, operation: str, cause: Exception):
        super().__init__(
            message=f"Database error during {operation}",
            code="DATABASE_ERROR"
        )
        self.__cause__ = cause

class ExternalServiceError(InfrastructureError):
    """Raised when external service call fails."""

    def __init__(self, service: str, status_code: int, response: str):
        super().__init__(
            message=f"External service {service} returned {status_code}",
            code="EXTERNAL_SERVICE_ERROR"
        )
        self.service = service
        self.status_code = status_code
        self.response = response
```

## API Error Handling

### Exception Handler Middleware

```python
# api/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain errors (400 Bad Request)."""
    logger.warning("domain_error", code=exc.code, message=exc.message)
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )

async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
    """Handle not found errors (404)."""
    logger.info("entity_not_found", entity_type=exc.entity_type, entity_id=str(exc.entity_id))
    return JSONResponse(
        status_code=404,
        content=exc.to_dict()
    )

async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    """Handle authorization errors (403)."""
    logger.warning(
        "authorization_denied",
        user_id=exc.user_id,
        permission=exc.permission,
        resource=exc.resource
    )
    return JSONResponse(
        status_code=403,
        content={"code": exc.code, "message": "Access denied"}
    )

async def infrastructure_error_handler(request: Request, exc: InfrastructureError) -> JSONResponse:
    """Handle infrastructure errors (500)."""
    logger.error("infrastructure_error", code=exc.code, message=exc.message, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"}
    )

async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors (500)."""
    logger.exception("unhandled_error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
    )

# Register handlers
def configure_exception_handlers(app: FastAPI):
    app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(AuthorizationError, authorization_error_handler)
    app.add_exception_handler(InfrastructureError, infrastructure_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
```

### HTTP Status Code Mapping

| Exception Type | HTTP Status | Rationale |
|---------------|-------------|-----------|
| `EntityNotFoundError` | 404 | Resource doesn't exist |
| `ValidationError` | 400 | Invalid input |
| `BusinessRuleViolationError` | 400 | Business constraint failed |
| `AuthorizationError` | 403 | Permission denied |
| `ConcurrencyError` | 409 | Conflict due to concurrent modification |
| `InfrastructureError` | 500 | Server-side failure |
| `Exception` (unhandled) | 500 | Unexpected error |

## Rationale

### Why Exception Hierarchy?

- **Type-based handling:** Different exception types enable specific responses
- **Domain isolation:** Domain code raises domain exceptions, not HTTP errors
- **Consistent structure:** All errors have code, message, details
- **Logging clarity:** Can log with appropriate severity

### Why Not Result Types?

Result types (like Rust's `Result<T, E>`) are valid but:

- Python doesn't enforce handling
- Less idiomatic in Python ecosystem
- FastAPI exception handlers work well with exceptions

For complex operations where multiple errors are possible, we can use `ErrorDetail` lists.

## Consequences

### Positive

1. **Clear Categorization:** Know error type by exception class
2. **Appropriate Responses:** HTTP codes match error types
3. **Debugging Info:** Structured details for investigation
4. **Domain Isolation:** Domain doesn't know about HTTP
5. **Consistent API:** All errors have same structure

### Negative

1. **Exception Overhead:** Performance cost (negligible for I/O-bound code)
2. **Missing Errors:** New exceptions need handler registration
3. **Detail Leakage:** Must be careful not to expose internal details

### Mitigations

| Risk | Mitigation |
|------|------------|
| Performance | Exceptions are for exceptional cases only |
| Missing handlers | Unhandled error handler catches all |
| Detail leakage | Infrastructure errors return generic message |

## Usage Examples

### In Domain Layer

```python
class Order:
    def archive(self) -> None:
        if self.archived:
            raise BlockAlreadyArchivedError(self.id)
        self.archived = True
```

### In Application Layer

```python
class ArchiveBlockHandler:
    async def handle(self, command: ArchiveBlockCommand) -> None:
        block = await self._repository.get(command.block_id)
        if not block:
            raise BlockNotFoundError(command.block_id)

        if not await self._security.can_write(command.user_id, block):
            raise AuthorizationError(
                user_id=command.user_id,
                permission="write",
                resource=f"block:{command.block_id}"
            )

        block.archive()  # May raise BlockAlreadyArchivedError
        await self._repository.save(block)
```

### In Infrastructure Layer

```python
class PostgresRepository:
    async def save(self, block: Order) -> None:
        try:
            await self._db.execute(...)
        except asyncpg.UniqueViolationError as e:
            raise ConcurrencyError(
                entity_type="Order",
                entity_id=block.id,
                expected=block.version,
                actual=block.version + 1
            ) from e
        except asyncpg.PostgresError as e:
            raise DatabaseError("save", e) from e
```

## Related Decisions

- PADR-102: Hexagonal Ports (exceptions flow through layers)
- PADR-105: Logging & Observability (error logging)

## References

- [Python Exception Handling Best Practices](https://docs.python.org/3/tutorial/errors.html)
- [FastAPI Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
