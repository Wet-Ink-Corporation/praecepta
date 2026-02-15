"""Integration tests — Dog School domain and API lifecycle."""

from __future__ import annotations

import pytest
from examples.dog_school.domain import Dog

from praecepta.foundation.domain import ValidationError


@pytest.mark.integration
class TestDogSchoolDomain:
    """Domain-level tests: Dog aggregate + events (no HTTP)."""

    def test_create_dog(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        assert dog.name == "Fido"
        assert dog.tenant_id == "acme-corp"
        assert dog.tricks == []
        assert dog.version == 1

    def test_add_trick(self) -> None:
        dog = Dog(name="Buddy", tenant_id="acme-corp")
        dog.add_trick("sit")
        assert dog.tricks == ["sit"]
        assert dog.version == 2
        events = dog.collect_events()
        assert len(events) == 2  # Registered + TrickAdded

    def test_duplicate_trick_raises_validation_error(self) -> None:
        dog = Dog(name="Rex", tenant_id="acme-corp")
        dog.add_trick("roll over")
        with pytest.raises(ValidationError, match="already knows"):
            dog.add_trick("roll over")


@pytest.mark.integration
class TestDogSchoolAPI:
    """Full API lifecycle through create_app() stack."""

    def test_register_and_retrieve(self, client, tenant_headers) -> None:
        resp = client.post("/dogs/", json={"name": "Luna"}, headers=tenant_headers)
        assert resp.status_code == 201
        dog_id = resp.json()["id"]

        resp = client.get(f"/dogs/{dog_id}", headers=tenant_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Luna"
        assert body["tenant_id"] == "acme-corp"
        assert body["tricks"] == []
        assert body["version"] == 1

    def test_learn_tricks_workflow(self, client, tenant_headers) -> None:
        resp = client.post("/dogs/", json={"name": "Max"}, headers=tenant_headers)
        dog_id = resp.json()["id"]

        client.post(f"/dogs/{dog_id}/tricks", json={"trick": "sit"}, headers=tenant_headers)
        client.post(f"/dogs/{dog_id}/tricks", json={"trick": "shake"}, headers=tenant_headers)

        resp = client.get(f"/dogs/{dog_id}", headers=tenant_headers)
        body = resp.json()
        assert body["tricks"] == ["sit", "shake"]
        assert body["version"] == 3  # Registered + 2 tricks

    def test_tenant_id_from_request_context(self, client, tenant_headers) -> None:
        """Tenant ID flows from X-Tenant-ID header into the aggregate."""
        resp = client.post("/dogs/", json={"name": "Spot"}, headers=tenant_headers)
        assert resp.json()["tenant_id"] == "acme-corp"
