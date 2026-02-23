"""TaskIQ lifespan hook for broker startup/shutdown.

Ensures the broker is properly started at application startup and
cleanly shut down when the application stops.

Priority 150 ensures TaskIQ starts AFTER persistence (75) and
event store (100), since tasks may depend on database access.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import LifespanContribution
from praecepta.infra.taskiq.broker import get_broker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _taskiq_lifespan(app: Any) -> AsyncIterator[None]:
    """Manage TaskIQ broker lifecycle.

    Startup: call broker.startup()
    Shutdown: call broker.shutdown()

    Args:
        app: The application instance (unused but required by protocol).
    """
    _broker = get_broker()
    await _broker.startup()
    logger.info("taskiq_lifespan: broker started")

    try:
        yield
    finally:
        await _broker.shutdown()
        logger.info("taskiq_lifespan: broker shut down")


lifespan_contribution = LifespanContribution(
    hook=_taskiq_lifespan,
    priority=150,
)
