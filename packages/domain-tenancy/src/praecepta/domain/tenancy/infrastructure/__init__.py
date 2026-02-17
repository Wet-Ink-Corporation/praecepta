"""Praecepta Domain Tenancy Infrastructure — adapters and projections."""

from praecepta.domain.tenancy.infrastructure.cascade_deletion import (
    CascadeDeletionResult,
    CascadeDeletionService,
)
from praecepta.domain.tenancy.infrastructure.config_repository import (
    ConfigRepository,
)
from praecepta.domain.tenancy.infrastructure.slug_registry import SlugRegistry
from praecepta.domain.tenancy.infrastructure.tenant_repository import (
    TenantRepository,
)

__all__ = [
    "CascadeDeletionResult",
    "CascadeDeletionService",
    "ConfigRepository",
    "SlugRegistry",
    "TenantRepository",
]
