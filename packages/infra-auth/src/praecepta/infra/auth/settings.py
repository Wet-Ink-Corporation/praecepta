"""Authentication configuration settings.

Loaded from environment variables with AUTH_ prefix.
Follows Pydantic BaseSettings pattern for type-safe configuration.

Environment Variables:
    AUTH_ISSUER: OIDC issuer URL (required in non-bypass mode)
    AUTH_AUDIENCE: Expected JWT audience claim
    AUTH_JWKS_CACHE_TTL: JWKS key cache TTL in seconds
    AUTH_DEV_BYPASS: Skip JWT validation in development
    AUTH_OAUTH_CLIENT_ID: OAuth application client_id
    AUTH_OAUTH_CLIENT_SECRET: OAuth client secret
    AUTH_OAUTH_REDIRECT_URI: OAuth callback URL
    AUTH_OAUTH_SCOPES: OAuth scopes (space-separated)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Authentication configuration loaded from environment variables.

    Environment Variables:
        AUTH_ISSUER: OIDC issuer URL (required in non-bypass mode)
        AUTH_AUDIENCE: Expected JWT audience claim
        AUTH_JWKS_CACHE_TTL: JWKS key cache TTL in seconds
        AUTH_DEV_BYPASS: Skip JWT validation in development
        AUTH_OAUTH_CLIENT_ID: OAuth application client_id
        AUTH_OAUTH_CLIENT_SECRET: OAuth client secret (hidden from repr)
        AUTH_OAUTH_REDIRECT_URI: OAuth callback URL
        AUTH_OAUTH_SCOPES: OAuth scopes (space-separated)

    Example:
        >>> settings = AuthSettings()
        >>> settings.issuer
        ''
        >>> settings.audience
        'api'
        >>> settings.is_oauth_configured()
        False
    """

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    issuer: str = Field(
        default="",
        description="OIDC issuer URL",
    )
    audience: str = Field(
        default="api",
        description="Expected JWT audience claim",
    )
    jwks_cache_ttl: int = Field(
        default=300,
        ge=30,
        le=86400,
        description="JWKS key cache TTL in seconds",
    )
    dev_bypass: bool = Field(
        default=False,
        description="Skip JWT validation in development",
    )

    # OAuth 2.0 / OIDC fields
    oauth_client_id: str = Field(
        default="",
        description="OAuth application client_id for OAuth flows",
    )
    oauth_client_secret: str = Field(
        default="",
        repr=False,  # Security: never log client secret
        description="OAuth application client_secret",
    )
    oauth_redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        description="OAuth callback URL registered with identity provider",
    )
    oauth_scopes: str = Field(
        default="openid email profile",
        description="OAuth scopes requested during authorization",
    )

    def validate_oauth_config(self) -> None:
        """Validate OAuth configuration completeness.

        Raises:
            ValueError: If OAuth configuration is incomplete or invalid.
        """
        if not self.oauth_client_id:
            raise ValueError("AUTH_OAUTH_CLIENT_ID is required for OAuth flows")

        if not self.oauth_client_secret:
            raise ValueError("AUTH_OAUTH_CLIENT_SECRET is required for OAuth flows")

        if not self.oauth_redirect_uri:
            raise ValueError("AUTH_OAUTH_REDIRECT_URI is required for OAuth flows")

        # Validate redirect_uri format
        if not self.oauth_redirect_uri.startswith(
            "http://"
        ) and not self.oauth_redirect_uri.startswith("https://"):
            raise ValueError("AUTH_OAUTH_REDIRECT_URI must be a valid HTTP(S) URL")

        # Validate scopes format
        if not self.oauth_scopes or not isinstance(self.oauth_scopes, str):
            raise ValueError("AUTH_OAUTH_SCOPES must be a space-separated string")

    def is_oauth_configured(self) -> bool:
        """Check if OAuth configuration is complete (non-throwing).

        Returns:
            True if all required OAuth fields are set.
        """
        return bool(self.oauth_client_id and self.oauth_client_secret and self.oauth_redirect_uri)


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    """Get singleton AuthSettings instance.

    Cached for performance - settings are loaded once per application lifecycle.
    Clear cache with ``get_auth_settings.cache_clear()`` for testing.

    Returns:
        AuthSettings instance with configuration from environment.
    """
    return AuthSettings()
