"""Unit tests for praecepta.infra.taskiq.settings."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praecepta.infra.taskiq.settings import TaskIQSettings, get_taskiq_settings


@pytest.mark.unit
class TestTaskIQSettings:
    def test_default_redis_url(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = TaskIQSettings()  # type: ignore[call-arg]
            assert settings.redis_url == "redis://localhost:6379/1"

    def test_default_result_ttl(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = TaskIQSettings()  # type: ignore[call-arg]
            assert settings.result_ttl == 3600

    def test_default_stream_prefix(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = TaskIQSettings()  # type: ignore[call-arg]
            assert settings.stream_prefix == "taskiq"

    def test_redis_url_uses_database_1(self) -> None:
        """TaskIQ defaults to database 1 to avoid collision with persistence (database 0)."""
        with patch.dict("os.environ", {}, clear=True):
            settings = TaskIQSettings()  # type: ignore[call-arg]
            assert "/1" in settings.redis_url

    def test_env_var_override(self) -> None:
        env = {
            "TASKIQ_REDIS_URL": "redis://custom-host:6380/2",
            "TASKIQ_RESULT_TTL": "7200",
            "TASKIQ_STREAM_PREFIX": "myapp",
        }
        with patch.dict("os.environ", env, clear=True):
            settings = TaskIQSettings()  # type: ignore[call-arg]
            assert settings.redis_url == "redis://custom-host:6380/2"
            assert settings.result_ttl == 7200
            assert settings.stream_prefix == "myapp"


@pytest.mark.unit
class TestGetTaskIQSettings:
    def test_returns_settings_instance(self) -> None:
        get_taskiq_settings.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            settings = get_taskiq_settings()
            assert isinstance(settings, TaskIQSettings)

    def test_cached_returns_same_instance(self) -> None:
        get_taskiq_settings.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            s1 = get_taskiq_settings()
            s2 = get_taskiq_settings()
            assert s1 is s2
