"""Unit tests for praecepta.infra.taskiq.broker."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from taskiq import TaskiqScheduler
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from praecepta.infra.taskiq.broker import get_broker, get_result_backend, get_scheduler


class TestFactoryFunctions:
    @pytest.mark.unit
    def test_get_broker_returns_redis_stream_broker(self) -> None:
        get_broker.cache_clear()
        get_result_backend.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            b = get_broker()
            assert isinstance(b, RedisStreamBroker)

    @pytest.mark.unit
    def test_get_result_backend_returns_redis(self) -> None:
        get_result_backend.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            rb = get_result_backend()
            assert isinstance(rb, RedisAsyncResultBackend)

    @pytest.mark.unit
    def test_get_scheduler_returns_taskiq_scheduler(self) -> None:
        get_broker.cache_clear()
        get_result_backend.cache_clear()
        get_scheduler.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            s = get_scheduler()
            assert isinstance(s, TaskiqScheduler)

    @pytest.mark.unit
    def test_get_broker_is_cached(self) -> None:
        get_broker.cache_clear()
        get_result_backend.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            b1 = get_broker()
            b2 = get_broker()
            assert b1 is b2

    @pytest.mark.unit
    def test_factory_not_invoked_at_import_time(self) -> None:
        """Module-level broker/scheduler are lazy proxies, not eagerly created."""
        from praecepta.infra.taskiq.broker import _LazyBroker, _LazyScheduler

        lb = _LazyBroker()
        ls = _LazyScheduler()
        # _instance is None until first attribute access
        assert lb._instance is None
        assert ls._instance is None
