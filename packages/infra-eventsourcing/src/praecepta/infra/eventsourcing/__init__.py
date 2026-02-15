"""Praecepta Infra Eventsourcing -- event store factory, projections, config."""

from praecepta.infra.eventsourcing.config_cache import HybridConfigCache
from praecepta.infra.eventsourcing.event_store import EventStoreFactory, get_event_store
from praecepta.infra.eventsourcing.lifespan import lifespan_contribution
from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.settings import EventSourcingSettings

__all__ = [
    "BaseProjection",
    "EventSourcingSettings",
    "EventStoreFactory",
    "HybridConfigCache",
    "get_event_store",
    "lifespan_contribution",
]
