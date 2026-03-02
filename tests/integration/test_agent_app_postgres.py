"""Integration tests for AgentApplication against real PostgreSQL.

Verifies agent aggregate persistence including API key lifecycle.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.mark.integration
class TestAgentApplicationPostgres:
    """AgentApplication round-trip tests against real PostgreSQL."""

    def test_save_and_retrieve_agent(self, agent_app):
        """Create, save, reload, and verify agent state."""
        from praecepta.domain.identity.agent import Agent

        agent = Agent(
            agent_type_id="doc-processor",
            tenant_id="acme",
            display_name="Doc Processor Bot",
        )
        agent_app.save(agent)

        reloaded = agent_app.repository.get(agent.id)
        assert reloaded.agent_type_id == "doc-processor"
        assert reloaded.display_name == "Doc Processor Bot"
        assert reloaded.status == "active"

    def test_api_key_lifecycle(self, agent_app):
        """Issue an API key, save, reload, verify key metadata persisted."""
        from praecepta.domain.identity.agent import Agent

        agent = Agent(
            agent_type_id="api-agent",
            tenant_id="acme",
            display_name="API Agent",
        )
        agent_app.save(agent)

        agent = agent_app.repository.get(agent.id)
        agent.request_issue_api_key(
            key_id="k1234567",
            key_hash="$2b$12$fakehashfakehashfakehashfakehashfakehashfakehash",
            created_at=datetime.now(UTC).isoformat(),
        )
        agent_app.save(agent)

        reloaded = agent_app.repository.get(agent.id)
        assert len(reloaded.active_keys) == 1
        assert reloaded.active_keys[0]["key_id"] == "k1234567"
        assert reloaded.active_keys[0]["status"] == "active"

    def test_api_key_rotation(self, agent_app):
        """Issue, rotate, verify old revoked and new issued."""
        from praecepta.domain.identity.agent import Agent

        agent = Agent(
            agent_type_id="rotate-agent",
            tenant_id="acme",
            display_name="Rotate Agent",
        )
        agent_app.save(agent)

        # Issue first key
        agent = agent_app.repository.get(agent.id)
        agent.request_issue_api_key(
            key_id="oldkey01",
            key_hash="$2b$12$oldhash",
            created_at=datetime.now(UTC).isoformat(),
        )
        agent_app.save(agent)

        # Rotate
        agent = agent_app.repository.get(agent.id)
        agent.request_rotate_api_key(
            new_key_id="newkey01",
            new_key_hash="$2b$12$newhash",
        )
        agent_app.save(agent)

        reloaded = agent_app.repository.get(agent.id)
        active = [k for k in reloaded.active_keys if k["status"] == "active"]
        revoked = [k for k in reloaded.active_keys if k["status"] == "revoked"]
        assert len(active) == 1
        assert active[0]["key_id"] == "newkey01"
        assert len(revoked) == 1
        assert revoked[0]["key_id"] == "oldkey01"
        assert "oldkey01" in reloaded.revoked_keys
