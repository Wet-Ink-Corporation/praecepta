"""FastAPI dependency for feature flag gating.

Provides ``require_feature()`` factory that creates endpoint dependencies
for gating access based on tenant feature flags.

Usage in endpoint::

    from praecepta.infra.fastapi.dependencies.feature_flags import require_feature

    @router.get("/graph")
    async def get_graph_view(
        _: Annotated[None, Depends(require_feature("feature.graph_view"))]
    ):
        # Endpoint only executes if feature is enabled for the requesting tenant
        ...
"""

# NOTE: Do NOT use ``from __future__ import annotations`` here.
# FastAPI dependency injection needs runtime-evaluable type annotations
# on the inner functions (``request: Request``) to resolve parameters.
# PEP 563 deferred evaluation breaks this under pytest --import-mode=importlib.

from collections.abc import Callable
from typing import Protocol

from fastapi import Request
from praecepta.foundation.application.context import get_current_tenant_id
from praecepta.foundation.domain import FeatureDisabledError


class FeatureChecker(Protocol):
    """Protocol for checking whether a feature is enabled for a tenant."""

    def __call__(self, tenant_id: str, feature_key: str) -> bool:
        """Check if a feature is enabled for a given tenant.

        Args:
            tenant_id: Tenant slug identifier.
            feature_key: The feature flag key string.

        Returns:
            True if the feature is enabled, False otherwise.
        """
        ...


def _get_feature_checker(request: Request) -> FeatureChecker:
    """Retrieve feature checker from FastAPI app state.

    Expects ``request.app.state.feature_checker`` to be set during
    lifespan startup.

    Args:
        request: FastAPI request with access to app state.

    Returns:
        Feature checker callable from app state.
    """
    return request.app.state.feature_checker  # type: ignore[no-any-return]


def require_feature(
    feature_key: str,
    *,
    checker_getter: Callable[[Request], FeatureChecker] | None = None,
) -> Callable[..., None]:
    """Create a FastAPI dependency that gates endpoint access on a feature flag.

    Returns a dependency function that:
    1. Reads tenant_id from request context (set by RequestContextMiddleware)
    2. Reads feature checker from app state (or custom getter)
    3. Evaluates the feature flag
    4. Raises FeatureDisabledError (-> 403) if the feature is disabled

    Args:
        feature_key: The feature flag key string to check.
        checker_getter: Optional callable to retrieve the FeatureChecker
            from the request. Defaults to reading from
            ``request.app.state.feature_checker``.

    Returns:
        FastAPI-compatible sync dependency function (returns None
        on success or raises FeatureDisabledError).
    """
    _get_checker = checker_getter or _get_feature_checker

    def _check_feature(
        request: Request,
    ) -> None:
        """Evaluate feature flag for current tenant.

        Raises:
            FeatureDisabledError: If feature is disabled for the tenant.
            NoRequestContextError: If called outside request context.
        """
        checker = _get_checker(request)
        tenant_id = get_current_tenant_id()
        enabled = checker(tenant_id, feature_key)
        if not enabled:
            raise FeatureDisabledError(feature_key, tenant_id)

    # Store metadata for introspection
    _check_feature.__qualname__ = f"require_feature({feature_key!r})._check_feature"

    return _check_feature
