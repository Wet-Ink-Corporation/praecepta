"""Application service for User aggregate persistence.

Lifespan singleton. Created during FastAPI startup and stored
in ``app.state.user_app``.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from eventsourcing.application import Application

from praecepta.domain.identity.user import User


class UserApplication(Application[UUID]):
    """Application service for User aggregate persistence.

    Uses shared event store infrastructure (same PostgreSQL database,
    separate aggregate stream).

    Attributes:
        snapshotting_intervals: Snapshot every 50 events for User.
    """

    snapshotting_intervals: ClassVar[dict[type, int]] = {User: 50}
