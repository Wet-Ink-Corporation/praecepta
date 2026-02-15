"""Tests for BaseAggregate."""

from __future__ import annotations

import pytest
from eventsourcing.domain import event

from praecepta.foundation.domain.aggregates import BaseAggregate


class Dog(BaseAggregate):
    """Test aggregate for verifying BaseAggregate behavior."""

    @event("Created")
    def __init__(self, *, name: str, tenant_id: str) -> None:
        self.name = name
        self.tenant_id = tenant_id
        self.tricks: list[str] = []

    @event("TrickAdded")
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)


@pytest.mark.unit
class TestBaseAggregate:
    """Tests for BaseAggregate."""

    def test_tenant_id_set(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        assert dog.tenant_id == "acme-corp"

    def test_name_set(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        assert dog.name == "Fido"

    def test_version_after_creation(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        assert dog.version == 1

    def test_version_after_event(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        dog.add_trick("sit")
        assert dog.version == 2

    def test_collect_events(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        dog.add_trick("roll over")
        events = dog.collect_events()
        assert len(events) == 2

    def test_has_id(self) -> None:
        dog = Dog(name="Fido", tenant_id="acme-corp")
        assert dog.id is not None

    def test_inherits_aggregate(self) -> None:
        from eventsourcing.domain import Aggregate

        assert issubclass(BaseAggregate, Aggregate)
