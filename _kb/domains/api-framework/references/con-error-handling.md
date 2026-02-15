# Error Handling

> Exception patterns, error responses, and failure recovery

---

## Overview

{Project} uses a structured approach to error handling that provides clear information for debugging while maintaining security. This document describes error patterns applied across all bounded contexts.

---

## Error Classification

### Error Categories

| Category | HTTP Status | Retryable | User-Facing |
|----------|-------------|-----------|-------------|
| **Validation** | 400 Bad Request | No | Yes |
| **Authentication** | 401 Unauthorized | Yes (refresh) | Yes |
| **Authorization** | 403 Forbidden | No | Yes |
| **Not Found** | 404 Not Found | No | Yes |
| **Conflict** | 409 Conflict | Maybe | Yes |
| **Rate Limited** | 429 Too Many Requests | Yes | Yes |
| **Internal** | 500 Internal Server | Yes | No (generic) |
| **Unavailable** | 503 Service Unavailable | Yes | Yes |

### Exception Hierarchy

```python
from dataclasses import dataclass
from typing import Any

class {Project}Error(Exception):
    """Base exception for all {Project} errors."""

    def __init__(
        self,
        message: str,
        code: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

# Domain Errors
class DomainError({Project}Error):
    """Base for domain-level errors."""
    pass

class ValidationError(DomainError):
    """Invalid input or state."""
    pass

class BusinessRuleViolationError(DomainError):
    """Business rule was violated."""
    pass

class AggregateNotFoundError(DomainError):
    """Aggregate does not exist."""
    pass

class ConcurrencyError(DomainError):
    """Optimistic concurrency conflict."""
    pass

# Infrastructure Errors
class InfrastructureError({Project}Error):
    """Base for infrastructure-level errors."""
    pass

class DatabaseError(InfrastructureError):
    """Database operation failed."""
    pass

class ExternalServiceError(InfrastructureError):
    """External service call failed."""
    pass

class RateLimitError(InfrastructureError):
    """Rate limit exceeded."""
    pass

# Security Errors
class SecurityError({Project}Error):
    """Base for security-related errors."""
    pass

class AuthenticationError(SecurityError):
    """Authentication failed."""
    pass

class AuthorizationError(SecurityError):
    """User not authorized."""
    pass

class CrossTenantAccessError(SecurityError):
    """Attempted cross-tenant access."""
    pass
```

---

## Domain Error Examples

### Context-Specific Errors

```python
# Memory Context
class BlockNotFoundError(AggregateNotFoundError):
    def __init__(self, block_id: UUID):
        super().__init__(
            message=f"Memory block {block_id} not found",
            code="BLOCK_NOT_FOUND",
            details={"block_id": str(block_id)},
        )

class MembershipExistsError(BusinessRuleViolationError):
    def __init__(self, content_id: UUID, block_id: UUID):
        super().__init__(
            message=f"Content {content_id} already in block {block_id}",
            code="MEMBERSHIP_EXISTS",
            details={
                "content_id": str(content_id),
                "block_id": str(block_id),
            },
        )

class BlockArchivedError(BusinessRuleViolationError):
    def __init__(self, block_id: UUID):
        super().__init__(
            message=f"Block {block_id} is archived and cannot be modified",
            code="BLOCK_ARCHIVED",
            details={"block_id": str(block_id)},
        )

# Ingestion Context
class DocumentNotFoundError(AggregateNotFoundError):
    def __init__(self, document_id: UUID):
        super().__init__(
            message=f"Source document {document_id} not found",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": str(document_id)},
        )

class ChunkingError(DomainError):
    def __init__(self, document_id: UUID, reason: str):
        super().__init__(
            message=f"Failed to chunk document {document_id}: {reason}",
            code="CHUNKING_FAILED",
            details={
                "document_id": str(document_id),
                "reason": reason,
            },
        )

# Query Context
class QueryTimeoutError(DomainError):
    def __init__(self, query_id: UUID, timeout_ms: int):
        super().__init__(
            message=f"Query {query_id} timed out after {timeout_ms}ms",
            code="QUERY_TIMEOUT",
            details={
                "query_id": str(query_id),
                "timeout_ms": timeout_ms,
            },
        )
```

---

## API Error Responses

### Standard Error Format

```python
from pydantic import BaseModel
from typing import Any

class ErrorResponse(BaseModel):
    """Standard API error response."""
    error: str           # Machine-readable code
    message: str         # Human-readable message
    details: dict[str, Any] | None = None
    trace_id: str | None = None  # For correlation

class ValidationErrorResponse(ErrorResponse):
    """Validation error with field details."""
    fields: dict[str, list[str]]  # Field -> error messages

# Example responses
{
    "error": "BLOCK_NOT_FOUND",
    "message": "Memory block 550e8400-e29b-41d4-a716-446655440000 not found",
    "details": {
        "block_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "trace_id": "abc123xyz"
}

{
    "error": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "fields": {
        "title": ["Title is required", "Title must be at least 3 characters"],
        "scope_type": ["Invalid scope type: INVALID"]
    },
    "trace_id": "abc123xyz"
}
```

### Exception Handler

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

def create_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers."""

    @app.exception_handler({Project}Error)
    async def {Project}_error_handler(
        request: Request,
        exc: {Project}Error,
    ) -> JSONResponse:
        status_code = _get_status_code(exc)
        trace_id = request.state.trace_id

        # Log with context
        logger.warning(
            "domain_error",
            error_code=exc.code,
            error_message=exc.message,
            details=exc.details,
            trace_id=trace_id,
            status_code=status_code,
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details,
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        trace_id = request.state.trace_id

        # Log full details for debugging
        logger.exception(
            "unhandled_error",
            error_type=type(exc).__name__,
            error_message=str(exc),
            trace_id=trace_id,
        )

        # Return generic message to user (security)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "trace_id": trace_id,
            },
        )

def _get_status_code(exc: {Project}Error) -> int:
    """Map exception type to HTTP status code."""
    match exc:
        case ValidationError():
            return 400
        case AuthenticationError():
            return 401
        case AuthorizationError() | CrossTenantAccessError():
            return 403
        case AggregateNotFoundError():
            return 404
        case ConcurrencyError():
            return 409
        case RateLimitError():
            return 429
        case ExternalServiceError():
            return 503
        case _:
            return 500
```

---

## Result Pattern

### Result Type

For operations that can fail predictably:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound={Project}Error)

@dataclass
class Success(Generic[T]):
    """Successful result."""
    value: T

@dataclass
class Failure(Generic[E]):
    """Failed result."""
    error: E

Result = Success[T] | Failure[E]

# Usage in handlers
class CreateBlockHandler:
    async def handle(
        self,
        command: CreateBlock,
    ) -> Result[UUID, DomainError]:
        # Validate
        if not command.title:
            return Failure(ValidationError(
                message="Title is required",
                code="TITLE_REQUIRED",
            ))

        # Check business rules
        existing = await self.repo.find_by_title(
            command.title,
            command.scope_id,
        )
        if existing:
            return Failure(BusinessRuleViolationError(
                message=f"Block with title '{command.title}' already exists",
                code="DUPLICATE_TITLE",
            ))

        # Create block
        block_id = await self._create_block(command)
        return Success(block_id)

# Usage in endpoint
@router.post("/blocks")
async def create_block(
    request: CreateBlockRequest,
    handler: CreateBlockHandler = Depends(),
) -> BlockResponse:
    result = await handler.handle(CreateBlock(**request.model_dump()))

    match result:
        case Success(block_id):
            return BlockResponse(id=block_id)
        case Failure(error):
            raise error  # Let exception handler convert to response
```

---

## Retry Strategies

### Retry Configuration

```python
from dataclasses import dataclass
from enum import Enum

class RetryStrategy(Enum):
    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    strategy: RetryStrategy
    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int
    jitter: bool = True

# Default configs per error type
RETRY_CONFIGS = {
    "database": RetryConfig(
        strategy=RetryStrategy.EXPONENTIAL,
        max_attempts=3,
        base_delay_ms=100,
        max_delay_ms=5000,
        jitter=True,
    ),
    "external_service": RetryConfig(
        strategy=RetryStrategy.EXPONENTIAL,
        max_attempts=5,
        base_delay_ms=500,
        max_delay_ms=30000,
        jitter=True,
    ),
    "embedding": RetryConfig(
        strategy=RetryStrategy.EXPONENTIAL,
        max_attempts=3,
        base_delay_ms=1000,
        max_delay_ms=10000,
        jitter=True,
    ),
}
```

### Retry Decorator

```python
import asyncio
import random
from functools import wraps

def with_retry(config: RetryConfig):
    """Decorator for retry with backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    if attempt == config.max_attempts - 1:
                        raise

                    delay = _calculate_delay(config, attempt)

                    logger.warning(
                        "retry_attempt",
                        attempt=attempt + 1,
                        max_attempts=config.max_attempts,
                        delay_ms=delay,
                        error=str(e),
                    )

                    await asyncio.sleep(delay / 1000)

            raise last_error

        return wrapper
    return decorator

def _calculate_delay(config: RetryConfig, attempt: int) -> int:
    """Calculate delay with backoff and jitter."""
    if config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay_ms * (attempt + 1)
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay_ms * (2 ** attempt)
    else:
        delay = 0

    delay = min(delay, config.max_delay_ms)

    if config.jitter:
        delay = delay * (0.5 + random.random())

    return int(delay)

# Usage
class EmbeddingService:
    @with_retry(RETRY_CONFIGS["embedding"])
    async def embed(self, text: str) -> list[float]:
        return await self._client.embed(text)
```

---

## Circuit Breaker

### Circuit Breaker Pattern

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls."""
    name: str
    failure_threshold: int = 5
    recovery_timeout: timedelta = timedelta(seconds=30)
    half_open_requests: int = 3

    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    last_failure: datetime | None = field(default=None)
    half_open_successes: int = field(default=0)

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_try_recovery():
                self.state = CircuitState.HALF_OPEN
                self.half_open_successes = 0
            else:
                raise CircuitOpenError(self.name)

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            raise

    def _should_try_recovery(self) -> bool:
        if self.last_failure is None:
            return True
        return datetime.utcnow() - self.last_failure > self.recovery_timeout

    def _on_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_requests:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("circuit_closed", circuit=self.name)
        else:
            self.failure_count = 0

    def _on_failure(self) -> None:
        self.failure_count += 1
        self.last_failure = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("circuit_reopened", circuit=self.name)

        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "circuit_opened",
                circuit=self.name,
                failures=self.failure_count,
            )

class CircuitOpenError(InfrastructureError):
    def __init__(self, circuit_name: str):
        super().__init__(
            message=f"Circuit {circuit_name} is open",
            code="CIRCUIT_OPEN",
            details={"circuit": circuit_name},
        )
```

### Usage with External Services

```python
class VoyageAIAdapter:
    """Adapter for Voyage AI embedding service."""

    def __init__(self):
        self._circuit = CircuitBreaker(
            name="voyage_ai",
            failure_threshold=5,
            recovery_timeout=timedelta(seconds=60),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._circuit.call(
            self._do_embed,
            texts,
        )

    async def _do_embed(self, texts: list[str]) -> list[list[float]]:
        # Actual API call
        response = await self._client.embeddings.create(
            input=texts,
            model="voyage-large-2",
        )
        return [r.embedding for r in response.data]
```

---

## Graceful Degradation

### Fallback Strategies

```python
class QueryService:
    """Query service with graceful degradation."""

    async def search(
        self,
        query: str,
        scope: SearchScope,
    ) -> SearchResults:
        results = SearchResults()

        # Try vector search with fallback
        try:
            results.vector_results = await self._vector_search(query)
        except ExternalServiceError:
            logger.warning("vector_search_degraded")
            results.degraded_sources.append("vector")

        # Try BM25 search with fallback
        try:
            results.bm25_results = await self._bm25_search(query)
        except DatabaseError:
            logger.warning("bm25_search_degraded")
            results.degraded_sources.append("bm25")

        # Try graph search with fallback
        try:
            results.graph_results = await self._graph_search(query)
        except ExternalServiceError:
            logger.warning("graph_search_degraded")
            results.degraded_sources.append("graph")

        # Must have at least one source
        if not results.has_any_results():
            raise SearchUnavailableError()

        return results
```

---

## Error Monitoring

### Error Metrics

```python
from prometheus_client import Counter, Histogram

error_counter = Counter(
    "{Project}_errors_total",
    "Total number of errors",
    ["error_code", "context", "severity"],
)

error_duration = Histogram(
    "{Project}_error_duration_seconds",
    "Time spent handling errors",
    ["error_code"],
)

class ErrorTracker:
    """Track error metrics for monitoring."""

    def track(self, error: {Project}Error, context: str) -> None:
        severity = self._get_severity(error)
        error_counter.labels(
            error_code=error.code,
            context=context,
            severity=severity,
        ).inc()

    def _get_severity(self, error: {Project}Error) -> str:
        match error:
            case ValidationError():
                return "info"
            case AuthorizationError():
                return "warning"
            case InfrastructureError():
                return "error"
            case _:
                return "error"
```

---

## See Also

- [Observability](con-observability.md) - Error logging and tracing
- [Testing Strategy](con-testing-strategy.md) - Testing error paths
- [Quality Approach](../04-solution-strategy/con-quality-approach.md)
