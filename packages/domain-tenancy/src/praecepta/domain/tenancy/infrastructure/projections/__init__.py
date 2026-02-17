"""Praecepta Domain Tenancy Projections."""

from praecepta.domain.tenancy.infrastructure.projections.tenant_config import (
    TenantConfigProjection,
)
from praecepta.domain.tenancy.infrastructure.projections.tenant_list import (
    TenantListProjection,
)

__all__ = [
    "TenantConfigProjection",
    "TenantListProjection",
]
