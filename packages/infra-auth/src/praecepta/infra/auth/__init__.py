"""Praecepta Infra Auth -- JWT, JWKS, PKCE, auth middleware.

Provides JWKS discovery, JWT validation middleware, principal extraction,
PKCE utilities for OAuth 2.0 flows, OIDC HTTP client, API key generation,
and FastAPI dependency injection for authentication/authorization.
"""

from praecepta.infra.auth.api_key_generator import APIKeyGenerator
from praecepta.infra.auth.dependencies import (
    CurrentPrincipal,
    get_current_principal,
    require_role,
)
from praecepta.infra.auth.dev_bypass import resolve_dev_bypass
from praecepta.infra.auth.jwks import JWKSProvider
from praecepta.infra.auth.lifespan import lifespan_contribution
from praecepta.infra.auth.middleware.api_key_auth import APIKeyAuthMiddleware
from praecepta.infra.auth.middleware.jwt_auth import JWTAuthMiddleware
from praecepta.infra.auth.oidc_client import (
    OIDCTokenClient,
    TokenExchangeError,
    TokenResponse,
)
from praecepta.infra.auth.pkce import PKCEData, PKCEStore, derive_code_challenge
from praecepta.infra.auth.settings import AuthSettings, get_auth_settings

# Synthetic principal claims for development bypass.
# These values are intentionally non-production-like to prevent confusion.
DEV_BYPASS_CLAIMS: dict[str, object] = {
    "sub": "00000000-0000-0000-0000-000000000000",
    "tenant_id": "dev-tenant",
    "roles": ["admin"],
    "email": "dev-bypass@localhost",
    "iss": "dev-bypass",
    "aud": "api",
    "exp": 0,  # Sentinel: bypass never "expires" in dev mode
}

__all__ = [
    "DEV_BYPASS_CLAIMS",
    "APIKeyAuthMiddleware",
    "APIKeyGenerator",
    "AuthSettings",
    "CurrentPrincipal",
    "JWKSProvider",
    "JWTAuthMiddleware",
    "OIDCTokenClient",
    "PKCEData",
    "PKCEStore",
    "TokenExchangeError",
    "TokenResponse",
    "derive_code_challenge",
    "get_auth_settings",
    "get_current_principal",
    "lifespan_contribution",
    "require_role",
    "resolve_dev_bypass",
]
