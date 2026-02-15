"""Unit tests for praecepta.infra.fastapi.error_handlers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from praecepta.foundation.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    FeatureDisabledError,
    NotFoundError,
    ResourceLimitExceededError,
    ValidationError,
)
from praecepta.infra.fastapi.error_handlers import (
    PROBLEM_MEDIA_TYPE,
    ProblemDetail,
    _is_sensitive_key,
    _sanitize_context,
    _sanitize_value,
    register_exception_handlers,
)


def _make_app() -> FastAPI:
    """Create a minimal app with error handlers registered."""
    app = FastAPI()
    register_exception_handlers(app)
    return app


# ---------------------------------------------------------------------------
# ProblemDetail model tests
# ---------------------------------------------------------------------------


class TestProblemDetail:
    @pytest.mark.unit
    def test_required_fields(self) -> None:
        problem = ProblemDetail(
            type="/errors/test",
            title="Test",
            status=400,
            detail="detail",
        )
        assert problem.type == "/errors/test"
        assert problem.title == "Test"
        assert problem.status == 400
        assert problem.detail == "detail"

    @pytest.mark.unit
    def test_optional_fields_default_none(self) -> None:
        problem = ProblemDetail(
            type="/errors/test",
            title="Test",
            status=400,
            detail="detail",
        )
        assert problem.instance is None
        assert problem.error_code is None
        assert problem.context is None
        assert problem.correlation_id is None

    @pytest.mark.unit
    def test_exclude_none_serialization(self) -> None:
        problem = ProblemDetail(
            type="/errors/test",
            title="Test",
            status=400,
            detail="detail",
        )
        data = problem.model_dump(exclude_none=True)
        assert "instance" not in data
        assert "error_code" not in data
        assert "context" not in data
        assert "correlation_id" not in data


# ---------------------------------------------------------------------------
# Sanitization tests
# ---------------------------------------------------------------------------


class TestSanitization:
    @pytest.mark.unit
    def test_sanitize_context_none(self) -> None:
        assert _sanitize_context(None) is None

    @pytest.mark.unit
    def test_sanitize_context_empty(self) -> None:
        assert _sanitize_context({}) is None

    @pytest.mark.unit
    def test_sanitize_strips_sensitive_keys(self) -> None:
        ctx: dict[str, Any] = {
            "resource_type": "User",
            "password": "secret123",
            "token": "abc",
        }
        result = _sanitize_context(ctx)
        assert result is not None
        assert "resource_type" in result
        assert "password" not in result
        assert "token" not in result

    @pytest.mark.unit
    def test_sanitize_uuid_to_string(self) -> None:
        uid = UUID("12345678-1234-5678-1234-567812345678")
        assert _sanitize_value(uid) == str(uid)

    @pytest.mark.unit
    def test_sanitize_datetime_to_isoformat(self) -> None:
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert _sanitize_value(dt) == dt.isoformat()

    @pytest.mark.unit
    def test_sanitize_redacts_connection_strings(self) -> None:
        text = "postgresql://user:pass@host:5432/db"
        result = _sanitize_value(text)
        assert "user:pass" not in result
        assert "REDACTED" in result

    @pytest.mark.unit
    def test_sanitize_redacts_password_assignment(self) -> None:
        result = _sanitize_value("password=mysecret")
        assert "mysecret" not in result
        assert "REDACTED" in result

    @pytest.mark.unit
    def test_sanitize_nested_dict(self) -> None:
        ctx: dict[str, Any] = {"outer": {"password": "secret", "ok": "value"}}
        result = _sanitize_context(ctx)
        assert result is not None
        inner = result["outer"]
        assert isinstance(inner, dict)
        assert "password" not in inner
        assert inner["ok"] == "value"

    @pytest.mark.unit
    def test_sanitize_list_values(self) -> None:
        uid = UUID("12345678-1234-5678-1234-567812345678")
        result = _sanitize_value([uid, "hello", 42])
        assert result == [str(uid), "hello", 42]

    @pytest.mark.unit
    def test_is_sensitive_key(self) -> None:
        assert _is_sensitive_key("password") is True
        assert _is_sensitive_key("PASSWORD") is True
        assert _is_sensitive_key("secret") is True
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("credential") is True
        assert _is_sensitive_key("name") is False


# ---------------------------------------------------------------------------
# Handler tests — each domain exception maps to the correct HTTP status
# ---------------------------------------------------------------------------


class TestNotFoundHandler:
    @pytest.mark.unit
    def test_returns_404(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise NotFoundError("Widget", "abc-123")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 404
        body = resp.json()
        assert body["type"] == "/errors/not-found"
        assert body["title"] == "Resource Not Found"
        assert body["error_code"] == "RESOURCE_NOT_FOUND"
        assert body["instance"] == "/test"

    @pytest.mark.unit
    def test_content_type(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise NotFoundError("Widget", "abc-123")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert PROBLEM_MEDIA_TYPE in resp.headers["content-type"]


class TestValidationErrorHandler:
    @pytest.mark.unit
    def test_returns_422(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise ValidationError("title", "too short")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 422
        body = resp.json()
        assert body["type"] == "/errors/validation-error"
        assert body["error_code"] == "VALIDATION_ERROR"


class TestConflictErrorHandler:
    @pytest.mark.unit
    def test_returns_409(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise ConflictError("optimistic lock failure", expected_version=5)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 409
        body = resp.json()
        assert body["type"] == "/errors/conflict"
        assert body["error_code"] == "CONFLICT"


class TestFeatureDisabledHandler:
    @pytest.mark.unit
    def test_returns_403(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise FeatureDisabledError("feature.graph_view", "acme-corp")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 403
        body = resp.json()
        assert body["type"] == "/errors/feature-disabled"
        assert body["error_code"] == "FEATURE_DISABLED"


class TestResourceLimitHandler:
    @pytest.mark.unit
    def test_returns_429_with_headers(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise ResourceLimitExceededError("agents", limit=100, current=100)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 429
        body = resp.json()
        assert body["type"] == "/errors/resource-limit-exceeded"
        assert body["error_code"] == "RESOURCE_LIMIT_EXCEEDED"
        assert resp.headers["X-RateLimit-Limit"] == "100"
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        assert resp.headers["Retry-After"] == "3600"


class TestAuthenticationErrorHandler:
    @pytest.mark.unit
    def test_returns_401_with_www_authenticate(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise AuthenticationError(
                "Token expired",
                auth_error="invalid_token",
                error_code="TOKEN_EXPIRED",
            )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 401
        body = resp.json()
        assert body["type"] == "/errors/token-expired"
        assert body["title"] == "Unauthorized"
        assert body["error_code"] == "TOKEN_EXPIRED"

        www_auth = resp.headers["WWW-Authenticate"]
        assert 'realm="API"' in www_auth
        assert 'error="invalid_token"' in www_auth


class TestAuthorizationErrorHandler:
    @pytest.mark.unit
    def test_returns_403(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise AuthorizationError("Missing required role: admin")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 403
        body = resp.json()
        assert body["type"] == "/errors/forbidden"
        assert body["error_code"] == "AUTHORIZATION_ERROR"


class TestDomainErrorFallbackHandler:
    @pytest.mark.unit
    def test_returns_400(self) -> None:
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise DomainError("something went wrong")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 400
        body = resp.json()
        assert body["type"] == "/errors/domain-error"
        assert body["title"] == "Bad Request"


class TestRequestValidationHandler:
    @pytest.mark.unit
    def test_returns_422_for_invalid_body(self) -> None:
        from pydantic import BaseModel

        app = _make_app()

        class Payload(BaseModel):
            name: str

        @app.post("/test")
        def endpoint(body: Payload) -> dict[str, str]:
            return {"name": body.name}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert body["type"] == "/errors/request-validation-error"
        assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
        assert "errors" in body["context"]


class TestUnhandledExceptionHandler:
    @pytest.mark.unit
    def test_returns_500_production_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEBUG", raising=False)
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise RuntimeError("kaboom")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 500
        body = resp.json()
        assert body["type"] == "/errors/internal-error"
        assert body["error_code"] == "INTERNAL_ERROR"
        assert "kaboom" not in body["detail"]
        assert "correlation_id" in body

    @pytest.mark.unit
    def test_returns_500_debug_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEBUG", "true")
        app = _make_app()

        @app.get("/test")
        def endpoint() -> None:
            raise RuntimeError("kaboom")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 500
        body = resp.json()
        assert "RuntimeError" in body["detail"]
        assert "kaboom" in body["detail"]
