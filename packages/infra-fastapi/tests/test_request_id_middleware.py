"""Unit tests for praecepta.infra.fastapi.middleware.request_id."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from praecepta.infra.fastapi.middleware.request_id import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    _is_valid_uuid,
    get_request_id,
    request_id_ctx,
)


def _make_app() -> FastAPI:
    """Create a minimal app with RequestIdMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/test")
    def test_endpoint() -> dict[str, str]:
        return {"request_id": get_request_id()}

    return app


class TestIsValidUUID:
    @pytest.mark.unit
    def test_valid_uuid4(self) -> None:
        assert _is_valid_uuid(str(uuid.uuid4())) is True

    @pytest.mark.unit
    def test_valid_uuid1(self) -> None:
        assert _is_valid_uuid(str(uuid.uuid1())) is True

    @pytest.mark.unit
    def test_none(self) -> None:
        assert _is_valid_uuid(None) is False

    @pytest.mark.unit
    def test_empty_string(self) -> None:
        assert _is_valid_uuid("") is False

    @pytest.mark.unit
    def test_invalid_format(self) -> None:
        assert _is_valid_uuid("not-a-uuid") is False

    @pytest.mark.unit
    def test_partial_uuid(self) -> None:
        assert _is_valid_uuid("12345678-1234") is False


class TestRequestIdMiddleware:
    @pytest.mark.unit
    def test_generates_uuid_when_no_header(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        # Response should have X-Request-ID header
        response_id = resp.headers[REQUEST_ID_HEADER]
        assert _is_valid_uuid(response_id)
        # Body should contain the same request ID
        assert resp.json()["request_id"] == response_id

    @pytest.mark.unit
    def test_extracts_valid_uuid_from_header(self) -> None:
        app = _make_app()
        client = TestClient(app)
        expected_id = str(uuid.uuid4())
        resp = client.get("/test", headers={REQUEST_ID_HEADER: expected_id})
        assert resp.status_code == 200
        assert resp.headers[REQUEST_ID_HEADER] == expected_id
        assert resp.json()["request_id"] == expected_id

    @pytest.mark.unit
    def test_replaces_invalid_uuid_with_generated(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/test", headers={REQUEST_ID_HEADER: "not-a-uuid"})
        assert resp.status_code == 200
        response_id = resp.headers[REQUEST_ID_HEADER]
        # Should be a valid UUID (not the original invalid value)
        assert _is_valid_uuid(response_id)
        assert response_id != "not-a-uuid"

    @pytest.mark.unit
    def test_adds_response_header(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/test")
        assert REQUEST_ID_HEADER in resp.headers

    @pytest.mark.unit
    def test_context_var_reset_after_request(self) -> None:
        app = _make_app()
        client = TestClient(app)
        client.get("/test")
        # After the request completes, the context var should be reset
        assert request_id_ctx.get() == ""

    @pytest.mark.unit
    def test_get_request_id_outside_context(self) -> None:
        # Outside of middleware, get_request_id returns empty string
        assert get_request_id() == ""
