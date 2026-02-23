"""TaskIQ broker and scheduler configuration with Redis Stream.

This module provides factory functions for the TaskIQ broker, result backend,
and scheduler instances configured to use Redis Stream for reliable message
delivery with acknowledgements.

TaskIQ provides:
- Native async/await support
- FastAPI DI sharing via taskiq-fastapi
- Redis Stream reliable delivery with ACKs

Usage:
    # Define a task
    from praecepta.infra.taskiq import broker

    @broker.task
    async def my_task(arg: str) -> str:
        return f"processed {arg}"

    # Define a scheduled task
    @broker.task(schedule=[{"cron": "0 * * * *"}])
    async def hourly_task() -> None:
        pass

    # Enqueue task
    result = await my_task.kiq("value")

    # Start worker
    # taskiq worker praecepta.infra.taskiq.broker:broker

    # Start scheduler (single instance only)
    # taskiq scheduler praecepta.infra.taskiq.broker:scheduler --skip-first-run
"""

from __future__ import annotations

from functools import lru_cache

from taskiq_redis import (
    ListRedisScheduleSource,
    RedisAsyncResultBackend,
    RedisStreamBroker,
)

from praecepta.infra.taskiq.errors import TaskIQError  # noqa: F401 — re-export
from praecepta.infra.taskiq.settings import get_taskiq_settings
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource


@lru_cache(maxsize=1)
def get_result_backend() -> RedisAsyncResultBackend[str]:
    """Get or create the TaskIQ result backend.

    Returns:
        RedisAsyncResultBackend configured from TaskIQSettings.
    """
    settings = get_taskiq_settings()
    return RedisAsyncResultBackend(
        redis_url=settings.redis_url,
        result_ex_time=settings.result_ttl,
    )


@lru_cache(maxsize=1)
def get_broker() -> RedisStreamBroker:
    """Get or create the TaskIQ broker.

    Returns:
        RedisStreamBroker configured from TaskIQSettings with result backend.
    """
    settings = get_taskiq_settings()
    return RedisStreamBroker(
        url=settings.redis_url,
    ).with_result_backend(get_result_backend())


@lru_cache(maxsize=1)
def get_scheduler() -> TaskiqScheduler:
    """Get or create the TaskIQ scheduler.

    Uses dual schedule sources:
    - LabelScheduleSource: discovers @broker.task(schedule=[...]) decorators
    - ListRedisScheduleSource: runtime-configurable schedules stored in Redis

    WARNING: Only run ONE scheduler instance per deployment to avoid
    duplicate execution.

    Returns:
        TaskiqScheduler configured with the broker and schedule sources.
    """
    settings = get_taskiq_settings()
    _broker = get_broker()
    return TaskiqScheduler(
        broker=_broker,
        sources=[
            LabelScheduleSource(_broker),
            ListRedisScheduleSource(settings.redis_url),
        ],
    )


# Module-level references for backward compatibility and taskiq CLI.
# The CLI expects `taskiq worker module:broker` and `taskiq scheduler module:scheduler`.
# These are evaluated lazily on first access via the factory functions.


class _LazyBroker:
    """Lazy proxy that defers broker creation until first attribute access."""

    _instance: RedisStreamBroker | None = None

    def _get(self) -> RedisStreamBroker:
        if self._instance is None:
            self._instance = get_broker()
        return self._instance

    def __getattr__(self, name: str) -> object:
        return getattr(self._get(), name)


class _LazyResultBackend:
    """Lazy proxy that defers result backend creation until first attribute access."""

    _instance: RedisAsyncResultBackend[str] | None = None

    def _get(self) -> RedisAsyncResultBackend[str]:
        if self._instance is None:
            self._instance = get_result_backend()
        return self._instance

    def __getattr__(self, name: str) -> object:
        return getattr(self._get(), name)


class _LazyScheduler:
    """Lazy proxy that defers scheduler creation until first attribute access."""

    _instance: TaskiqScheduler | None = None

    def _get(self) -> TaskiqScheduler:
        if self._instance is None:
            self._instance = get_scheduler()
        return self._instance

    def __getattr__(self, name: str) -> object:
        return getattr(self._get(), name)


broker: RedisStreamBroker = _LazyBroker()  # type: ignore[assignment]
result_backend: RedisAsyncResultBackend[str] = _LazyResultBackend()  # type: ignore[assignment]
scheduler: TaskiqScheduler = _LazyScheduler()  # type: ignore[assignment]
