"""Integration tests for DatabaseManager against real PostgreSQL.

Verifies async/sync engine creation, session lifecycle, and disposal.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestDatabaseManagerLive:
    """DatabaseManager tests against a real PostgreSQL container."""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_async_engine_connects(self, database_manager):
        """Async engine should execute SELECT 1 successfully."""
        from sqlalchemy import text

        engine = database_manager.get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_sync_engine_connects(self, database_manager):
        """Sync engine should execute SELECT 1 successfully."""
        from sqlalchemy import text

        engine = database_manager.get_sync_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_async_session_yields_and_closes(self, database_manager):
        """Async session generator should yield a usable session."""
        from sqlalchemy import text

        async for session in database_manager.get_db_session():
            result = await session.execute(text("SELECT 42"))
            assert result.scalar() == 42

    @pytest.mark.asyncio(loop_scope="function")
    async def test_dispose_cleans_up_both_engines(self, database_manager):
        """dispose() should clean up both async and sync engines."""
        # Create both engines
        _ = database_manager.get_engine()
        _ = database_manager.get_sync_engine()

        await database_manager.dispose()

        assert database_manager._engine is None
        assert database_manager._sync_engine is None

    def test_pool_settings_applied(self, database_manager):
        """Verify engine pool size matches configured settings."""
        engine = database_manager.get_sync_engine()
        pool = engine.pool

        assert pool.size() == database_manager.settings.sync_pool_size
