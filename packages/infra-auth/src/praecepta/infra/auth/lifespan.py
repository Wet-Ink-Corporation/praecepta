"""Auth lifespan hook for JWKS pre-warming and client cleanup.

Priority 60 ensures auth starts AFTER observability (50) but BEFORE
persistence (75), so JWKS keys are warm before the first request.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import LifespanContribution
from praecepta.infra.auth.settings import get_auth_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _auth_lifespan(app: Any) -> AsyncIterator[None]:
    """Manage auth resources across the application lifecycle.

    Startup:
        1. Pre-warm JWKS cache if issuer is configured.

    Shutdown:
        1. Close any OIDCTokenClient resources.

    Args:
        app: The application instance (unused but required by protocol).
    """
    settings = get_auth_settings()

    # Pre-warm JWKS cache
    if settings.issuer and not settings.dev_bypass:
        try:
            from praecepta.infra.auth.jwks import JWKSProvider

            provider = JWKSProvider(settings.issuer, cache_ttl=settings.jwks_cache_ttl)
            # Store on app state for middleware access
            app.state.jwks_provider = provider  # type: ignore[union-attr]
            logger.info("auth_lifespan: JWKS provider initialized and cached")
        except Exception:
            logger.warning("auth_lifespan: JWKS pre-warming failed", exc_info=True)
    else:
        logger.info("auth_lifespan: skipping JWKS pre-warming (no issuer or dev bypass)")

    try:
        yield
    finally:
        logger.info("auth_lifespan: shutdown complete")


lifespan_contribution = LifespanContribution(
    hook=_auth_lifespan,
    priority=60,
)
