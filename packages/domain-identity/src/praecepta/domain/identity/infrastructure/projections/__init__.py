"""Praecepta Domain Identity Projections."""

from praecepta.domain.identity.infrastructure.projections.agent_api_key import (
    AgentAPIKeyProjection,
)
from praecepta.domain.identity.infrastructure.projections.user_profile import (
    UserProfileProjection,
)

__all__ = [
    "AgentAPIKeyProjection",
    "UserProfileProjection",
]
