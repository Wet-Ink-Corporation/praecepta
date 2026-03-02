"""Create registry tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-01

Creates tenant_slug_registry and user_oidc_sub_registry tables
used by the event store database for uniqueness enforcement.
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- tenant_slug_registry --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_slug_registry (
            slug VARCHAR(63) PRIMARY KEY,
            tenant_id UUID,
            reserved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            confirmed BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_slug_registry_unconfirmed
            ON tenant_slug_registry (reserved_at)
            WHERE confirmed = FALSE
    """)

    # -- user_oidc_sub_registry --
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_oidc_sub_registry (
            oidc_sub VARCHAR(255) PRIMARY KEY,
            user_id UUID,
            tenant_id VARCHAR(63) NOT NULL,
            reserved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            confirmed BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_oidc_sub_registry_unconfirmed
            ON user_oidc_sub_registry (reserved_at)
            WHERE confirmed = FALSE
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_oidc_sub_registry CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_slug_registry CASCADE")
