"""Integration tests for Row-Level Security enforcement.

Verifies that RLS policies correctly isolate tenants on projection tables.

NOTE: RLS is bypassed for superusers (even with FORCE ROW LEVEL SECURITY).
These tests create a dedicated non-superuser role ``rls_test_user`` and connect
via a separate engine so that the policies are actually enforced.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def rls_session_factory(postgres_url, sync_session_factory):
    """Session factory connected as a non-superuser so RLS is enforced."""
    # Create the non-superuser role (idempotent)
    with sync_session_factory() as session:
        session.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rls_test_user') THEN
                    CREATE ROLE rls_test_user LOGIN PASSWORD 'rls_test_pass';
                END IF;
            END $$
        """))
        # Grant usage on tables so the role can SELECT/INSERT
        session.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO rls_test_user"))
        session.commit()

    # Build a connection URL for the non-superuser
    rls_url = postgres_url.replace(
        "://test:test@", "://rls_test_user:rls_test_pass@"
    )
    engine = create_engine(rls_url, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)
    yield factory
    engine.dispose()


@pytest.mark.integration
class TestRLSEnforcement:
    """RLS policy tests against real PostgreSQL with RLS-enabled tables."""

    def test_rls_policy_isolates_tenants_on_user_profile(
        self, sync_session_factory, rls_session_factory
    ):
        """Insert profiles for 2 tenants, SET app.current_tenant, verify isolation."""
        # Insert as superuser (bypasses RLS for writes)
        with sync_session_factory() as session:
            for tenant, sub in [("tenant-a", "sub-a"), ("tenant-b", "sub-b")]:
                session.execute(
                    text("""
                        INSERT INTO user_profile
                            (user_id, oidc_sub, email, display_name, tenant_id, preferences)
                        VALUES
                            (:uid, :sub, :email, :name, :tid, '{}')
                    """),
                    {
                        "uid": str(uuid4()),
                        "sub": sub,
                        "email": f"{sub}@test.com",
                        "name": f"User {sub}",
                        "tid": tenant,
                    },
                )
            session.commit()

        # Query as non-superuser with tenant-a context
        with rls_session_factory() as session:
            session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": "tenant-a"},
            )
            rows = session.execute(text("SELECT tenant_id FROM user_profile")).fetchall()
            tenant_ids = [r[0] for r in rows]
            assert tenant_ids == ["tenant-a"]

    def test_rls_policy_isolates_tenants_on_tenant_configuration(
        self, sync_session_factory, rls_session_factory
    ):
        """Insert config for 2 tenants, verify isolation."""
        with sync_session_factory() as session:
            for tenant in ["cfg-tenant-a", "cfg-tenant-b"]:
                session.execute(
                    text("""
                        INSERT INTO tenant_configuration
                            (tenant_id, config_key, config_value, updated_by)
                        VALUES
                            (:tid, 'features', '{"enabled": true}', 'admin')
                    """),
                    {"tid": tenant},
                )
            session.commit()

        with rls_session_factory() as session:
            session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": "cfg-tenant-a"},
            )
            rows = session.execute(
                text("SELECT tenant_id FROM tenant_configuration")
            ).fetchall()
            tenant_ids = [r[0] for r in rows]
            assert tenant_ids == ["cfg-tenant-a"]

    def test_set_local_scoped_to_transaction(self, rls_session_factory):
        """set_config with is_local=true should be scoped to the current transaction."""
        with rls_session_factory() as session:
            session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": "scoped-tenant"},
            )
            result = session.execute(
                text("SELECT current_setting('app.current_tenant', true)")
            ).scalar()
            assert result == "scoped-tenant"
            session.commit()

        # New transaction should not have the setting
        with rls_session_factory() as session:
            result = session.execute(
                text("SELECT current_setting('app.current_tenant', true)")
            ).scalar()
            assert result in (None, "")
