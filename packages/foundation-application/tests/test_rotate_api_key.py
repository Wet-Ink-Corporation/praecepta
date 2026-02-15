"""Unit tests for praecepta.foundation.application.rotate_api_key."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.foundation.application.rotate_api_key import (
    RotateAPIKeyCommand,
    RotateAPIKeyHandler,
    RotateAPIKeyResult,
)


def _make_key_generator() -> MagicMock:
    """Create a mock APIKeyGeneratorPort."""
    gen = MagicMock()
    gen.generate_api_key.return_value = (
        "newkey456",
        "pk_newkey456_newsecret",
    )
    gen.extract_key_parts.return_value = ("newkey456", "newsecret")
    gen.hash_secret.return_value = "hashed_newsecret"
    return gen


def _make_app() -> MagicMock:
    """Create a mock EventSourcedApplication."""
    app = MagicMock()
    agent = MagicMock()
    app.repository.get.return_value = agent
    return app


class TestRotateAPIKeyCommand:
    @pytest.mark.unit
    def test_construction(self) -> None:
        uid = uuid4()
        cmd = RotateAPIKeyCommand(agent_id=uid, requested_by="user|abc")
        assert cmd.agent_id == uid
        assert cmd.requested_by == "user|abc"

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        cmd = RotateAPIKeyCommand(agent_id=uuid4(), requested_by="u")
        with pytest.raises(AttributeError):
            cmd.requested_by = "other"  # type: ignore[misc]


class TestRotateAPIKeyResult:
    @pytest.mark.unit
    def test_construction(self) -> None:
        r = RotateAPIKeyResult(key_id="k1", api_key="pk_k1_secret")
        assert r.key_id == "k1"
        assert r.api_key == "pk_k1_secret"
        assert "Save this key" in r.warning

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        r = RotateAPIKeyResult(key_id="k1", api_key="pk_k1_secret")
        with pytest.raises(AttributeError):
            r.key_id = "other"  # type: ignore[misc]


class TestRotateAPIKeyHandler:
    @pytest.mark.unit
    def test_handle_returns_result(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = RotateAPIKeyHandler(app=app, key_generator=gen)

        cmd = RotateAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        result = handler.handle(cmd)

        assert isinstance(result, RotateAPIKeyResult)
        assert result.key_id == "newkey456"
        assert result.api_key == "pk_newkey456_newsecret"

    @pytest.mark.unit
    def test_handle_calls_generate_extract_hash(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = RotateAPIKeyHandler(app=app, key_generator=gen)

        cmd = RotateAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        handler.handle(cmd)

        gen.generate_api_key.assert_called_once()
        gen.extract_key_parts.assert_called_once_with("pk_newkey456_newsecret")
        gen.hash_secret.assert_called_once_with("newsecret")

    @pytest.mark.unit
    def test_handle_rotates_on_aggregate(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = RotateAPIKeyHandler(app=app, key_generator=gen)

        agent_id = uuid4()
        cmd = RotateAPIKeyCommand(agent_id=agent_id, requested_by="user|abc")
        handler.handle(cmd)

        agent = app.repository.get.return_value
        agent.request_rotate_api_key.assert_called_once_with("newkey456", "hashed_newsecret")

    @pytest.mark.unit
    def test_handle_saves_aggregate(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = RotateAPIKeyHandler(app=app, key_generator=gen)

        cmd = RotateAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        handler.handle(cmd)

        agent = app.repository.get.return_value
        app.save.assert_called_once_with(agent)

    @pytest.mark.unit
    def test_dependency_injection_of_key_generator(self) -> None:
        """Key generator is injected, not hard-imported."""
        app = _make_app()
        custom_gen = MagicMock()
        custom_gen.generate_api_key.return_value = (
            "custom_id",
            "custom_full_key",
        )
        custom_gen.extract_key_parts.return_value = (
            "custom_id",
            "custom_secret",
        )
        custom_gen.hash_secret.return_value = "custom_hash"

        handler = RotateAPIKeyHandler(app=app, key_generator=custom_gen)
        cmd = RotateAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        result = handler.handle(cmd)

        assert result.key_id == "custom_id"
        assert result.api_key == "custom_full_key"
