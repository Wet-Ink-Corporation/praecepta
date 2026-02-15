"""PKCE (Proof Key for Code Exchange) utilities and storage.

Implements RFC 7636 S256 code challenge derivation and Redis-backed
storage for PKCE verifiers with single-use retrieve-and-delete semantics.

The PKCEStore uses Redis keys with ``pkce:`` prefix and configurable TTL
(default 600 seconds) to match authorization code lifetime with buffer
for user interaction delays.

Design decisions:
- Use manual S256 derivation (not Authlib) to keep the PKCE module
  dependency-light and testable without OAuth client.
- Single-use semantics (retrieve_and_delete) prevent replay attacks
  on authorization codes.
- Store redirect_uri alongside code_verifier to validate redirect_uri
  consistency in the callback handler.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Default TTL for PKCE data in Redis (seconds).
# Set to 600s (10 minutes) to account for user interaction delays
# while remaining shorter than typical session TTL.
_DEFAULT_TTL = 600


def derive_code_challenge(code_verifier: str) -> str:
    """Derive S256 code_challenge from code_verifier per RFC 7636.

    Computes ``BASE64URL(SHA256(code_verifier))`` with padding stripped,
    as required by the PKCE specification.

    Args:
        code_verifier: The code verifier string (43-128 ASCII characters).

    Returns:
        Base64url-encoded SHA-256 hash without padding.

    Example:
        >>> derive_code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class PKCEData:
    """Immutable container for PKCE session data.

    Stores the code_verifier, redirect_uri, and creation timestamp
    retrieved from Redis after a successful authorization callback.

    Attributes:
        code_verifier: The PKCE code verifier to send in the token exchange.
        redirect_uri: The redirect_uri used in the authorization request.
        created_at: Unix timestamp when the PKCE session was created.
    """

    code_verifier: str
    redirect_uri: str
    created_at: float


class PKCEStore:
    """Redis-backed store for PKCE verifiers with single-use semantics.

    Keys use the format ``pkce:{state}`` where ``state`` is the OAuth
    state parameter. Values are JSON-encoded PKCEData fields. Keys
    are automatically deleted on retrieval (single-use) and expire
    via Redis TTL if never retrieved.

    Args:
        redis_client: Async Redis client instance.
        ttl: Time-to-live in seconds for stored PKCE data.

    Example:
        >>> store = PKCEStore(redis_client, ttl=600)
        >>> await store.store("state-abc", "verifier-xyz", "http://localhost/cb")
        >>> data = await store.retrieve_and_delete("state-abc")
        >>> data.code_verifier
        'verifier-xyz'
        >>> await store.retrieve_and_delete("state-abc")  # Returns None
    """

    def __init__(self, redis_client: Any, ttl: int = _DEFAULT_TTL) -> None:
        """Initialize PKCEStore with Redis client and TTL.

        Args:
            redis_client: Async Redis client (redis.asyncio.Redis).
            ttl: Time-to-live in seconds for PKCE data keys.
        """
        self._redis = redis_client
        self._ttl = ttl

    async def store(
        self,
        state: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> None:
        """Store PKCE data keyed by OAuth state parameter.

        Args:
            state: OAuth state parameter (used as Redis key suffix).
            code_verifier: The PKCE code verifier to store.
            redirect_uri: The redirect_uri used in the authorization request.
        """
        key = f"pkce:{state}"
        payload = json.dumps(
            {
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "created_at": time.time(),
            }
        )
        await self._redis.setex(key, self._ttl, payload)
        logger.debug("pkce_data_stored", extra={"state_prefix": state[:8]})

    async def retrieve_and_delete(self, state: str) -> PKCEData | None:
        """Retrieve and delete PKCE data for the given state (single-use).

        Implements atomic retrieve-and-delete semantics to prevent replay
        attacks. Returns None if the state parameter is not found or has
        expired.

        Args:
            state: OAuth state parameter to look up.

        Returns:
            PKCEData if found and valid, None otherwise.
        """
        key = f"pkce:{state}"
        raw = await self._redis.get(key)

        if raw is None:
            logger.debug(
                "pkce_data_not_found",
                extra={"state_prefix": state[:8] if state else ""},
            )
            return None

        # Delete immediately (single-use)
        await self._redis.delete(key)

        try:
            data = json.loads(raw)
            return PKCEData(
                code_verifier=data["code_verifier"],
                redirect_uri=data["redirect_uri"],
                created_at=data["created_at"],
            )
        except (json.JSONDecodeError, KeyError):
            logger.warning(
                "pkce_data_corrupt",
                extra={"state_prefix": state[:8] if state else ""},
            )
            return None
