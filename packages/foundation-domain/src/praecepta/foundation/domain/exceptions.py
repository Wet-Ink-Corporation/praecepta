"""Domain exception hierarchy for type-safe error handling.

This module provides the base exception hierarchy for all domain errors.
Exceptions include structured error codes and context for consistent
API error handling and logging across bounded contexts.

Example:
    >>> from praecepta.foundation.domain.exceptions import NotFoundError
    >>> from uuid import UUID
    >>> raise NotFoundError("Resource", UUID("550e8400-e29b-41d4-a716-446655440000"))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "DomainError",
    "FeatureDisabledError",
    "InvalidStateTransitionError",
    "NotFoundError",
    "ResourceLimitExceededError",
    "ValidationError",
]


class DomainError(Exception):
    """Base class for all domain errors.

    Provides error code and structured context for debugging. All domain
    exceptions inherit from this class to enable consistent API error
    handling and logging.

    Attributes:
        error_code: Machine-readable error code for client handling.
        message: Human-readable error description.
        context: Structured debugging information (aggregate IDs, field names).

    Example:
        >>> raise DomainError("Operation failed", context={"aggregate_id": "123"})
        DomainError: Operation failed (aggregate_id=123)
    """

    error_code: str = "DOMAIN_ERROR"

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        """Initialize domain error with message and optional context.

        Args:
            message: Human-readable error description.
            context: Structured debugging information. Keys should be snake_case.
                     Values are typically strings, UUIDs, or primitive types.
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        """String representation including context for logging."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"{self.__class__.__name__}({self.message!r}, context={self.context!r})"


class NotFoundError(DomainError):
    """Raised when a requested resource does not exist.

    Maps to HTTP 404 Not Found. Use when aggregate lookup fails or
    entity cannot be found by identifier.

    Attributes:
        error_code: "RESOURCE_NOT_FOUND" (class constant).
        resource_type: Type of missing resource.
        resource_id: Identifier of missing resource.

    Example:
        >>> from uuid import UUID
        >>> raise NotFoundError("Resource", UUID("550e8400-e29b-41d4-a716-446655440000"))
        NotFoundError: Resource not found: 550e8400-e29b-41d4-a716-446655440000
    """

    error_code: str = "RESOURCE_NOT_FOUND"

    def __init__(
        self,
        resource_type: str,
        resource_id: UUID | str,
        **extra_context: Any,
    ) -> None:
        """Initialize not found error.

        Args:
            resource_type: Type of resource (e.g., "Tenant", "User").
            resource_id: Identifier of missing resource. UUID is converted to string.
            **extra_context: Additional debugging context (e.g., tenant_id, scope).
        """
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type} not found: {resource_id}"
        context = {
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            **extra_context,
        }
        super().__init__(message, context)


class ValidationError(DomainError):
    """Raised when input fails domain validation rules.

    Maps to HTTP 422 Unprocessable Entity. Use for domain rule violations
    on command input, not for Pydantic schema validation (which uses 400).

    Attributes:
        error_code: "VALIDATION_ERROR" (class constant).
        field: Field path that failed validation.
        reason: Human-readable validation failure reason.

    Example:
        >>> raise ValidationError("title", "Title must be at least 3 characters")
        ValidationError: Validation failed for 'title': Title must be at least 3 characters
    """

    error_code: str = "VALIDATION_ERROR"

    def __init__(
        self,
        field: str,
        reason: str,
        **extra_context: Any,
    ) -> None:
        """Initialize validation error.

        Args:
            field: Field path that failed validation. Supports dot notation
                   for nested fields (e.g., "metadata.source_url").
            reason: Human-readable validation failure reason.
            **extra_context: Additional debugging context.
        """
        self.field = field
        self.reason = reason
        message = f"Validation failed for '{field}': {reason}"
        context = {
            "field": field,
            "reason": reason,
            **extra_context,
        }
        super().__init__(message, context)


class ConflictError(DomainError):
    """Raised when operation conflicts with current system state.

    Maps to HTTP 409 Conflict. Use for optimistic concurrency violations,
    duplicate resource creation, or state transition conflicts.

    Attributes:
        error_code: "CONFLICT" (class constant).
        reason: Description of the conflict.

    Example:
        >>> raise ConflictError(
        ...     "Optimistic lock failure",
        ...     expected_version=5,
        ...     actual_version=7,
        ... )
        ConflictError: Conflict: Optimistic lock failure (expected_version=5, actual_version=7)
    """

    error_code: str = "CONFLICT"

    def __init__(
        self,
        reason: str,
        **context: Any,
    ) -> None:
        """Initialize conflict error.

        Args:
            reason: Description of conflict (e.g., "Optimistic lock failure",
                    "Resource already exists", "Invalid state transition").
            **context: Additional debugging context. For concurrency errors,
                       include expected_version and actual_version.
        """
        self.reason = reason
        message = f"Conflict: {reason}"
        super().__init__(message, context)


class InvalidStateTransitionError(ConflictError):
    """Raised when a state machine transition is not allowed.

    Maps to HTTP 409 Conflict. Inherits from ConflictError for
    consistent error handling at the API layer.

    Attributes:
        error_code: "INVALID_STATE_TRANSITION" (class constant).

    Example:
        >>> raise InvalidStateTransitionError(
        ...     "Cannot activate tenant: current state is SUSPENDED"
        ... )
    """

    error_code: str = "INVALID_STATE_TRANSITION"

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize invalid state transition error.

        Args:
            message: Description of the invalid transition attempt.
            **context: Additional debugging context (e.g., current_state, target_state).
        """
        super().__init__(message, **context)


class FeatureDisabledError(DomainError):
    """Raised when a feature flag is disabled for the requesting tenant.

    Maps to HTTP 403 Forbidden.

    Attributes:
        error_code: "FEATURE_DISABLED" (class constant).
        feature_key: The feature flag key that was checked.
        tenant_id: The tenant for which the feature is disabled.

    Example:
        >>> raise FeatureDisabledError("feature.graph_view", "acme-corp")
        FeatureDisabledError: Feature 'feature.graph_view' is not enabled for tenant 'acme-corp'
    """

    error_code: str = "FEATURE_DISABLED"

    def __init__(self, feature_key: str, tenant_id: str) -> None:
        """Initialize feature disabled error.

        Args:
            feature_key: ConfigKey string value (e.g., "feature.graph_view").
            tenant_id: Tenant slug identifier.
        """
        self.feature_key = feature_key
        self.tenant_id = tenant_id
        message = f"Feature '{feature_key}' is not enabled for tenant '{tenant_id}'"
        context = {"feature_key": feature_key, "tenant_id": tenant_id}
        super().__init__(message, context)


class AuthenticationError(DomainError):
    """Raised when authentication fails (missing, expired, invalid token).

    Maps to HTTP 401 Unauthorized. All 401 responses MUST include
    WWW-Authenticate header per RFC 6750.

    Attributes:
        error_code: Machine-readable error code (e.g., "MISSING_TOKEN").
        auth_error: RFC 6750 error code for WWW-Authenticate header.

    Example:
        >>> raise AuthenticationError("Token has expired", auth_error="invalid_token",
        ...     error_code="TOKEN_EXPIRED")
    """

    error_code: str = "AUTHENTICATION_ERROR"

    def __init__(
        self,
        message: str,
        auth_error: str = "invalid_token",
        error_code: str = "AUTHENTICATION_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Initialize authentication error.

        Args:
            message: Human-readable error description.
            auth_error: RFC 6750 error code for WWW-Authenticate header.
            error_code: Machine-readable error code for client handling.
            context: Structured debugging information.
        """
        self.auth_error = auth_error
        self.error_code = error_code
        super().__init__(message, context)


class AuthorizationError(DomainError):
    """Raised when authenticated principal lacks required permissions.

    Maps to HTTP 403 Forbidden. Used for valid credentials with insufficient
    claims or roles.

    Attributes:
        error_code: "AUTHORIZATION_ERROR" or more specific code.

    Example:
        >>> raise AuthorizationError("Missing required role: admin")
    """

    error_code: str = "AUTHORIZATION_ERROR"


class ResourceLimitExceededError(DomainError):
    """Raised when tenant exceeds a configured resource limit.

    Maps to HTTP 429 Too Many Requests.

    Attributes:
        error_code: "RESOURCE_LIMIT_EXCEEDED" (class constant).
        resource: Resource type key (e.g., "agents").
        limit: Maximum allowed count.
        current: Current usage count at time of check.

    Example:
        >>> raise ResourceLimitExceededError("agents", limit=100, current=100)
        ResourceLimitExceededError: Tenant has reached limit of 100 agents
    """

    error_code: str = "RESOURCE_LIMIT_EXCEEDED"

    def __init__(
        self,
        resource: str,
        limit: int,
        current: int,
        **extra_context: Any,
    ) -> None:
        """Initialize resource limit exceeded error.

        Args:
            resource: Resource type (e.g., "agents").
            limit: Maximum allowed value.
            current: Current usage count.
            **extra_context: Additional debugging context (e.g., tenant_id).
        """
        self.resource = resource
        self.limit = limit
        self.current = current
        message = f"Tenant has reached limit of {limit} {resource}"
        context = {
            "resource": resource,
            "limit": limit,
            "current": current,
            **extra_context,
        }
        super().__init__(message, context)
