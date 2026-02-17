"""Unit tests for Agent aggregate."""

from __future__ import annotations

import pytest

from praecepta.domain.identity.agent import Agent
from praecepta.foundation.domain.agent_value_objects import AgentStatus
from praecepta.foundation.domain.exceptions import ValidationError


@pytest.mark.unit
class TestAgentCreation:
    """Agent creation and initialization."""

    def test_agent_registered_event_emitted(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        events = agent.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Registered"
        assert events[0].agent_type_id == "test-bot"
        assert events[0].tenant_id == "acme-corp"
        assert events[0].display_name == "Test Bot"

    def test_agent_starts_in_active_state(self) -> None:
        agent = Agent(
            agent_type_id="workflow-agent",
            tenant_id="acme-corp",
            display_name="Workflow Agent",
        )
        assert agent.status == AgentStatus.ACTIVE.value

    def test_agent_tenant_id_immutable(self) -> None:
        agent = Agent(
            agent_type_id="data-bot",
            tenant_id="tenant-123",
            display_name="Data Bot",
        )
        assert agent.tenant_id == "tenant-123"

    def test_agent_creation_validates_agent_type_id(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent type ID format"):
            Agent(
                agent_type_id="Invalid-Type-ID",
                tenant_id="acme-corp",
                display_name="Invalid Agent",
            )

    def test_agent_creation_validates_display_name(self) -> None:
        with pytest.raises(ValueError, match="Display name cannot be empty"):
            Agent(
                agent_type_id="test-bot",
                tenant_id="acme-corp",
                display_name="   ",
            )

    def test_agent_creation_requires_tenant_id(self) -> None:
        with pytest.raises(TypeError):
            Agent(  # type: ignore[call-arg]
                agent_type_id="test-bot",
                display_name="Test Bot",
            )


@pytest.mark.unit
class TestAgentSuspension:
    """Agent suspension lifecycle."""

    def test_agent_suspend_active_to_suspended(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.collect_events()
        agent.request_suspend(reason="Test suspension")
        assert agent.status == AgentStatus.SUSPENDED.value
        events = agent.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Suspended"
        assert events[0].reason == "Test suspension"

    def test_agent_suspend_idempotent(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.request_suspend(reason="First suspension")
        agent.collect_events()
        agent.request_suspend(reason="Second suspension")
        assert agent.status == AgentStatus.SUSPENDED.value
        events = agent.collect_events()
        assert len(events) == 0

    def test_agent_suspend_default_reason(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.request_suspend()
        assert agent.status == AgentStatus.SUSPENDED.value


@pytest.mark.unit
class TestAgentReactivation:
    """Agent reactivation lifecycle."""

    def test_agent_reactivate_suspended_to_active(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.request_suspend(reason="Test")
        agent.collect_events()
        agent.request_reactivate()
        assert agent.status == AgentStatus.ACTIVE.value
        events = agent.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Reactivated"

    def test_agent_reactivate_idempotent(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.collect_events()
        agent.request_reactivate()
        assert agent.status == AgentStatus.ACTIVE.value
        events = agent.collect_events()
        assert len(events) == 0


@pytest.mark.unit
class TestAgentAPIKeys:
    """Agent API key issuance and rotation."""

    def test_issue_api_key_on_active_agent_succeeds(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.collect_events()
        agent.request_issue_api_key(
            key_id="abc12345",
            key_hash="$2b$12$hash...",
            created_at="2026-02-08T10:00:00Z",
        )
        events = agent.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "APIKeyIssued"
        assert events[0].key_id == "abc12345"
        assert len(agent.active_keys) == 1
        assert agent.active_keys[0]["key_id"] == "abc12345"
        assert agent.active_keys[0]["status"] == "active"

    def test_issue_api_key_on_suspended_agent_raises(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.request_suspend(reason="Test")
        with pytest.raises(ValidationError, match="Cannot issue key for suspended agent"):
            agent.request_issue_api_key(
                key_id="abc12345",
                key_hash="$2b$12$hash...",
                created_at="2026-02-08T10:00:00Z",
            )

    def test_rotate_api_key_succeeds(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.request_issue_api_key(
            key_id="old12345",
            key_hash="$2b$12$oldhash...",
            created_at="2026-02-08T10:00:00Z",
        )
        agent.collect_events()
        agent.request_rotate_api_key(
            new_key_id="new12345",
            new_key_hash="$2b$12$newhash...",
        )
        events = agent.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "APIKeyRotated"
        assert events[0].new_key_id == "new12345"
        assert events[0].revoked_key_id == "old12345"
        old_key = next(k for k in agent.active_keys if k["key_id"] == "old12345")
        assert old_key["status"] == "revoked"
        new_key = next(k for k in agent.active_keys if k["key_id"] == "new12345")
        assert new_key["status"] == "active"
        assert "old12345" in agent.revoked_keys

    def test_rotate_api_key_without_active_key_raises(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        with pytest.raises(ValidationError, match="No active key to rotate"):
            agent.request_rotate_api_key(
                new_key_id="new12345",
                new_key_hash="$2b$12$newhash...",
            )

    def test_rotate_api_key_on_suspended_agent_raises(self) -> None:
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        agent.request_issue_api_key(
            key_id="old12345",
            key_hash="$2b$12$oldhash...",
            created_at="2026-02-08T10:00:00Z",
        )
        agent.request_suspend(reason="Test")
        with pytest.raises(ValidationError, match="Cannot rotate key for non-active agent"):
            agent.request_rotate_api_key(
                new_key_id="new12345",
                new_key_hash="$2b$12$newhash...",
            )
