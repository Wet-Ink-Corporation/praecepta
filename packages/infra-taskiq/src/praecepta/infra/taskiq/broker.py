"""TaskIQ broker and scheduler configuration with Redis Stream.

This module provides the TaskIQ broker and scheduler instances configured to use
Redis Stream for reliable message delivery with acknowledgements.

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

import os

from taskiq_redis import (
    ListRedisScheduleSource,
    RedisAsyncResultBackend,
    RedisStreamBroker,
)

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource


def _get_redis_url() -> str:
    """Get Redis URL from environment.

    Reads the ``REDIS_URL`` environment variable. Falls back to
    ``redis://localhost:6379/0`` if not set.

    Returns:
        Redis connection URL string.
    """
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


# Result backend with 1-hour TTL for task results
result_backend: RedisAsyncResultBackend[str] = RedisAsyncResultBackend(
    redis_url=_get_redis_url(),
    result_ex_time=3600,  # 1 hour expiration
)

# Broker with Redis Stream for reliable delivery with acknowledgements
broker: RedisStreamBroker = RedisStreamBroker(
    url=_get_redis_url(),
).with_result_backend(result_backend)

# Scheduler with dual sources for static and dynamic schedules
# - LabelScheduleSource: discovers @broker.task(schedule=[...]) decorators
# - ListRedisScheduleSource: runtime-configurable schedules stored in Redis
# WARNING: Only run ONE scheduler instance per deployment to avoid duplicate execution
scheduler: TaskiqScheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        LabelScheduleSource(broker),
        ListRedisScheduleSource(_get_redis_url()),
    ],
)
