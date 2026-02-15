"""Tests for APIKeyAuthMiddleware: passthrough, malformed key, valid flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

if TYPE_CHECKING:
    from starlette.requests import Request
from starlette.testclient import TestClient

from praecepta.infra.auth.api_key_generator import APIKeyGenerator
from praecepta.infra.auth.middleware.api_key_auth import APIKeyAuthMiddleware


@dataclass
class FakeKeyRecord:
    """Fake key record for testing."""

    agent_id: UUID
    tenant_id: str
    key_hash: str
    status: str


class FakeKeyRepo:
    """Fake repository that returns a preconfigured key record."""

    def __init__(self, records: dict[str, FakeKeyRecord]) -> None:
        self._records = records

    def lookup_by_key_id(self, key_id: str) -> FakeKeyRecord | None:
        return self._records.get(key_id)


def _make_app(
    repo: FakeKeyRepo,
    key_prefix: str = "pk_",
) -> Starlette:
    """Build a minimal Starlette app with APIKeyAuthMiddleware."""

    async def homepage(request: Request) -> Response:
        return JSONResponse({"ok": True})

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "healthy"})

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/health", health),
        ],
    )
    app.state.agent_api_key_repo = repo  # type: ignore[attr-defined]
    app.add_middleware(APIKeyAuthMiddleware, key_prefix=key_prefix)
    return app


@pytest.mark.unit
class TestAPIKeyPassthrough:
    """Test that missing API key passes through to next middleware."""

    def test_no_api_key_passes_through(self) -> None:
        app = _make_app(FakeKeyRepo({}))
        client = TestClient(app, raise_server_exceptions=False)
        # Without X-API-Key, middleware passes through.
        # No JWT middleware behind it, so we hit the route directly.
        response = client.get("/")
        assert response.status_code == 200

    def test_excluded_path_skips_auth(self) -> None:
        app = _make_app(FakeKeyRepo({}))
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.unit
class TestAPIKeyMalformed:
    """Test malformed API key handling."""

    def test_wrong_prefix_returns_401(self) -> None:
        app = _make_app(FakeKeyRepo({}))
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"X-API-Key": "bad_12345678secret"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_FORMAT"

    def test_too_short_returns_401(self) -> None:
        app = _make_app(FakeKeyRepo({}))
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"X-API-Key": "pk_short"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_FORMAT"

    def test_unknown_key_id_returns_401(self) -> None:
        app = _make_app(FakeKeyRepo({}))
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"X-API-Key": "pk_UNKNOWN1thisisthesecretpart"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_KEY"


@pytest.mark.unit
class TestAPIKeyValidFlow:
    """Test valid API key flow."""

    def test_valid_key_authenticates(self) -> None:
        gen = APIKeyGenerator(prefix="pk_")
        key_id, full_key = gen.generate_api_key()
        parts = gen.extract_key_parts(full_key)
        assert parts is not None
        _, secret = parts
        key_hash = gen.hash_secret(secret)

        agent_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        record = FakeKeyRecord(
            agent_id=agent_id,
            tenant_id="acme",
            key_hash=key_hash,
            status="active",
        )
        repo = FakeKeyRepo({key_id: record})
        app = _make_app(repo)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"X-API-Key": full_key})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_revoked_key_returns_401(self) -> None:
        gen = APIKeyGenerator(prefix="pk_")
        key_id, full_key = gen.generate_api_key()
        parts = gen.extract_key_parts(full_key)
        assert parts is not None
        _, secret = parts
        key_hash = gen.hash_secret(secret)

        agent_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        record = FakeKeyRecord(
            agent_id=agent_id,
            tenant_id="acme",
            key_hash=key_hash,
            status="revoked",
        )
        repo = FakeKeyRepo({key_id: record})
        app = _make_app(repo)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"X-API-Key": full_key})
        assert response.status_code == 401
        assert response.json()["error_code"] == "REVOKED_KEY"

    def test_wrong_secret_returns_401(self) -> None:
        gen = APIKeyGenerator(prefix="pk_")
        key_id, full_key = gen.generate_api_key()
        parts = gen.extract_key_parts(full_key)
        assert parts is not None
        _, secret = parts
        key_hash = gen.hash_secret(secret)

        agent_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        record = FakeKeyRecord(
            agent_id=agent_id,
            tenant_id="acme",
            key_hash=key_hash,
            status="active",
        )
        repo = FakeKeyRepo({key_id: record})
        app = _make_app(repo)

        # Use the correct key_id but a wrong secret
        wrong_key = f"pk_{key_id}wrongsecretvalue12345678901234567890123"
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"X-API-Key": wrong_key})
        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_KEY"
