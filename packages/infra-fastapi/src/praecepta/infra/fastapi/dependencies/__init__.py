"""FastAPI dependency injection factories for praecepta.

Provides reusable FastAPI dependency factories for feature flag gating
and resource limit enforcement.
"""

from praecepta.infra.fastapi.dependencies.feature_flags import require_feature
from praecepta.infra.fastapi.dependencies.resource_limits import check_resource_limit

__all__ = [
    "check_resource_limit",
    "require_feature",
]
