"""Praecepta Infra Eventsourcing -- event store factory, projections, config."""

from praecepta.infra.eventsourcing.config_cache import HybridConfigCache
from praecepta.infra.eventsourcing.event_store import EventStoreFactory, get_event_store
from praecepta.infra.eventsourcing.lifespan import lifespan_contribution
from praecepta.infra.eventsourcing.projection_lifespan import projection_lifespan_contribution
from praecepta.infra.eventsourcing.projections.base import BaseProjection

# Deprecated — kept for backward compatibility
from praecepta.infra.eventsourcing.projections.poller import ProjectionPoller
from praecepta.infra.eventsourcing.projections.subscription_runner import (
    SubscriptionProjectionRunner,
)
from praecepta.infra.eventsourcing.settings import EventSourcingSettings, ProjectionPollingSettings

__all__ = [
    "BaseProjection",
    "EventSourcingSettings",
    "EventStoreFactory",
    "HybridConfigCache",
    "ProjectionPoller",  # deprecated
    "ProjectionPollingSettings",  # deprecated
    "SubscriptionProjectionRunner",
    "get_event_store",
    "lifespan_contribution",
    "projection_lifespan_contribution",
]
