"""Tests for APIKeyGenerator: generation, extraction, hashing, protocol conformance."""

from __future__ import annotations

import pytest

from praecepta.foundation.domain.ports import APIKeyGeneratorPort
from praecepta.infra.auth.api_key_generator import APIKeyGenerator


@pytest.mark.unit
class TestAPIKeyGenerator:
    """Test APIKeyGenerator key operations."""

    def test_generate_api_key_default_prefix(self) -> None:
        gen = APIKeyGenerator()
        key_id, full_key = gen.generate_api_key()
        assert full_key.startswith("pk_")
        assert len(key_id) == 8
        assert full_key[3:11] == key_id  # "pk_" is 3 chars, key_id is next 8

    def test_generate_api_key_custom_prefix(self) -> None:
        gen = APIKeyGenerator(prefix="test_")
        key_id, full_key = gen.generate_api_key()
        assert full_key.startswith("test_")
        assert full_key[5:13] == key_id

    def test_generate_api_key_sufficient_length(self) -> None:
        gen = APIKeyGenerator()
        _, full_key = gen.generate_api_key()
        # "pk_" (3) + key_id (8) + secret (43) = 54 minimum
        assert len(full_key) >= 54

    def test_extract_key_parts_valid(self) -> None:
        gen = APIKeyGenerator()
        key_id, full_key = gen.generate_api_key()
        parts = gen.extract_key_parts(full_key)
        assert parts is not None
        extracted_key_id, extracted_secret = parts
        assert extracted_key_id == key_id
        assert len(extracted_secret) > 0

    def test_extract_key_parts_wrong_prefix(self) -> None:
        gen = APIKeyGenerator()
        assert gen.extract_key_parts("wrong_prefix_key") is None

    def test_extract_key_parts_too_short(self) -> None:
        gen = APIKeyGenerator()
        assert gen.extract_key_parts("pk_short") is None

    def test_hash_secret_bcrypt_format(self) -> None:
        gen = APIKeyGenerator()
        key_hash = gen.hash_secret("test_secret_with_entropy")
        assert key_hash.startswith("$2b$")

    def test_verify_secret_correct(self) -> None:
        gen = APIKeyGenerator()
        secret = "my_secret_value_for_testing"
        key_hash = gen.hash_secret(secret)
        assert gen.verify_secret(secret, key_hash) is True

    def test_verify_secret_wrong(self) -> None:
        gen = APIKeyGenerator()
        key_hash = gen.hash_secret("correct_secret")
        assert gen.verify_secret("wrong_secret", key_hash) is False

    def test_roundtrip(self) -> None:
        """Full roundtrip: generate -> extract -> hash -> verify."""
        gen = APIKeyGenerator()
        key_id, full_key = gen.generate_api_key()
        parts = gen.extract_key_parts(full_key)
        assert parts is not None
        extracted_key_id, secret = parts
        assert extracted_key_id == key_id

        key_hash = gen.hash_secret(secret)
        assert gen.verify_secret(secret, key_hash) is True


@pytest.mark.unit
class TestAPIKeyGeneratorProtocol:
    """Test that APIKeyGenerator implements APIKeyGeneratorPort."""

    def test_implements_protocol(self) -> None:
        gen = APIKeyGenerator()
        assert isinstance(gen, APIKeyGeneratorPort)

    def test_protocol_generate(self) -> None:
        gen: APIKeyGeneratorPort = APIKeyGenerator()
        key_id, full_key = gen.generate_api_key()
        assert isinstance(key_id, str)
        assert isinstance(full_key, str)

    def test_protocol_extract(self) -> None:
        gen: APIKeyGeneratorPort = APIKeyGenerator()
        _, full_key = gen.generate_api_key()
        result = gen.extract_key_parts(full_key)
        assert result is not None

    def test_protocol_hash(self) -> None:
        gen: APIKeyGeneratorPort = APIKeyGenerator()
        hashed = gen.hash_secret("some_secret")
        assert isinstance(hashed, str)
