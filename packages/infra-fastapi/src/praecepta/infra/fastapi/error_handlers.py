"""RFC 7807 Problem Details exception handlers for FastAPI.

This module provides exception handlers that translate domain exceptions
into standardized HTTP responses following RFC 7807 Problem Details for
HTTP APIs. All handlers return responses with Content-Type: application/problem+json.

Usage:
    from praecepta.infra.fastapi.error_handlers import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, Field

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from praecepta.foundation.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    FeatureDisabledError,
    NotFoundError,
    ResourceLimitExceededError,
    ValidationError,
)

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response model.

    Standard fields:
    - type: URI reference identifying the problem type
    - title: Short human-readable summary
    - status: HTTP status code
    - detail: Human-readable explanation
    - instance: URI reference to specific occurrence

    Extension fields:
    - error_code: Machine-readable error code for client handling
    - context: Structured debugging information
    - correlation_id: Request correlation ID (5xx errors only)
    """

    type: str = Field(
        ...,
        description="URI reference identifying problem type",
        examples=["/errors/not-found", "/errors/validation-error"],
    )
    title: str = Field(
        ...,
        description="Short human-readable summary",
        examples=["Resource Not Found", "Validation Error"],
    )
    status: int = Field(
        ...,
        ge=400,
        le=599,
        description="HTTP status code",
    )
    detail: str = Field(
        ...,
        description="Human-readable explanation",
    )
    instance: str | None = Field(
        default=None,
        description="URI reference to specific occurrence (request path)",
    )
    error_code: str | None = Field(
        default=None,
        description="Machine-readable error code",
        examples=["RESOURCE_NOT_FOUND", "VALIDATION_ERROR"],
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Structured debugging information",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Request correlation ID for support requests",
    )


# Patterns for sensitive data
_SENSITIVE_PATTERNS = [
    (
        re.compile(r"postgresql://[^@]*@[^/\s]*"),
        "postgresql://[REDACTED]@[REDACTED]",
    ),
    (
        re.compile(r"password\s*=\s*['\"]?[^'\"\s]+['\"]?", re.IGNORECASE),
        "password=[REDACTED]",
    ),
    (
        re.compile(r"secret\s*=\s*['\"]?[^'\"\s]+['\"]?", re.IGNORECASE),
        "secret=[REDACTED]",
    ),
    (
        re.compile(r"token\s*=\s*['\"]?[^'\"\s]+['\"]?", re.IGNORECASE),
        "token=[REDACTED]",
    ),
    (
        re.compile(r"api[_-]?key\s*=\s*['\"]?[^'\"\s]+['\"]?", re.IGNORECASE),
        "api_key=[REDACTED]",
    ),
]


def _create_problem_response(problem: ProblemDetail) -> JSONResponse:
    """Create JSONResponse with RFC 7807 content type.

    Args:
        problem: ProblemDetail model instance

    Returns:
        JSONResponse with problem+json content type and proper status
    """
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _get_correlation_id() -> str:
    """Get correlation ID from request context.

    Returns the request ID set by RequestIdMiddleware, or "unknown"
    if called outside of request context.

    Returns:
        Correlation ID string
    """
    try:
        from praecepta.infra.fastapi.middleware.request_id import get_request_id

        request_id = get_request_id()
        return request_id if request_id else "unknown"
    except ImportError:
        return "unknown"


def _sanitize_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize context dictionary for safe inclusion in responses.

    - Converts UUIDs and datetimes to strings
    - Removes or redacts sensitive values (passwords, tokens, etc.)
    - Handles non-serializable types gracefully

    Args:
        context: Context dictionary from exception

    Returns:
        Sanitized context dictionary, or None if input is None
    """
    if context is None:
        return None

    sanitized = {}
    for key, value in context.items():
        # Skip sensitive keys
        if _is_sensitive_key(key):
            continue

        # Convert types
        sanitized[key] = _sanitize_value(value)

    return sanitized if sanitized else None


def _is_sensitive_key(key: str) -> bool:
    """Check if key name indicates sensitive data."""
    sensitive_keys = {"password", "secret", "token", "api_key", "apikey", "credential"}
    return key.lower() in sensitive_keys


def _sanitize_value(value: Any) -> Any:
    """Sanitize a single value for JSON serialization."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return _redact_sensitive_strings(value)
    if isinstance(value, dict):
        return _sanitize_context(value)
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]
    # For other types, convert to string if not JSON-serializable
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _redact_sensitive_strings(text: str) -> str:
    """Redact sensitive patterns from string values."""
    result = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Translate NotFoundError to 404 with RFC 7807 problem details.

    Args:
        request: FastAPI request object
        exc: NotFoundError instance with resource_type and resource_id

    Returns:
        JSONResponse with 404 status and problem details
    """
    problem = ProblemDetail(
        type="/errors/not-found",
        title="Resource Not Found",
        status=404,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context),
    )
    return _create_problem_response(problem)


async def validation_error_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """Translate ValidationError to 422 with field-level details.

    Args:
        request: FastAPI request object
        exc: ValidationError instance with field and reason

    Returns:
        JSONResponse with 422 status and problem details
    """
    problem = ProblemDetail(
        type="/errors/validation-error",
        title="Validation Error",
        status=422,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context),
    )
    return _create_problem_response(problem)


async def conflict_error_handler(
    request: Request,
    exc: ConflictError,
) -> JSONResponse:
    """Translate ConflictError to 409 with conflict context.

    Args:
        request: FastAPI request object
        exc: ConflictError instance with reason and version context

    Returns:
        JSONResponse with 409 status and problem details
    """
    problem = ProblemDetail(
        type="/errors/conflict",
        title="Conflict",
        status=409,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context),
    )
    return _create_problem_response(problem)


async def feature_disabled_handler(
    request: Request,
    exc: FeatureDisabledError,
) -> JSONResponse:
    """Translate FeatureDisabledError to 403 Forbidden with RFC 7807 details.

    Response includes the feature_key in the context so clients can
    identify which feature gate blocked their request.

    Args:
        request: FastAPI request object.
        exc: FeatureDisabledError with feature_key and tenant_id.

    Returns:
        JSONResponse with 403 status and problem details.
    """
    problem = ProblemDetail(
        type="/errors/feature-disabled",
        title="Feature Disabled",
        status=403,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context),
    )
    return _create_problem_response(problem)


async def resource_limit_handler(
    request: Request,
    exc: ResourceLimitExceededError,
) -> JSONResponse:
    """Translate ResourceLimitExceededError to 429 with RFC 7807 + rate-limit headers.

    Response includes:
    - RFC 7807 problem details body with resource/limit/current fields
    - X-RateLimit-Limit header: maximum allowed value
    - X-RateLimit-Remaining header: available capacity (always 0 on 429)
    - Retry-After header: suggested retry delay (3600 seconds = 1 hour)

    Args:
        request: FastAPI request object.
        exc: ResourceLimitExceededError with resource, limit, current.

    Returns:
        JSONResponse with 429 status, problem details, and rate-limit headers.
    """
    problem = ProblemDetail(
        type="/errors/resource-limit-exceeded",
        title="Resource Limit Exceeded",
        status=429,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context),
    )

    response = _create_problem_response(problem)
    response.headers["X-RateLimit-Limit"] = str(exc.limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, exc.limit - exc.current))
    response.headers["Retry-After"] = "3600"
    return response


async def authentication_error_handler(
    request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    """Translate AuthenticationError to 401 with WWW-Authenticate header.

    Per RFC 6750 Section 3, all 401 responses for Bearer token errors
    MUST include a WWW-Authenticate header.

    Args:
        request: FastAPI request object.
        exc: AuthenticationError instance with auth_error and error_code.

    Returns:
        JSONResponse with 401 status, problem details, and WWW-Authenticate header.
    """
    problem = ProblemDetail(
        type=f"/errors/{exc.error_code.lower().replace('_', '-')}",
        title="Unauthorized",
        status=401,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
    )
    response = _create_problem_response(problem)
    response.headers["WWW-Authenticate"] = f'Bearer realm="API", error="{exc.auth_error}"'
    return response


async def authorization_error_handler(
    request: Request,
    exc: AuthorizationError,
) -> JSONResponse:
    """Translate AuthorizationError to 403 Forbidden.

    Args:
        request: FastAPI request object.
        exc: AuthorizationError instance.

    Returns:
        JSONResponse with 403 status and problem details.
    """
    problem = ProblemDetail(
        type="/errors/forbidden",
        title="Forbidden",
        status=403,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context) if exc.context else None,
    )
    return _create_problem_response(problem)


async def domain_error_handler(
    request: Request,
    exc: DomainError,
) -> JSONResponse:
    """Translate generic DomainError to 400 Bad Request.

    This is the fallback handler for domain errors that don't have
    a more specific handler (NotFoundError, ValidationError, ConflictError).

    Args:
        request: FastAPI request object
        exc: DomainError instance

    Returns:
        JSONResponse with 400 status and problem details
    """
    problem = ProblemDetail(
        type="/errors/domain-error",
        title="Bad Request",
        status=400,
        detail=str(exc),
        instance=str(request.url.path),
        error_code=exc.error_code,
        context=_sanitize_context(exc.context),
    )
    return _create_problem_response(problem)


async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Translate Pydantic RequestValidationError to 422.

    This handles FastAPI's built-in validation of request bodies,
    query parameters, and path parameters.

    Args:
        request: FastAPI request object
        exc: RequestValidationError from Pydantic validation

    Returns:
        JSONResponse with 422 status and validation error details
    """
    # Format Pydantic errors for client consumption
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )

    problem = ProblemDetail(
        type="/errors/request-validation-error",
        title="Request Validation Error",
        status=422,
        detail="Request validation failed",
        instance=str(request.url.path),
        error_code="REQUEST_VALIDATION_ERROR",
        context={"errors": errors},
    )
    return _create_problem_response(problem)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Logs full exception details for debugging but returns a sanitized
    response to the client. Includes correlation ID for support requests.

    In debug mode (DEBUG=true), includes exception type and message.
    In production, returns generic error message only.

    Args:
        request: FastAPI request object
        exc: Any unhandled exception

    Returns:
        JSONResponse with 500 status and sanitized problem details
    """
    correlation_id = _get_correlation_id()

    # Log full exception for debugging
    logger.exception(
        "unhandled_exception",
        extra={
            "correlation_id": correlation_id,
            "path": str(request.url.path),
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
    )

    # Build response based on debug mode
    debug_mode = getattr(request.app, "debug", False)

    if debug_mode:
        detail = f"{type(exc).__name__}: {exc}"
        context: dict[str, Any] | None = {"exception_type": type(exc).__name__}
    else:
        detail = "An internal error occurred. Please contact support with the correlation ID."
        context = None

    problem = ProblemDetail(
        type="/errors/internal-error",
        title="Internal Server Error",
        status=500,
        detail=detail,
        instance=str(request.url.path),
        error_code="INTERNAL_ERROR",
        context=context,
        correlation_id=correlation_id,
    )
    return _create_problem_response(problem)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on FastAPI application.

    Handlers are registered from most specific to least specific:
    1. AuthenticationError -> 401
    2. AuthorizationError -> 403
    3. NotFoundError -> 404
    4. ValidationError -> 422
    5. ConflictError -> 409
    6. FeatureDisabledError -> 403
    7. ResourceLimitExceededError -> 429
    8. DomainError -> 400 (base class fallback)
    9. RequestValidationError -> 422 (Pydantic)
    10. Exception -> 500 (catch-all)

    Call this function after middleware configuration and before
    including routers in create_app().

    Args:
        app: FastAPI application instance

    Example:
        >>> from fastapi import FastAPI
        >>> from praecepta.infra.fastapi.error_handlers import (
        ...     register_exception_handlers,
        ... )
        >>> app = FastAPI()
        >>> register_exception_handlers(app)
    """
    # Specific domain exceptions (most specific first)
    # Note: Type ignores needed due to Starlette's overly strict handler typing
    # The handlers work correctly at runtime with their specific exception types

    # Auth exceptions MUST be registered before DomainError catch-all
    app.add_exception_handler(
        AuthenticationError,
        authentication_error_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        AuthorizationError,
        authorization_error_handler,  # type: ignore[arg-type]
    )

    app.add_exception_handler(
        NotFoundError,
        not_found_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        ValidationError,
        validation_error_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        ConflictError,
        conflict_error_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        FeatureDisabledError,
        feature_disabled_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        ResourceLimitExceededError,
        resource_limit_handler,  # type: ignore[arg-type]
    )

    # Base domain exception (fallback for unlisted domain errors)
    app.add_exception_handler(
        DomainError,
        domain_error_handler,  # type: ignore[arg-type]
    )

    # Pydantic validation errors
    app.add_exception_handler(
        RequestValidationError,
        request_validation_handler,  # type: ignore[arg-type]
    )

    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, unhandled_exception_handler)
