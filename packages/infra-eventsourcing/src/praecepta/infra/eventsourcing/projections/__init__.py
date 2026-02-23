"""Projection infrastructure for CQRS read models.

Provides base classes and utilities for building, running, and rebuilding
projections that consume domain events and maintain read models.
"""

from praecepta.infra.eventsourcing.projections.base import BaseProjection

# Deprecated — kept for backward compatibility
from praecepta.infra.eventsourcing.projections.poller import ProjectionPoller
from praecepta.infra.eventsourcing.projections.rebuilder import ProjectionRebuilder
from praecepta.infra.eventsourcing.projections.runner import ProjectionRunner
from praecepta.infra.eventsourcing.projections.subscription_runner import (
    SubscriptionProjectionRunner,
)

__all__ = [
    "BaseProjection",
    "ProjectionPoller",  # deprecated
    "ProjectionRebuilder",
    "ProjectionRunner",  # deprecated
    "SubscriptionProjectionRunner",
]
