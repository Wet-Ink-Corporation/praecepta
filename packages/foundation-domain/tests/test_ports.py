"""Tests for port protocol conformance."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from praecepta.foundation.domain.ports.api_key_generator import APIKeyGeneratorPort
from praecepta.foundation.domain.ports.llm_service import LLMServicePort

if TYPE_CHECKING:
    from pydantic import BaseModel


class _FakeLLMService:
    """Fake LLM service that conforms to LLMServicePort protocol."""

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        return f"response to: {prompt}"

    def complete_structured(
        self,
        prompt: str,
        response_type: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> BaseModel:
        return response_type.model_validate({})  # type: ignore[return-value]


class _FakeAPIKeyGenerator:
    """Fake API key generator that conforms to APIKeyGeneratorPort protocol."""

    def generate_api_key(self) -> tuple[str, str]:
        return ("key123", "pk_key123_secret")

    def extract_key_parts(self, full_key: str) -> tuple[str, str] | None:
        if full_key.startswith("pk_"):
            parts = full_key.split("_", 2)
            if len(parts) == 3:
                return (parts[1], parts[2])
        return None

    def hash_secret(self, secret: str) -> str:
        return f"hashed:{secret}"


class _NotAPort:
    """Class that does NOT conform to any port protocol."""

    def unrelated_method(self) -> None:
        pass


@pytest.mark.unit
class TestLLMServicePort:
    """Tests for LLMServicePort protocol conformance."""

    def test_runtime_checkable(self) -> None:
        fake = _FakeLLMService()
        assert isinstance(fake, LLMServicePort)

    def test_non_conforming_rejected(self) -> None:
        non_port = _NotAPort()
        assert not isinstance(non_port, LLMServicePort)

    def test_complete_returns_string(self) -> None:
        fake = _FakeLLMService()
        result = fake.complete("hello")
        assert isinstance(result, str)


@pytest.mark.unit
class TestAPIKeyGeneratorPort:
    """Tests for APIKeyGeneratorPort protocol conformance."""

    def test_runtime_checkable(self) -> None:
        fake = _FakeAPIKeyGenerator()
        assert isinstance(fake, APIKeyGeneratorPort)

    def test_non_conforming_rejected(self) -> None:
        non_port = _NotAPort()
        assert not isinstance(non_port, APIKeyGeneratorPort)

    def test_generate_returns_tuple(self) -> None:
        fake = _FakeAPIKeyGenerator()
        key_id, full_key = fake.generate_api_key()
        assert isinstance(key_id, str)
        assert isinstance(full_key, str)

    def test_extract_key_parts_valid(self) -> None:
        fake = _FakeAPIKeyGenerator()
        result = fake.extract_key_parts("pk_key123_secret")
        assert result == ("key123", "secret")

    def test_extract_key_parts_invalid(self) -> None:
        fake = _FakeAPIKeyGenerator()
        result = fake.extract_key_parts("invalid-key")
        assert result is None

    def test_hash_secret_returns_string(self) -> None:
        fake = _FakeAPIKeyGenerator()
        result = fake.hash_secret("mysecret")
        assert isinstance(result, str)
