"""Application service for Tenant aggregate persistence.

Lifespan singleton. Created during FastAPI startup and stored
in ``app.state.tenant_app``.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from eventsourcing.application import Application

from praecepta.domain.tenancy.tenant import Tenant


class TenantApplication(Application[UUID]):
    """Application service for Tenant aggregate persistence.

    Uses shared event store infrastructure (same PostgreSQL database,
    separate aggregate stream).

    Attributes:
        snapshotting_intervals: Snapshot every 50 events for Tenant.
    """

    snapshotting_intervals: ClassVar[dict[type, int]] = {Tenant: 50}
