"""Shared fixtures for integration tests requiring real infrastructure.

Session-scoped PostgreSQL and Redis containers are started once per test run.
Environment variables are injected per-test via monkeypatch so that the
eventsourcing library and persistence layer pick up container connection details.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Event Loop Policy (Windows compatibility)
# ---------------------------------------------------------------------------
# psycopg async requires SelectorEventLoop on Windows (ProactorEventLoop
# is incompatible). Set the policy globally so that both pytest-asyncio
# tests AND sync code that internally creates event loops (e.g. FastAPI
# TestClient lifespan) use a compatible loop.

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    @pytest.fixture(scope="session")
    def event_loop_policy():
        return asyncio.WindowsSelectorEventLoopPolicy()

# ---------------------------------------------------------------------------
# PostgreSQL Container (session-scoped)
# ---------------------------------------------------------------------------

_INFRA_PERSISTENCE = Path(__file__).resolve().parents[2] / "packages" / "infra-persistence"
ALEMBIC_INI = str(_INFRA_PERSISTENCE / "alembic.ini")
ALEMBIC_SCRIPT_LOCATION = str(_INFRA_PERSISTENCE / "alembic")


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL 16 container for the entire test session."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg


@pytest.fixture(scope="session")
def postgres_url(postgres_container) -> str:
    """SQLAlchemy-compatible connection URL using psycopg driver."""
    url = postgres_container.get_connection_url()
    # Ensure we use psycopg (v3) driver, not psycopg2
    return url.replace("+psycopg2", "+psycopg")


@pytest.fixture(scope="session")
def _eventsourcing_env(postgres_container) -> dict[str, str]:
    """Environment variables for the eventsourcing library."""
    url = postgres_container.get_connection_url()
    parsed = urlparse(url)
    return {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": parsed.path.lstrip("/"),
        "POSTGRES_HOST": parsed.hostname or "localhost",
        "POSTGRES_PORT": str(parsed.port or 5432),
        "POSTGRES_USER": parsed.username or "test",
        "POSTGRES_PASSWORD": parsed.password or "test",
        "CREATE_TABLE": "true",
        "POSTGRES_SCHEMA": "public",
    }


@pytest.fixture(scope="session")
def _database_env(postgres_container) -> dict[str, str]:
    """Environment variables for the persistence layer (DATABASE_* prefix)."""
    url = postgres_container.get_connection_url()
    parsed = urlparse(url)
    return {
        "DATABASE_HOST": parsed.hostname or "localhost",
        "DATABASE_PORT": str(parsed.port or 5432),
        "DATABASE_USER": parsed.username or "test",
        "DATABASE_PASSWORD": parsed.password or "test",
        "DATABASE_NAME": parsed.path.lstrip("/"),
    }


# ---------------------------------------------------------------------------
# Redis Container (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def redis_container():
    """Start a Redis 7 container for the entire test session."""
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.fixture(scope="session")
def redis_url(redis_container) -> str:
    """Redis connection URL from the container."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def _redis_env(redis_container) -> dict[str, str]:
    """Environment variables for Redis."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return {
        "REDIS_HOST": host,
        "REDIS_PORT": str(port),
        "REDIS_DB": "0",
    }


# ---------------------------------------------------------------------------
# Alembic Migrations (session-scoped, runs once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(postgres_url):
    """Run Alembic migrations to create all read model and registry tables."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(ALEMBIC_INI)
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_url)
    alembic_cfg.set_main_option("script_location", ALEMBIC_SCRIPT_LOCATION)
    command.upgrade(alembic_cfg, "head")


# ---------------------------------------------------------------------------
# Environment Variable Injection (function-scoped, autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch, _eventsourcing_env, _database_env, _redis_env):
    """Inject container connection details into os.environ for each test."""
    for key, value in _eventsourcing_env.items():
        monkeypatch.setenv(key, value)
    for key, value in _database_env.items():
        monkeypatch.setenv(key, value)
    for key, value in _redis_env.items():
        monkeypatch.setenv(key, value)


# ---------------------------------------------------------------------------
# Cache Clearing (function-scoped, autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear LRU-cached singletons so each test gets fresh instances."""
    from praecepta.infra.eventsourcing.event_store import get_event_store
    from praecepta.infra.persistence.database import get_database_manager
    from praecepta.infra.persistence.redis_client import get_redis_factory

    get_database_manager.cache_clear()
    get_event_store.cache_clear()
    get_redis_factory.cache_clear()
    yield
    get_database_manager.cache_clear()
    get_event_store.cache_clear()
    get_redis_factory.cache_clear()


# ---------------------------------------------------------------------------
# Table Cleanup (function-scoped, autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_read_model_tables(sync_session_factory):
    """TRUNCATE all projection tables after each test."""
    yield
    with sync_session_factory() as session:
        for table in (
            "agent_api_key_registry",
            "user_profile",
            "tenant_configuration",
            "tenants",
            "tenant_slug_registry",
            "user_oidc_sub_registry",
        ):
            session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        session.commit()


# ---------------------------------------------------------------------------
# SQLAlchemy Session Factories
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sync_engine(postgres_url):
    """Session-scoped sync SQLAlchemy engine."""
    engine = create_engine(postgres_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def sync_session_factory(sync_engine) -> sessionmaker[Session]:
    """Session-scoped sync session factory for repositories."""
    return sessionmaker(sync_engine, expire_on_commit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Application Service Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tenant_app(_set_env) -> Any:
    """TenantApplication backed by container PostgreSQL."""
    from praecepta.domain.tenancy.tenant_app import TenantApplication

    app = TenantApplication()
    return app


@pytest.fixture()
def user_app(_set_env) -> Any:
    """UserApplication backed by container PostgreSQL."""
    from praecepta.domain.identity.user_app import UserApplication

    app = UserApplication()
    return app


@pytest.fixture()
def agent_app(_set_env) -> Any:
    """AgentApplication backed by container PostgreSQL."""
    from praecepta.domain.identity.agent_app import AgentApplication

    app = AgentApplication()
    return app


# ---------------------------------------------------------------------------
# DatabaseManager Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def database_manager(_set_env):
    """DatabaseManager pointing at the container database."""
    from praecepta.infra.persistence.database import DatabaseManager, DatabaseSettings

    settings = DatabaseSettings()
    return DatabaseManager(settings)


# ---------------------------------------------------------------------------
# Redis Client Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def redis_client(redis_url):
    """Async Redis client connected to the container, flushed after each test.

    The client is created synchronously. Teardown uses a sync Redis client to
    flush the database, avoiding event-loop lifecycle conflicts with
    pytest-asyncio.
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(redis_url, decode_responses=True)
    yield client

    # Teardown: use sync redis to flush (avoids event loop conflicts)
    import redis as sync_redis

    sync_client = sync_redis.from_url(redis_url)
    sync_client.flushdb()
    sync_client.close()
