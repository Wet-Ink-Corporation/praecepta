"""Integration tests — RFC 7807 error responses through Dog School."""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestNotFoundError:
    """DogNotFoundError → 404 with RFC 7807 problem details."""

    def test_returns_404(self, client, tenant_headers) -> None:
        resp = client.get(
            "/dogs/00000000-0000-0000-0000-000000000099",
            headers=tenant_headers,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["type"] == "/errors/not-found"
        assert body["title"] == "Resource Not Found"
        assert body["error_code"] == "RESOURCE_NOT_FOUND"
        assert body["status"] == 404
        assert "application/problem+json" in resp.headers["content-type"]


@pytest.mark.integration
class TestValidationError:
    """Duplicate trick → 422 with RFC 7807 problem details."""

    def test_duplicate_trick(self, client, tenant_headers) -> None:
        resp = client.post("/dogs/", json={"name": "Rex"}, headers=tenant_headers)
        dog_id = resp.json()["id"]

        client.post(f"/dogs/{dog_id}/tricks", json={"trick": "sit"}, headers=tenant_headers)
        resp = client.post(
            f"/dogs/{dog_id}/tricks", json={"trick": "sit"}, headers=tenant_headers
        )

        assert resp.status_code == 422
        body = resp.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["type"] == "/errors/validation-error"


@pytest.mark.integration
class TestRequestValidationError:
    """Pydantic request validation → 422 with RFC 7807 problem details."""

    def test_missing_required_field(self, client, tenant_headers) -> None:
        resp = client.post("/dogs/", json={}, headers=tenant_headers)
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
        assert body["type"] == "/errors/request-validation-error"

    def test_invalid_uuid_path_param(self, client, tenant_headers) -> None:
        resp = client.get("/dogs/not-a-uuid", headers=tenant_headers)
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_code"] == "REQUEST_VALIDATION_ERROR"


@pytest.mark.integration
class TestProblemContentType:
    """All error responses use application/problem+json."""

    def test_404_content_type(self, client, tenant_headers) -> None:
        resp = client.get(
            "/dogs/00000000-0000-0000-0000-000000000099",
            headers=tenant_headers,
        )
        assert "application/problem+json" in resp.headers["content-type"]

    def test_422_content_type(self, client, tenant_headers) -> None:
        resp = client.post("/dogs/", json={}, headers=tenant_headers)
        assert "application/problem+json" in resp.headers["content-type"]
