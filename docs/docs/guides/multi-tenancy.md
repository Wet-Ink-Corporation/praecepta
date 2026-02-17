# Multi-Tenancy

Every praecepta application is multi-tenant by default. Tenant isolation is enforced at multiple levels.

## How It Works

1. **Request context middleware** extracts the tenant from the incoming request (JWT claim, header, or URL)
2. **TenantStateMiddleware** sets the `tenant_id` in request context, available via `get_current_tenant_id()`
3. **Row-Level Security (RLS)** on PostgreSQL tables ensures queries only return rows for the current tenant
4. **Projections** include `tenant_id` on every table — a framework invariant

## Request Context

Access the current tenant from anywhere in your request handler chain:

```python
from praecepta.foundation.application import (
    get_current_tenant_id,
    get_current_context,
)

tenant_id = get_current_tenant_id()
context = get_current_context()  # Full RequestContext with tenant, principal, correlation_id
```

## Row-Level Security

Praecepta provides helpers to create and manage RLS policies on PostgreSQL tables:

```python
from praecepta.infra.persistence import (
    enable_rls,
    create_tenant_isolation_policy,
)

# In a migration
enable_rls("order_summaries")
create_tenant_isolation_policy("order_summaries")
```

This ensures that:

- Every query is automatically scoped to the current tenant
- No application code can accidentally access another tenant's data
- Isolation is enforced at the database level, not just the application level

## Projection Tables

Every projection table **must** include a `tenant_id` column:

```sql
CREATE TABLE order_summaries (
    order_id TEXT PRIMARY KEY,
    tenant_id UUID NOT NULL,    -- Required for RLS
    total NUMERIC NOT NULL,
    status TEXT NOT NULL
);
```

This is not optional — the framework relies on this column for tenant isolation at the database level.

## Tenant Configuration

The hierarchical configuration system supports per-tenant overrides:

```python
from praecepta.foundation.domain import ConfigKey, StringConfigValue

# System default applies to all tenants
SYSTEM_DEFAULTS = {
    ConfigKey("feature.dark_mode"): BooleanConfigValue(False),
    ConfigKey("limits.max_orders"): IntegerConfigValue(1000),
}

# Per-tenant overrides are stored in the event store
# and cached via HybridConfigCache
```

## Tenant Value Objects

The foundation provides pre-built value objects for tenant data:

```python
from praecepta.foundation.domain import (
    TenantId,           # UUID-based tenant identifier
    TenantName,         # Validated display name
    TenantSlug,         # URL-safe unique identifier
    TenantStatus,       # Active, suspended, etc.
    SuspensionCategory, # Why a tenant was suspended
)
```
