"""Praecepta Domain Tenancy — multi-tenant lifecycle management."""

from praecepta.domain.tenancy.tenant import Tenant
from praecepta.domain.tenancy.tenant_app import TenantApplication

__all__ = [
    "Tenant",
    "TenantApplication",
]
