"""Unit tests for AgentApplication."""

from __future__ import annotations

import pytest

from praecepta.domain.identity.agent import Agent
from praecepta.domain.identity.agent_app import AgentApplication


@pytest.mark.unit
class TestAgentApplication:
    """AgentApplication configuration and instantiation."""

    def test_snapshotting_interval_configured(self) -> None:
        assert AgentApplication.snapshotting_intervals == {Agent: 50}

    def test_can_instantiate(self) -> None:
        app = AgentApplication()
        assert app is not None

    def test_save_and_retrieve(self) -> None:
        app = AgentApplication()
        agent = Agent(
            agent_type_id="test-bot",
            tenant_id="acme-corp",
            display_name="Test Bot",
        )
        app.save(agent)
        retrieved = app.repository.get(agent.id)
        assert retrieved.agent_type_id == "test-bot"
        assert retrieved.tenant_id == "acme-corp"
        assert retrieved.version == 1
