"""Async HTTP client for OIDC / OAuth 2.0 token endpoints.

Provides typed methods for token exchange, token refresh, and token
revocation. All methods use httpx.AsyncClient with explicit timeouts
and structured error handling.

Design decisions:
- Per-request httpx.AsyncClient (not singleton) because OIDC token
  calls are infrequent (login, callback, refresh, logout). Creating
  a new AsyncClient per call avoids lifecycle management complexity.
  Upgrade to lifespan-scoped client if profiling shows TLS handshake
  overhead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
_DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """Parsed response from OIDC token endpoint.

    Attributes:
        access_token: JWT access token.
        refresh_token: Opaque refresh token (rotated on each use).
        id_token: OIDC ID token (may be None for refresh grants).
        expires_in: Access token TTL in seconds.
        token_type: Always "Bearer".
        user_id: User UUID from response (provider-specific field).
    """

    access_token: str
    refresh_token: str
    id_token: str | None
    expires_in: int
    token_type: str
    user_id: str | None


class TokenExchangeError(Exception):
    """Raised when OIDC token exchange fails.

    Attributes:
        status_code: HTTP status from the identity provider.
        error: OAuth 2.0 error code (e.g., "invalid_grant").
        error_description: Human-readable error from the provider.
    """

    def __init__(self, status_code: int, error: str, error_description: str) -> None:
        self.status_code = status_code
        self.error = error
        self.error_description = error_description
        super().__init__(f"Token exchange failed: {error} ({status_code})")


class OIDCTokenClient:
    """Async HTTP client for OIDC / OAuth 2.0 token endpoints.

    Supports both per-request and shared httpx.AsyncClient modes:
    - If ``client`` is provided, it is reused across calls (caller manages lifecycle).
    - If ``client`` is omitted, an internal client is created lazily on first use.
      Call :meth:`aclose` to release the internal client when done.

    Args:
        base_url: Identity provider base URL (e.g., "https://auth.example.com").
        client_id: OAuth application client_id.
        client_secret: OAuth application client_secret.
        timeout: HTTP request timeout in seconds.
        client: Optional shared httpx.AsyncClient instance.
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._external_client = client is not None
        self._client: httpx.AsyncClient | None = client

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> TokenResponse:
        """Exchange authorization code for tokens (PKCE).

        Args:
            code: Authorization code from callback query parameter.
            code_verifier: PKCE verifier retrieved from store.
            redirect_uri: Must match the value used in authorization request.

        Returns:
            TokenResponse with access_token, refresh_token, etc.

        Raises:
            TokenExchangeError: On 4xx/5xx from identity provider.
            httpx.ConnectError: On network failure.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code_verifier": code_verifier,
        }
        return await self._token_request(data)

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Exchange refresh token for new token pair.

        Args:
            refresh_token: Current refresh token.

        Returns:
            TokenResponse with new access_token and rotated refresh_token.

        Raises:
            TokenExchangeError: On 4xx/5xx (expired/revoked token).
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        return await self._token_request(data)

    async def revoke_token(self, token: str) -> None:
        """Revoke a refresh token (RFC 7009).

        Per RFC 7009, returns 200 even if token is already invalid.
        This method is best-effort: revocation failure does not raise.

        Args:
            token: Refresh token to revoke.
        """
        client = self._get_client()
        try:
            response = await client.post(
                f"{self._base_url}/oauth2/revoke",
                data={
                    "token": token,
                    "token_type_hint": "refresh_token",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": _FORM_CONTENT_TYPE},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "oidc_revoke_failed",
                extra={"status": exc.response.status_code},
            )
            # Do not raise -- revocation failure should not block logout
        except httpx.ConnectError:
            logger.error("oidc_revoke_connection_error")
            # Do not raise -- best-effort revocation

    def _get_client(self) -> httpx.AsyncClient:
        """Return the shared or lazily-created httpx.AsyncClient."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self) -> None:
        """Close the internal httpx.AsyncClient if we own it.

        No-op if the client was provided externally or not yet created.
        """
        if self._client is not None and not self._external_client:
            await self._client.aclose()
            self._client = None

    async def _token_request(self, data: dict[str, str]) -> TokenResponse:
        """Send POST to /oauth2/token endpoint.

        Args:
            data: Form data for the token request.

        Returns:
            Parsed TokenResponse.

        Raises:
            TokenExchangeError: On non-200 responses.
        """
        client = self._get_client()
        try:
            response = await client.post(
                f"{self._base_url}/oauth2/token",
                data=data,
                headers={"Content-Type": _FORM_CONTENT_TYPE},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            content_type = exc.response.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                body: dict[str, str] = exc.response.json()
            else:
                body = {}
            raise TokenExchangeError(
                status_code=exc.response.status_code,
                error=body.get("error", "unknown"),
                error_description=body.get("error_description", str(exc)),
            ) from exc

        body_json: dict[str, object] = response.json()
        raw_expires_in = body_json.get("expires_in")
        expires_in = int(str(raw_expires_in)) if raw_expires_in is not None else 3600
        return TokenResponse(
            access_token=str(body_json["access_token"]),
            refresh_token=str(body_json.get("refresh_token", "")),
            id_token=(str(body_json["id_token"]) if body_json.get("id_token") else None),
            expires_in=expires_in,
            token_type=str(body_json.get("token_type", "Bearer")),
            user_id=(str(body_json["userId"]) if body_json.get("userId") else None),
        )
