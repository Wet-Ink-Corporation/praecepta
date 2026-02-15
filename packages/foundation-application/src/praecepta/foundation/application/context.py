"""Request context management for cross-cutting concerns.

Provides a ContextVar-based mechanism for propagating request-scoped data
(tenant ID, user ID, correlation ID) across the call stack without explicit
parameter passing. Enables proper user attribution for audit trails by making
the acting user ID available to domain event handlers.

Principal context: A separate ContextVar for the authenticated principal,
managed independently by AuthMiddleware. This avoids modifying the frozen
RequestContext dataclass and decouples auth lifecycle from request context.

Usage:
    # In middleware (automatically populates context)
    from praecepta.foundation.application.context import (
        request_context,
        RequestContext,
    )

    # In handlers/services
    from praecepta.foundation.application.context import get_current_user_id

    user_id = get_current_user_id()  # Raises if no context

    # For authenticated principal
    from praecepta.foundation.application.context import get_current_principal

    principal = get_current_principal()  # Raises if no principal context
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextvars import Token
    from uuid import UUID

    from praecepta.foundation.domain.principal import Principal


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Immutable container for request-scoped context data.

    Attributes:
        tenant_id: The tenant identifier for multi-tenancy.
        user_id: The authenticated user performing the action.
        correlation_id: Unique ID for distributed tracing.
    """

    tenant_id: str
    user_id: UUID
    correlation_id: str


# ContextVar for request-scoped data - None when no request is active
request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


class NoRequestContextError(RuntimeError):
    """Raised when request context is accessed outside of a request."""

    def __init__(self) -> None:
        super().__init__(
            "No request context available. "
            "Ensure this code is called within an HTTP request with context middleware."
        )


def get_current_context() -> RequestContext:
    """Get the current request context.

    Returns:
        The active RequestContext.

    Raises:
        NoRequestContextError: If called outside of a request context.
    """
    ctx = request_context.get()
    if ctx is None:
        raise NoRequestContextError()
    return ctx


def get_current_tenant_id() -> str:
    """Get the current tenant ID from request context.

    Returns:
        The tenant ID for the current request.

    Raises:
        NoRequestContextError: If called outside of a request context.
    """
    return get_current_context().tenant_id


def get_current_user_id() -> UUID:
    """Get the current user ID from request context.

    Returns:
        The UUID of the authenticated user performing the action.

    Raises:
        NoRequestContextError: If called outside of a request context.
    """
    return get_current_context().user_id


def get_current_correlation_id() -> str:
    """Get the current correlation ID for distributed tracing.

    Returns:
        The correlation ID for the current request.

    Raises:
        NoRequestContextError: If called outside of a request context.
    """
    return get_current_context().correlation_id


def set_request_context(
    tenant_id: str,
    user_id: UUID,
    correlation_id: str,
) -> Token[RequestContext | None]:
    """Set the request context for the current async task.

    Should be called by middleware at the start of request handling.
    Returns a token that must be used to reset the context.

    Args:
        tenant_id: The tenant identifier.
        user_id: The authenticated user's UUID.
        correlation_id: The correlation ID for tracing.

    Returns:
        Token for resetting the context via request_context.reset().
    """
    ctx = RequestContext(
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
    )
    return request_context.set(ctx)


def clear_request_context(token: Token[RequestContext | None]) -> None:
    """Reset the request context using the provided token.

    Should be called by middleware after request handling completes.

    Args:
        token: The token returned from set_request_context.
    """
    request_context.reset(token)


# ---------------------------------------------------------------------------
# Principal context
# ---------------------------------------------------------------------------
# Separate ContextVar for the authenticated principal. NOT part of
# RequestContext to avoid breaking the frozen dataclass contract and to
# allow independent lifecycle management by AuthMiddleware.

_principal_context: ContextVar[Principal | None] = ContextVar("principal_context", default=None)


def set_principal_context(principal: Principal) -> Token[Principal | None]:
    """Set the authenticated principal for the current request.

    Called by AuthMiddleware after successful JWT validation and
    principal extraction. Returns a token for cleanup.

    Args:
        principal: Validated Principal extracted from JWT claims.

    Returns:
        Token for resetting the context.
    """
    return _principal_context.set(principal)


def clear_principal_context(token: Token[Principal | None]) -> None:
    """Reset the principal context using the provided token.

    Called in middleware finally block after request completes.

    Args:
        token: Token from set_principal_context.
    """
    _principal_context.reset(token)


def get_current_principal() -> Principal:
    """Get the authenticated principal from request context.

    Returns:
        The authenticated Principal for the current request.

    Raises:
        NoRequestContextError: If called outside authenticated request.
    """
    principal = _principal_context.get()
    if principal is None:
        raise NoRequestContextError()
    return principal


def get_optional_principal() -> Principal | None:
    """Get the authenticated principal if available, or None.

    Unlike get_current_principal(), this does not raise on missing context.
    Useful for endpoints that support both authenticated and unauthenticated
    access.

    Returns:
        The authenticated Principal, or None if not in authenticated context.
    """
    return _principal_context.get()
