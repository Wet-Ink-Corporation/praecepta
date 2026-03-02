"""Create read model tables.

Revision ID: 001
Create Date: 2026-03-01

Creates projection tables for tenants, tenant_configuration,
user_profile, and agent_api_key_registry with appropriate
indexes and RLS policies.
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- tenants (no RLS, admin/control-plane) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY,
            slug VARCHAR(63) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            activated_at TIMESTAMP WITH TIME ZONE,
            suspended_at TIMESTAMP WITH TIME ZONE,
            decommissioned_at TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants (status)
    """)

    # -- tenant_configuration (RLS-enabled) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_configuration (
            tenant_id VARCHAR(63) NOT NULL,
            config_key VARCHAR(255) NOT NULL,
            config_value JSONB NOT NULL DEFAULT '{}',
            updated_by VARCHAR(255) NOT NULL DEFAULT '',
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tenant_id, config_key)
        )
    """)
    op.execute("ALTER TABLE tenant_configuration ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_configuration FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'tenant_configuration'
                AND policyname = 'tenant_isolation_policy'
            ) THEN
                CREATE POLICY tenant_isolation_policy
                    ON tenant_configuration
                    FOR ALL
                    USING (tenant_id = current_setting('app.current_tenant', true));
            END IF;
        END
        $$
    """)

    # -- user_profile (RLS-enabled) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id UUID PRIMARY KEY,
            oidc_sub VARCHAR(255) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL DEFAULT '',
            display_name VARCHAR(255) NOT NULL DEFAULT 'User',
            tenant_id VARCHAR(63) NOT NULL,
            preferences JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_profile_oidc_sub_tenant
            ON user_profile (oidc_sub, tenant_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_profile_tenant
            ON user_profile (tenant_id)
    """)
    op.execute("ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_profile FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'user_profile'
                AND policyname = 'tenant_isolation_user_profile'
            ) THEN
                CREATE POLICY tenant_isolation_user_profile
                    ON user_profile
                    FOR ALL
                    USING (tenant_id = current_setting('app.current_tenant', true));
            END IF;
        END
        $$
    """)

    # -- agent_api_key_registry (RLS-enabled) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_api_key_registry (
            key_id VARCHAR(8) PRIMARY KEY,
            agent_id UUID NOT NULL,
            tenant_id VARCHAR(63) NOT NULL,
            key_hash VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revoked_at TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_api_key_tenant
            ON agent_api_key_registry (tenant_id)
    """)
    op.execute("ALTER TABLE agent_api_key_registry ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_api_key_registry FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'agent_api_key_registry'
                AND policyname = 'tenant_isolation_agent_api_key'
            ) THEN
                CREATE POLICY tenant_isolation_agent_api_key
                    ON agent_api_key_registry
                    FOR ALL
                    USING (tenant_id = current_setting('app.current_tenant', true));
            END IF;
        END
        $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_api_key_registry CASCADE")
    op.execute("DROP TABLE IF EXISTS user_profile CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_configuration CASCADE")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE")
