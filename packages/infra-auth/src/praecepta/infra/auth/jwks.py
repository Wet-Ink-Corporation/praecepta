"""JWKS provider for JWT signature verification key management.

Wraps PyJWT's PyJWKClient to provide:
- JWKS URI construction from OIDC issuer
- In-memory key caching with configurable TTL
- Automatic key refresh on kid mismatch (handles key rotation)
- Graceful degradation when JWKS endpoint is temporarily unavailable

Lifecycle: Created once during app lifespan startup, stored in app.state.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jwt import PyJWKClient

if TYPE_CHECKING:
    from jwt import PyJWK

logger = logging.getLogger(__name__)


class JWKSProvider:
    """JWKS key provider with caching and rotation support.

    Wraps PyJWKClient to provide:
    - OIDC discovery of jwks_uri from .well-known/openid-configuration
    - In-memory key caching with configurable TTL
    - Automatic key refresh on kid mismatch (key rotation)
    - Graceful degradation on JWKS endpoint unavailability

    Lifecycle: Created once during app lifespan startup, stored in app.state.

    Args:
        issuer_url: OIDC issuer base URL.
        cache_ttl: Key cache TTL in seconds (default 300).

    Raises:
        ValueError: If issuer_url is empty or invalid.

    Example:
        >>> provider = JWKSProvider("https://auth.example.com", cache_ttl=300)
        >>> signing_key = provider.get_signing_key_from_jwt(token)
        >>> claims = jwt.decode(token, signing_key.key, algorithms=["RS256"])
    """

    def __init__(self, issuer_url: str, cache_ttl: int = 300) -> None:
        """Initialize JWKS provider with issuer URL and cache TTL.

        Args:
            issuer_url: OIDC issuer base URL
                (e.g., "https://auth.example.com").
            cache_ttl: JWKS cache TTL in seconds (default: 300).

        Raises:
            ValueError: If issuer_url is empty.
        """
        if not issuer_url:
            raise ValueError("OIDC issuer URL is required for JWKS discovery")

        self._issuer_url = issuer_url.rstrip("/")
        self._cache_ttl = cache_ttl

        # Try OIDC discovery to get the authoritative JWKS URI.
        # Fall back to constructed URI if discovery fails (CF-19).
        self._jwks_uri = self._discover_jwks_uri() or (f"{self._issuer_url}/.well-known/jwks.json")

        # Initialize PyJWKClient with caching enabled.
        # PyJWKClient handles kid mismatch -> refresh -> retry internally.
        self._client = PyJWKClient(
            self._jwks_uri,
            cache_jwk_set=True,
            lifespan=cache_ttl,
        )

        logger.info(
            "jwks_provider_initialized",
            extra={
                "issuer": self._issuer_url,
                "jwks_uri": self._jwks_uri,
                "cache_ttl": cache_ttl,
            },
        )

    def _discover_jwks_uri(self) -> str | None:
        """Attempt OIDC discovery to resolve jwks_uri.

        Fetches the OpenID Connect discovery document from
        ``{issuer}/.well-known/openid-configuration`` and extracts ``jwks_uri``.
        Validates that the discovered issuer matches the configured issuer.

        Returns:
            Discovered JWKS URI, or ``None`` if discovery fails.
        """
        import httpx

        discovery_url = f"{self._issuer_url}/.well-known/openid-configuration"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(discovery_url)
                resp.raise_for_status()
                doc = resp.json()

            # Validate issuer match
            discovered_issuer = doc.get("issuer", "").rstrip("/")
            if discovered_issuer != self._issuer_url:
                logger.warning(
                    "oidc_discovery_issuer_mismatch",
                    extra={
                        "expected": self._issuer_url,
                        "discovered": discovered_issuer,
                    },
                )
                return None

            jwks_uri = doc.get("jwks_uri")
            if jwks_uri:
                logger.info(
                    "oidc_discovery_success",
                    extra={"jwks_uri": jwks_uri},
                )
                return str(jwks_uri)

            logger.warning("oidc_discovery_no_jwks_uri")
            return None
        except Exception:
            logger.debug(
                "oidc_discovery_failed",
                extra={"url": discovery_url},
                exc_info=True,
            )
            return None

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        """Retrieve the signing key for a JWT token.

        Extracts kid from the token header, looks up the key in cache,
        and refreshes from JWKS endpoint on cache miss. PyJWKClient
        handles the kid mismatch -> refresh -> retry internally.

        Args:
            token: Raw JWT string (not decoded).

        Returns:
            PyJWK signing key object with .key attribute for jwt.decode().

        Raises:
            PyJWKClientError: If key cannot be found after refresh.
            PyJWKClientConnectionError: If JWKS endpoint is unreachable.
        """
        return self._client.get_signing_key_from_jwt(token)

    @property
    def jwks_uri(self) -> str:
        """The discovered JWKS endpoint URI.

        Returns:
            JWKS URI string constructed from issuer URL.
        """
        return self._jwks_uri

    @property
    def issuer_url(self) -> str:
        """The configured OIDC issuer URL.

        Returns:
            Issuer URL string (without trailing slash).
        """
        return self._issuer_url
