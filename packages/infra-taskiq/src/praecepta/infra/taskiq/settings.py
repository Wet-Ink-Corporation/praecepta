"""TaskIQ configuration using Pydantic settings.

Provides type-safe configuration for TaskIQ broker, result backend,
and scheduler. Settings are loaded from environment variables with
``TASKIQ_`` prefix.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TaskIQSettings(BaseSettings):
    """Configuration for TaskIQ broker and scheduler.

    Environment Variables:
        TASKIQ_REDIS_URL: Redis URL for broker/scheduler
            (default: redis://localhost:6379/1, database 1 to separate
            from persistence Redis on database 0)
        TASKIQ_RESULT_TTL: Result backend TTL in seconds (default: 3600)
        TASKIQ_STREAM_PREFIX: Redis stream key prefix (default: taskiq)

    Example:
        >>> settings = TaskIQSettings()
        >>> settings.redis_url
        'redis://localhost:6379/1'
    """

    model_config = SettingsConfigDict(
        env_prefix="TASKIQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis URL for TaskIQ broker (database 1 by default)",
    )
    result_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Result backend TTL in seconds",
    )
    stream_prefix: str = Field(
        default="taskiq",
        description="Redis stream key prefix",
    )


@lru_cache(maxsize=1)
def get_taskiq_settings() -> TaskIQSettings:
    """Get cached TaskIQ settings singleton.

    Returns:
        TaskIQSettings instance loaded from environment.
    """
    return TaskIQSettings()
