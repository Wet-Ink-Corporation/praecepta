"""Projection infrastructure for CQRS read models.

Provides base classes and utilities for building, running, and rebuilding
projections that consume domain events and maintain read models.
"""

from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.projections.rebuilder import ProjectionRebuilder
from praecepta.infra.eventsourcing.projections.subscription_runner import (
    SubscriptionProjectionRunner,
)

__all__ = [
    "BaseProjection",
    "ProjectionRebuilder",
    "SubscriptionProjectionRunner",
]
