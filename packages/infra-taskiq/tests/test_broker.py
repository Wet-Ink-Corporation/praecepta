"""Unit tests for praecepta.infra.taskiq.broker."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from taskiq import TaskiqScheduler
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker


class TestBrokerInstantiation:
    @pytest.mark.unit
    def test_broker_is_redis_stream_broker(self) -> None:
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            from praecepta.infra.taskiq.broker import broker

            assert isinstance(broker, RedisStreamBroker)

    @pytest.mark.unit
    def test_result_backend_is_redis(self) -> None:
        from praecepta.infra.taskiq.broker import result_backend

        assert isinstance(result_backend, RedisAsyncResultBackend)

    @pytest.mark.unit
    def test_scheduler_is_taskiq_scheduler(self) -> None:
        from praecepta.infra.taskiq.broker import scheduler

        assert isinstance(scheduler, TaskiqScheduler)

    @pytest.mark.unit
    def test_get_redis_url_uses_env(self) -> None:
        with patch.dict(
            "os.environ",
            {"REDIS_URL": "redis://custom-host:6380/1"},
            clear=False,
        ):
            from praecepta.infra.taskiq.broker import _get_redis_url

            assert _get_redis_url() == "redis://custom-host:6380/1"

    @pytest.mark.unit
    def test_get_redis_url_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            from praecepta.infra.taskiq.broker import _get_redis_url

            assert _get_redis_url() == "redis://localhost:6379/0"
