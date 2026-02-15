"""FastAPI dependency functions for authentication and authorization.

Provides Depends()-compatible functions for injecting principal context
into endpoint handlers.

Usage:
    from praecepta.infra.auth.dependencies import (
        CurrentPrincipal,
        get_current_principal,
        require_role,
    )

    @router.post("/blocks")
    def create_block(
        principal: CurrentPrincipal,
        ...
    ):
        # principal.tenant_id, principal.user_id available
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from praecepta.foundation.application.context import (
    get_current_principal as _get_principal_from_context,
)
from praecepta.foundation.domain.exceptions import AuthorizationError
from praecepta.foundation.domain.principal import Principal

if TYPE_CHECKING:
    from collections.abc import Callable


def get_current_principal() -> Principal:
    """FastAPI dependency that returns the authenticated principal.

    Reads from the principal ContextVar set by JWTAuthMiddleware.
    Sync function (not async) for minimal overhead.

    Returns:
        Principal extracted from validated JWT.

    Raises:
        NoRequestContextError: If called outside authenticated request.
    """
    return _get_principal_from_context()


# Type alias for cleaner endpoint signatures
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_role(role: str) -> Callable[..., None]:
    """Factory returning a dependency that enforces role membership.

    Args:
        role: Required role string (case-sensitive).

    Returns:
        FastAPI dependency function that raises AuthorizationError
        if principal lacks the required role.

    Usage:
        @router.delete("/admin/purge")
        def admin_purge(
            _: Annotated[None, Depends(require_role("admin"))],
            principal: CurrentPrincipal,
        ):
            ...
    """

    def _check_role(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> None:
        if role not in principal.roles:
            raise AuthorizationError(
                f"Required role '{role}' not found in principal roles",
                context={
                    "required_role": role,
                    "principal_id": principal.subject,
                },
            )

    return _check_role
