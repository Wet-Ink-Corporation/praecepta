"""Shared fixtures for integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from examples.dog_school.app import create_dog_school_app
from examples.dog_school.router import _dogs
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from fastapi import FastAPI

# Entry-point names excluded in integration tests (no external services).
TEST_EXCLUDE_NAMES = frozenset(
    {
        "api_key_auth",
        "jwt_auth",
        "auth",
        "event_store",
        "persistence",
        "projection_runner",
        "observability",
        "taskiq",
    }
)


@pytest.fixture()
def dog_school_app() -> FastAPI:
    """Create a fresh Dog School app for each test."""
    _dogs.clear()
    return create_dog_school_app(exclude_names=TEST_EXCLUDE_NAMES)


@pytest.fixture()
def client(dog_school_app: FastAPI) -> TestClient:
    """TestClient for the Dog School app (lifespan hooks executed)."""
    with TestClient(dog_school_app, raise_server_exceptions=False) as c:
        yield c  # type: ignore[misc]
    _dogs.clear()


@pytest.fixture()
def tenant_headers() -> dict[str, str]:
    """Standard headers that provide tenant context for requests."""
    return {
        "X-Tenant-ID": "acme-corp",
        "X-User-ID": "00000000-0000-0000-0000-000000000001",
    }
