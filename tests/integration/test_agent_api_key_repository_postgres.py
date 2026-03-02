"""Integration tests for AgentAPIKeyRepository against real PostgreSQL.

Verifies UPSERT, status updates, and lookups with real SQL execution.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.domain.identity.infrastructure.agent_api_key_repository import (
    AgentAPIKeyRepository,
)


@pytest.mark.integration
class TestAgentAPIKeyRepositoryPostgres:
    """AgentAPIKeyRepository tests against real PostgreSQL."""

    def _make_repo(self, sync_session_factory) -> AgentAPIKeyRepository:
        return AgentAPIKeyRepository(session_factory=sync_session_factory)

    def test_upsert_inserts_new_key(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        agent_id = uuid4()

        repo.upsert(
            key_id="key12345",
            agent_id=agent_id,
            tenant_id="acme",
            key_hash="$2b$12$somehash",
            status="active",
        )

        row = repo.lookup_by_key_id("key12345")
        assert row is not None
        assert row.key_id == "key12345"
        assert row.agent_id == agent_id
        assert row.tenant_id == "acme"
        assert row.status == "active"

    def test_update_status_to_revoked(self, sync_session_factory):
        """Status update to 'revoked' should also set revoked_at."""
        repo = self._make_repo(sync_session_factory)
        agent_id = uuid4()

        repo.upsert("revoke01", agent_id, "acme", "$2b$12$hash", "active")
        repo.update_status("revoke01", "revoked")

        row = repo.lookup_by_key_id("revoke01")
        assert row is not None
        assert row.status == "revoked"
        assert row.revoked_at is not None

    def test_lookup_returns_none_for_missing_key(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        assert repo.lookup_by_key_id("nope0000") is None
