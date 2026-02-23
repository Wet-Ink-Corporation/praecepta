"""Praecepta Infra TaskIQ — background task processing broker factory."""

from praecepta.infra.taskiq.broker import (
    broker,
    get_broker,
    get_result_backend,
    get_scheduler,
    result_backend,
    scheduler,
)
from praecepta.infra.taskiq.errors import (
    TaskIQBrokerError,
    TaskIQError,
    TaskIQResultError,
    TaskIQSerializationError,
)
from praecepta.infra.taskiq.lifespan import lifespan_contribution
from praecepta.infra.taskiq.settings import TaskIQSettings, get_taskiq_settings

__all__ = [
    "TaskIQBrokerError",
    "TaskIQError",
    "TaskIQResultError",
    "TaskIQSerializationError",
    "TaskIQSettings",
    "broker",
    "get_broker",
    "get_result_backend",
    "get_scheduler",
    "get_taskiq_settings",
    "lifespan_contribution",
    "result_backend",
    "scheduler",
]
