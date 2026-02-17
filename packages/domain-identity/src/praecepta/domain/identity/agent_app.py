"""Application service for Agent aggregate persistence.

Lifespan singleton. Created during FastAPI startup and stored
in ``app.state.agent_app``.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from eventsourcing.application import Application

from praecepta.domain.identity.agent import Agent


class AgentApplication(Application[UUID]):
    """Application service for Agent aggregate persistence.

    Uses shared event store infrastructure (same PostgreSQL database,
    separate aggregate stream).

    Attributes:
        snapshotting_intervals: Snapshot every 50 events for Agent.
    """

    snapshotting_intervals: ClassVar[dict[type, int]] = {Agent: 50}
