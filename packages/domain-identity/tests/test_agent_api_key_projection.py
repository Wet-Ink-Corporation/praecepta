"""Unit tests for AgentAPIKeyProjection with mock repository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.projections.agent_api_key import (
    AgentAPIKeyProjection,
)


def _make_api_key_issued_event(
    *,
    key_id: str = "abc12345",
    key_hash: str = "$2b$12$hash...",
    tenant_id: str = "acme-corp",
) -> MagicMock:
    event = MagicMock()
    event.__class__ = type("APIKeyIssued", (), {})
    event.__class__.__name__ = "APIKeyIssued"
    event.originator_id = uuid4()
    event.key_id = key_id
    event.key_hash = key_hash
    event.tenant_id = tenant_id
    return event


def _make_api_key_rotated_event(
    *,
    new_key_id: str = "new12345",
    new_key_hash: str = "$2b$12$newhash...",
    revoked_key_id: str = "old12345",
    tenant_id: str = "acme-corp",
) -> MagicMock:
    event = MagicMock()
    event.__class__ = type("APIKeyRotated", (), {})
    event.__class__.__name__ = "APIKeyRotated"
    event.originator_id = uuid4()
    event.new_key_id = new_key_id
    event.new_key_hash = new_key_hash
    event.revoked_key_id = revoked_key_id
    event.tenant_id = tenant_id
    return event


@pytest.mark.unit
class TestAgentAPIKeyProjectionUpstream:
    def test_declares_upstream_application(self) -> None:
        from praecepta.domain.identity.agent_app import AgentApplication

        assert AgentAPIKeyProjection.upstream_application is AgentApplication


@pytest.mark.unit
class TestAgentAPIKeyProjectionTopics:
    def test_subscribes_to_agent_key_events(self) -> None:
        assert len(AgentAPIKeyProjection.topics) == 2
        assert any("Agent.APIKeyIssued" in t for t in AgentAPIKeyProjection.topics)
        assert any("Agent.APIKeyRotated" in t for t in AgentAPIKeyProjection.topics)


@pytest.mark.unit
class TestAgentAPIKeyProjectionPolicy:
    def test_upserts_on_api_key_issued(self) -> None:
        mock_repo = MagicMock()
        projection = AgentAPIKeyProjection(repository=mock_repo)
        event = _make_api_key_issued_event()
        projection.policy(event, MagicMock())
        mock_repo.upsert.assert_called_once()
        call_kwargs = mock_repo.upsert.call_args.kwargs
        assert call_kwargs["key_id"] == "abc12345"
        assert call_kwargs["status"] == "active"

    def test_revokes_and_upserts_on_rotation(self) -> None:
        mock_repo = MagicMock()
        projection = AgentAPIKeyProjection(repository=mock_repo)
        event = _make_api_key_rotated_event()
        projection.policy(event, MagicMock())
        # Should revoke old key and upsert new key
        mock_repo.update_status.assert_called_once_with(key_id="old12345", status="revoked")
        mock_repo.upsert.assert_called_once()
        call_kwargs = mock_repo.upsert.call_args.kwargs
        assert call_kwargs["key_id"] == "new12345"
        assert call_kwargs["status"] == "active"

    def test_ignores_unknown_events(self) -> None:
        mock_repo = MagicMock()
        projection = AgentAPIKeyProjection(repository=mock_repo)
        event = MagicMock()
        event.__class__.__name__ = "Registered"
        projection.policy(event, MagicMock())
        mock_repo.upsert.assert_not_called()
        mock_repo.update_status.assert_not_called()
