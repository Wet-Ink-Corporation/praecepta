"""API key generation and hashing utilities.

Separated from domain layer because key generation is infrastructure
concern (uses secrets module, bcrypt). Domain only sees key_id + key_hash.

Implements the APIKeyGeneratorPort protocol from
praecepta.foundation.domain.ports.
"""

from __future__ import annotations

import secrets

import bcrypt

from praecepta.foundation.domain.agent_value_objects import DEFAULT_API_KEY_PREFIX

# Key format: {prefix}{key_id}{secret}
# key_id: 8 chars (for lookup/identification)
# secret: 43 chars from token_urlsafe(32) (256-bit entropy)
_KEY_ID_LENGTH = 8
_SECRET_BYTES = 32
_BCRYPT_ROUNDS = 12


class APIKeyGenerator:
    """API key generator implementing APIKeyGeneratorPort.

    Generates keys with a configurable prefix (default ``pk_``),
    extracts key parts, and hashes secrets using bcrypt.

    Args:
        prefix: Key prefix string (default: ``pk_``).

    Example:
        >>> gen = APIKeyGenerator()
        >>> key_id, full_key = gen.generate_api_key()
        >>> full_key.startswith("pk_")
        True
    """

    def __init__(self, prefix: str = DEFAULT_API_KEY_PREFIX) -> None:
        self._prefix = prefix

    def generate_api_key(self) -> tuple[str, str]:
        """Generate API key with configured prefix.

        Returns:
            (key_id, full_key) where full_key = {prefix}{key_id}{secret}

        Example:
            >>> gen = APIKeyGenerator()
            >>> key_id, full_key = gen.generate_api_key()
            >>> full_key.startswith("pk_")
            True
            >>> len(full_key) >= 55
            True
        """
        key_id = secrets.token_urlsafe(6)[:_KEY_ID_LENGTH]
        secret = secrets.token_urlsafe(_SECRET_BYTES)
        full_key = f"{self._prefix}{key_id}{secret}"
        return key_id, full_key

    def extract_key_parts(self, full_key: str) -> tuple[str, str] | None:
        """Parse API key into (key_id, secret).

        Args:
            full_key: Full API key string ({prefix}{key_id}{secret}).

        Returns:
            (key_id, secret) or None if format is invalid.

        Example:
            >>> gen = APIKeyGenerator()
            >>> key_id, full_key = gen.generate_api_key()
            >>> parts = gen.extract_key_parts(full_key)
            >>> parts is not None
            True
            >>> parts[0] == key_id
            True
        """
        if not full_key.startswith(self._prefix):
            return None
        body = full_key[len(self._prefix) :]
        if len(body) < _KEY_ID_LENGTH + 1:
            return None
        key_id = body[:_KEY_ID_LENGTH]
        secret = body[_KEY_ID_LENGTH:]
        return key_id, secret

    def hash_secret(self, secret: str) -> str:
        """Hash API key secret with bcrypt.

        Args:
            secret: The secret portion of the key (after prefix + key_id).

        Returns:
            Bcrypt hash string (includes salt, starts with $2b$).

        Example:
            >>> gen = APIKeyGenerator()
            >>> key_hash = gen.hash_secret("test_secret_with_high_entropy")
            >>> key_hash.startswith("$2b$")
            True
        """
        return bcrypt.hashpw(
            secret.encode("utf-8"),
            bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
        ).decode("utf-8")

    def verify_secret(self, secret: str, key_hash: str) -> bool:
        """Verify API key secret against stored bcrypt hash.

        Timing-safe comparison (bcrypt inherently constant-time).

        Args:
            secret: The secret portion of the API key.
            key_hash: Bcrypt hash stored in aggregate/projection.

        Returns:
            True if secret matches hash, False otherwise.

        Example:
            >>> gen = APIKeyGenerator()
            >>> key_hash = gen.hash_secret("test_secret")
            >>> gen.verify_secret("test_secret", key_hash)
            True
            >>> gen.verify_secret("wrong_secret", key_hash)
            False
        """
        return bcrypt.checkpw(secret.encode("utf-8"), key_hash.encode("utf-8"))
