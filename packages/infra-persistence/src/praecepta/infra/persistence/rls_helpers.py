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
