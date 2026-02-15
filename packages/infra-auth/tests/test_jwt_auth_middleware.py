"""Tests for JWTAuthMiddleware: excluded paths, missing token, valid flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

if TYPE_CHECKING:
    from starlette.requests import Request
from starlette.testclient import TestClient

from praecepta.infra.auth.middleware.jwt_auth import JWTAuthMiddleware


def _make_app(
    *,
    jwks_provider: MagicMock | None = None,
    issuer: str = "https://auth.example.com",
    audience: str = "api",
    dev_bypass: bool = False,
) -> Starlette:
    """Build a minimal Starlette app with JWTAuthMiddleware."""

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
    # Patch resolve_dev_bypass to skip env check in tests
    with patch("praecepta.infra.auth.middleware.jwt_auth.resolve_dev_bypass") as mock_resolve:
        mock_resolve.return_value = dev_bypass
        app.add_middleware(
            JWTAuthMiddleware,
            jwks_provider=jwks_provider,
            issuer=issuer,
            audience=audience,
            dev_bypass=dev_bypass,
        )
    return app


@pytest.mark.unit
class TestExcludedPaths:
    """Test that excluded paths skip authentication."""

    def test_health_path_skips_auth(self) -> None:
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.unit
class TestMissingToken:
    """Test that missing Authorization header returns 401."""

    def test_missing_auth_header_returns_401(self) -> None:
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 401
        body = response.json()
        assert body["error_code"] == "MISSING_TOKEN"
        assert "WWW-Authenticate" in response.headers

    def test_invalid_format_returns_401(self) -> None:
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"Authorization": "Basic abc"})
        assert response.status_code == 401
        body = response.json()
        assert body["error_code"] == "INVALID_FORMAT"

    def test_empty_bearer_returns_401(self) -> None:
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"Authorization": "Bearer "})
        assert response.status_code == 401

    def test_no_jwks_provider_returns_503(self) -> None:
        app = _make_app(jwks_provider=None)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", headers={"Authorization": "Bearer some.jwt.token"})
        assert response.status_code == 503
        body = response.json()
        assert body["error_code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.unit
class TestValidFlow:
    """Test valid JWT flow with mocked JWKS."""

    def test_valid_token_sets_claims(self) -> None:
        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        test_claims = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "tenant_id": "acme",
            "roles": ["admin"],
            "email": "test@example.com",
            "iss": "https://auth.example.com",
            "aud": "api",
            "exp": 9999999999,
        }

        app = _make_app(jwks_provider=mock_jwks)

        with patch("praecepta.infra.auth.middleware.jwt_auth.pyjwt.decode") as mock_decode:
            mock_decode.return_value = test_claims
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/", headers={"Authorization": "Bearer valid.jwt.token"})

        assert response.status_code == 200
        assert response.json() == {"ok": True}


@pytest.mark.unit
class TestDevBypass:
    """Test dev bypass mode."""

    def test_dev_bypass_injects_claims(self) -> None:
        app = _make_app(dev_bypass=True)
        client = TestClient(app, raise_server_exceptions=False)
        # No Authorization header -> dev bypass should inject synthetic claims
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
