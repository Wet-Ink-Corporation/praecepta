"""Unit tests for praecepta.foundation.application.issue_api_key."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.foundation.application.issue_api_key import (
    IssueAPIKeyCommand,
    IssueAPIKeyHandler,
)


def _make_key_generator() -> MagicMock:
    """Create a mock APIKeyGeneratorPort."""
    gen = MagicMock()
    gen.generate_api_key.return_value = (
        "key123",
        "pk_key123_secretpart",
    )
    gen.extract_key_parts.return_value = ("key123", "secretpart")
    gen.hash_secret.return_value = "hashed_secretpart"
    return gen


def _make_app() -> MagicMock:
    """Create a mock EventSourcedApplication."""
    app = MagicMock()
    agent = MagicMock()
    app.repository.get.return_value = agent
    return app


class TestIssueAPIKeyCommand:
    @pytest.mark.unit
    def test_construction(self) -> None:
        uid = uuid4()
        cmd = IssueAPIKeyCommand(agent_id=uid, requested_by="user|abc")
        assert cmd.agent_id == uid
        assert cmd.requested_by == "user|abc"

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        cmd = IssueAPIKeyCommand(agent_id=uuid4(), requested_by="u")
        with pytest.raises(AttributeError):
            cmd.requested_by = "other"  # type: ignore[misc]


class TestIssueAPIKeyHandler:
    @pytest.mark.unit
    def test_handle_returns_key_id_and_full_key(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = IssueAPIKeyHandler(app=app, key_generator=gen)

        cmd = IssueAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        key_id, full_key = handler.handle(cmd)

        assert key_id == "key123"
        assert full_key == "pk_key123_secretpart"

    @pytest.mark.unit
    def test_handle_calls_generate_extract_hash(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = IssueAPIKeyHandler(app=app, key_generator=gen)

        cmd = IssueAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        handler.handle(cmd)

        gen.generate_api_key.assert_called_once()
        gen.extract_key_parts.assert_called_once_with("pk_key123_secretpart")
        gen.hash_secret.assert_called_once_with("secretpart")

    @pytest.mark.unit
    def test_handle_stores_hash_in_aggregate(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = IssueAPIKeyHandler(app=app, key_generator=gen)

        agent_id = uuid4()
        cmd = IssueAPIKeyCommand(agent_id=agent_id, requested_by="user|abc")
        handler.handle(cmd)

        agent = app.repository.get.return_value
        agent.request_issue_api_key.assert_called_once()
        call_args = agent.request_issue_api_key.call_args[0]
        assert call_args[0] == "key123"  # key_id
        assert call_args[1] == "hashed_secretpart"  # key_hash

    @pytest.mark.unit
    def test_handle_saves_aggregate(self) -> None:
        app = _make_app()
        gen = _make_key_generator()
        handler = IssueAPIKeyHandler(app=app, key_generator=gen)

        cmd = IssueAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        handler.handle(cmd)

        agent = app.repository.get.return_value
        app.save.assert_called_once_with(agent)

    @pytest.mark.unit
    def test_dependency_injection_of_key_generator(self) -> None:
        """Key generator is injected, not hard-imported."""
        app = _make_app()
        custom_gen = MagicMock()
        custom_gen.generate_api_key.return_value = ("custom_id", "custom_key")
        custom_gen.extract_key_parts.return_value = ("custom_id", "custom_secret")
        custom_gen.hash_secret.return_value = "custom_hash"

        handler = IssueAPIKeyHandler(app=app, key_generator=custom_gen)
        cmd = IssueAPIKeyCommand(agent_id=uuid4(), requested_by="user|abc")
        key_id, full_key = handler.handle(cmd)

        assert key_id == "custom_id"
        assert full_key == "custom_key"
