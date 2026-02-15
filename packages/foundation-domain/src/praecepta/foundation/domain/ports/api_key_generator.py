"""Port interface for API key generation.

This module defines the APIKeyGeneratorPort protocol for abstracting API key
creation and management, enabling domain logic to generate and validate keys
without coupling to specific hashing or key generation implementations.

Example:
    >>> from praecepta.foundation.domain.ports import APIKeyGeneratorPort
    >>> def provision_agent_key(gen: APIKeyGeneratorPort) -> tuple[str, str]:
    ...     key_id, full_key = gen.generate_api_key()
    ...     return key_id, full_key
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class APIKeyGeneratorPort(Protocol):
    """Port for API key generation and hashing.

    This protocol defines the contract for API key operations. Implementations
    handle key format, generation strategy, and hashing algorithm choices.

    The protocol is runtime_checkable to enable isinstance() verification
    in tests and dependency injection validation.

    Example:
        >>> class MyKeyGenerator:
        ...     def generate_api_key(self) -> tuple[str, str]:
        ...         return ("key123", "pk_key123_secretpart")
        ...
        ...     def extract_key_parts(self, full_key: str) -> tuple[str, str] | None:
        ...         # Parse and return (key_id, secret) or None
        ...         ...
        ...
        ...     def hash_secret(self, secret: str) -> str:
        ...         # Return hashed secret
        ...         ...
        >>> isinstance(MyKeyGenerator(), APIKeyGeneratorPort)
        True
    """

    def generate_api_key(self) -> tuple[str, str]:
        """Generate a new API key.

        Returns:
            A tuple of (key_id, full_plaintext_key) where key_id is used
            for lookup and full_plaintext_key is shown to the user once.
        """
        ...

    def extract_key_parts(self, full_key: str) -> tuple[str, str] | None:
        """Extract (key_id, secret) from a full key.

        Args:
            full_key: The full plaintext key string.

        Returns:
            A tuple of (key_id, secret) if the key format is valid,
            or None if the key format is invalid.
        """
        ...

    def hash_secret(self, secret: str) -> str:
        """Hash a key secret for storage.

        Args:
            secret: The plaintext secret portion to hash.

        Returns:
            The hash string suitable for persistent storage.
        """
        ...
