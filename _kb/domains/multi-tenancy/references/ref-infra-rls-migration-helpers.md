# Infrastructure Pattern: RLS Migration Helpers

> Reusable Alembic migration helpers for PostgreSQL Row-Level Security operations.

**Pattern ID:** `ref-infra-rls-migration-helpers`
**Category:** Infrastructure / Database Migrations
**Introduced:** F-101-002 (Database Isolation)
**Status:** Active

---

## Context

Alembic has no native DDL operations for PostgreSQL Row-Level Security (RLS) policies. Managing RLS policies across migrations requires raw SQL via `op.execute()`, which can lead to inconsistency and copy-paste errors when applied across multiple tables.

**Problem:** Without helpers, each migration that applies RLS must:

1. Manually construct `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` SQL
2. Handle `FORCE ROW LEVEL SECURITY` variations
3. Build policy `USING` clauses with correct session variable references and casts
4. Implement idempotent `DROP POLICY IF EXISTS` for downgrades

This leads to brittle, error-prone migrations with no shared logic.

---

## Pattern

Centralize RLS DDL operations in a `migrations/helpers/rls.py` module with reusable functions:

```python
"""Reusable helpers for RLS migration operations.

Centralizes RLS DDL patterns to ensure consistency across migration files.
Uses op.execute() with raw SQL because Alembic has no native RLS support.
"""

from alembic import op


def enable_rls(table_name: str, *, force: bool = False) -> None:
    """Enable Row-Level Security on a table.

    Args:
        table_name: PostgreSQL table name.
        force: If True, apply FORCE ROW LEVEL SECURITY (applies
               RLS even to table owners). Default False.
    """
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    if force:
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")


def disable_rls(table_name: str) -> None:
    """Disable Row-Level Security on a table.

    Args:
        table_name: PostgreSQL table name.
    """
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def create_tenant_isolation_policy(
    table_name: str,
    *,
    cast_type: str | None = None,
    policy_name: str = "tenant_isolation_policy",
) -> None:
    """Create a standard tenant isolation RLS policy.

    Creates a permissive policy that filters rows by comparing
    the tenant_id column to the current session variable.

    Args:
        table_name: PostgreSQL table name (must have tenant_id column).
        cast_type: PostgreSQL type to cast current_setting result to.
                   Use 'uuid' for UUID columns, None for text/varchar.
        policy_name: Policy name (default: tenant_isolation_policy).
    """
    cast_expr = f"::{cast_type}" if cast_type else ""

    op.execute(f"""
        CREATE POLICY {policy_name} ON {table_name}
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant', true){cast_expr})
    """)


def drop_tenant_isolation_policy(
    table_name: str,
    *,
    policy_name: str = "tenant_isolation_policy",
) -> None:
    """Drop a tenant isolation RLS policy.

    Args:
        table_name: PostgreSQL table name.
        policy_name: Policy name to drop.
    """
    op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")
```

---

## Usage

### Example Migration: Enable RLS on a New Table

```python
"""Add RLS to new projection table.

Revision ID: abc123def456
"""

from alembic import op
import sqlalchemy as sa
from migrations.helpers.rls import (
    enable_rls,
    create_tenant_isolation_policy,
    disable_rls,
    drop_tenant_isolation_policy,
)


def upgrade() -> None:
    # Create table with tenant_id column
    op.create_table(
        "usage_metrics",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )

    # Create index with tenant_id as leading column for RLS performance
    op.create_index(
        "ix_usage_metrics_tenant_id",
        "usage_metrics",
        ["tenant_id", "recorded_at"],
    )

    # Enable RLS with FORCE (apply to table owners)
    enable_rls("usage_metrics", force=True)

    # Create standard tenant isolation policy
    create_tenant_isolation_policy("usage_metrics")


def downgrade() -> None:
    drop_tenant_isolation_policy("usage_metrics")
    disable_rls("usage_metrics")
    op.drop_index("ix_usage_metrics_tenant_id", table_name="usage_metrics")
    op.drop_table("usage_metrics")
```

### Example: Applying FORCE RLS to Existing Tables

```python
"""Apply FORCE RLS to event store tables.

Revision ID: def456ghi789
Revises: abc123def456
"""

from migrations.helpers.rls import enable_rls


def upgrade() -> None:
    """Tighten RLS by applying FORCE to existing policies."""
    # Tables already have RLS enabled, just add FORCE
    enable_rls("stored_events", force=True)
    enable_rls("snapshots", force=True)


def downgrade() -> None:
    """Remove FORCE, keep RLS enabled."""
    op.execute("ALTER TABLE stored_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE snapshots NO FORCE ROW LEVEL SECURITY")
```

---

## Design Rationale

### Why Helpers Instead of Alembic Extensions?

**Considered:** Contributing RLS support to Alembic as a plugin.

**Rejected:** Alembic's extension API is designed for custom operation objects, which adds significant complexity. Helper functions in the migrations directory provide the same benefits with zero external dependencies.

### Why `current_setting('app.current_tenant', true)` Pattern?

The second parameter `true` in `current_setting()` is critical:

- Returns `NULL` when variable is unset (instead of raising an error)
- Enables migrations, health checks, and admin tools to run without tenant context
- RLS default-deny behavior filters out all rows when NULL (safe fallback)

### Why Parameterized `cast_type`?

Different tables use different tenant_id column types:

- Event store tables (`stored_events`, `snapshots`): `VARCHAR(255)` (tenant slug)
- Projection tables: `VARCHAR(255)` (consistent with event store)
- Future tables might use `UUID` if tenant IDs change to UUIDs

The helper supports both via optional casting: `cast_type="uuid"` or `cast_type=None`.

---

## Conventions

### 1. Standard Policy Name

All tenant isolation policies use the name `tenant_isolation_policy` for consistency. This makes it easy to query `pg_policies` catalog to verify RLS coverage.

### 2. Session Variable Name

All policies reference `app.current_tenant` as the session variable name. This is set by the SQLAlchemy session event handler (see `ref-infra-tenant-context-handler.md`).

### 3. Index Convention

Every table with RLS must have an index with `tenant_id` as the **leading column**:

```python
op.create_index(
    "ix_{table}_tenant_id",
    "{table}",
    ["tenant_id", "{primary_key_or_query_column}"],
)
```

This allows the query planner to efficiently filter rows by tenant before applying other WHERE conditions.

### 4. FORCE vs Non-FORCE

**Use `force=True` when:**

- Applying RLS to projection tables (queries always have tenant context)
- Tightening security after initial RLS validation

**Use `force=False` when:**

- Initial RLS rollout (allows debugging as table owner)
- Tables accessed by admin/support tools that need cross-tenant visibility

---

## Testing

### Verify RLS Coverage via Integration Test

```python
async def test_all_tenant_scoped_tables_have_rls_policies(
    db_engine_with_migrations: AsyncEngine,
) -> None:
    """Verify all tenant-scoped tables have tenant_isolation_policy."""
    async with db_engine_with_migrations.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_policies "
                "WHERE policyname = 'tenant_isolation_policy' "
                "ORDER BY tablename"
            )
        )
        tables_with_policy = {row[0] for row in result}

    expected = {"stored_events", "snapshots", "memory_block_summaries", ...}
    assert tables_with_policy == expected
```

This test catches silent regressions (e.g., a migration that accidentally drops a policy).

---

## Related Patterns

- **Tenant Context Handler** (`ref-infra-tenant-context-handler.md`): Sets `app.current_tenant` session variable
- **Cross-Tenant Isolation Testing** (`ref-infra-cross-tenant-isolation-tests.md`): Validates RLS enforcement
- **Alembic Migration Patterns** (not yet documented): General migration best practices

---

## References

- **Feature:** F-101-002 (Database Isolation)
- **Stories:** S-101-002-001, S-101-002-003, S-101-002-004
- **Implementation:** `migrations/helpers/rls.py`
- **PostgreSQL Docs:** [Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

---

**Last Updated:** 2026-02-06
**Introduced By:** S-101-002-001
**Status:** Active — used across 3 migrations in F-101-002
