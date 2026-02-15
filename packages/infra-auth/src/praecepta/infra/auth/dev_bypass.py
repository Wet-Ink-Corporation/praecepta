"""Development mode authentication bypass resolution.

Provides a standalone function to determine whether dev bypass should be active,
with production safety checks and structured logging.

The bypass is used by JWTAuthMiddleware to inject synthetic DEV_BYPASS_CLAIMS
when no Authorization header is present.

Safety rules:
1. Production lockout: ENVIRONMENT=production ALWAYS disables bypass
2. Only active when explicitly requested via AUTH_DEV_BYPASS=true
3. Bypass only applies when Authorization header is absent (enforced in middleware)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def resolve_dev_bypass(requested: bool) -> bool:
    """Resolve whether development authentication bypass should be active.

    Evaluates the bypass request against the current runtime environment.
    Production environments ALWAYS block bypass regardless of the request flag.

    Args:
        requested: Whether bypass was requested via AUTH_DEV_BYPASS=true.

    Returns:
        True if bypass should be active, False otherwise.

    Side effects:
        - Logs WARNING when bypass is active in non-production environment.
        - Logs ERROR when bypass is requested but blocked in production.
    """
    if not requested:
        return False

    env = os.environ.get("ENVIRONMENT", "development")

    if env == "production":
        logger.error(
            "auth_dev_bypass_blocked",
            extra={
                "environment": env,
                "detail": (
                    "Authentication bypass was requested but blocked in production environment."
                ),
            },
        )
        return False

    logger.warning(
        "auth_dev_bypass_active",
        extra={
            "environment": env,
            "detail": ("Authentication bypass is enabled. Do not use in production."),
        },
    )
    return True
