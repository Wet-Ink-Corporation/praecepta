"""Integration tests for ConfigRepository against real PostgreSQL.

Verifies JSONB storage, UPSERT, and tenant-scoped queries.
"""

from __future__ import annotations

import pytest

from praecepta.domain.tenancy.infrastructure.config_repository import ConfigRepository


@pytest.mark.integration
class TestConfigRepositoryPostgres:
    """ConfigRepository tests against real PostgreSQL."""

    def _make_repo(self, sync_session_factory) -> ConfigRepository:
        return ConfigRepository(session_factory=sync_session_factory)

    def test_upsert_inserts_and_reads_back_jsonb(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        repo.upsert(
            tenant_id="acme",
            key="features",
            value={"dark_mode": True, "beta": False},
            updated_by="admin",
        )

        result = repo.get("acme", "features")
        assert result == {"dark_mode": True, "beta": False}

    def test_upsert_updates_existing_config_key(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        repo.upsert("acme", "theme", {"color": "blue"}, "admin")
        repo.upsert("acme", "theme", {"color": "red"}, "admin")

        result = repo.get("acme", "theme")
        assert result == {"color": "red"}

    def test_get_returns_none_for_missing_key(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        assert repo.get("acme", "nonexistent") is None

    def test_get_all_returns_multiple_keys(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        repo.upsert("acme", "key1", {"a": 1}, "admin")
        repo.upsert("acme", "key2", {"b": 2}, "admin")

        all_config = repo.get_all("acme")
        assert len(all_config) == 2
        assert all_config["key1"] == {"a": 1}
        assert all_config["key2"] == {"b": 2}

    def test_delete_removes_config_entry(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)

        repo.upsert("acme", "to-delete", {"temp": True}, "admin")
        assert repo.get("acme", "to-delete") is not None

        deleted = repo.delete("acme", "to-delete")
        assert deleted is True
        assert repo.get("acme", "to-delete") is None

    def test_delete_returns_false_for_missing(self, sync_session_factory):
        repo = self._make_repo(sync_session_factory)
        assert repo.delete("acme", "never-existed") is False
