"""Tests for BaseEvent domain event class."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from praecepta.foundation.domain.events import BaseEvent


@dataclass(frozen=True, kw_only=True)
class SampleEvent(BaseEvent):
    """Test event subclass."""

    title: str = "test"


def _make_event(**overrides: object) -> SampleEvent:
    """Create a SampleEvent with sensible defaults."""
    defaults: dict[str, object] = {
        "originator_id": uuid4(),
        "originator_version": 1,
        "timestamp": datetime.now(UTC),
        "tenant_id": "acme-corp",
    }
    defaults.update(overrides)
    return SampleEvent(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestBaseEventTenantValidation:
    """Tests for tenant_id validation on BaseEvent."""

    def test_valid_tenant_id(self) -> None:
        evt = _make_event(tenant_id="acme-corp")
        assert evt.tenant_id == "acme-corp"

    def test_valid_no_hyphens(self) -> None:
        evt = _make_event(tenant_id="contoso")
        assert evt.tenant_id == "contoso"

    def test_valid_multiple_hyphens(self) -> None:
        evt = _make_event(tenant_id="big-bank-nyc")
        assert evt.tenant_id == "big-bank-nyc"

    def test_valid_minimum_length(self) -> None:
        evt = _make_event(tenant_id="a1")
        assert evt.tenant_id == "a1"

    def test_rejects_single_char(self) -> None:
        with pytest.raises(ValueError, match="length must be 2-63"):
            _make_event(tenant_id="a")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="length must be 2-63"):
            _make_event(tenant_id="")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="length must be 2-63"):
            _make_event(tenant_id="a" * 64)

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="must be lowercase"):
            _make_event(tenant_id="Acme")

    def test_rejects_underscore(self) -> None:
        with pytest.raises(ValueError, match="must be lowercase"):
            _make_event(tenant_id="acme_corp")

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="must be lowercase"):
            _make_event(tenant_id="-acme")

    def test_rejects_trailing_hyphen(self) -> None:
        with pytest.raises(ValueError, match="must be lowercase"):
            _make_event(tenant_id="acme-")


@pytest.mark.unit
class TestBaseEventGetTopic:
    """Tests for get_topic() method."""

    def test_base_event_topic(self) -> None:
        topic = BaseEvent.get_topic()
        assert topic == "praecepta.foundation.domain.events:BaseEvent"

    def test_subclass_topic(self) -> None:
        topic = SampleEvent.get_topic()
        # Module will be this test file's module path
        assert ":SampleEvent" in topic


@pytest.mark.unit
class TestBaseEventToDict:
    """Tests for to_dict() serialization."""

    def test_contains_required_keys(self) -> None:
        evt = _make_event()
        d = evt.to_dict()
        assert "originator_id" in d
        assert "originator_version" in d
        assert "timestamp" in d
        assert "tenant_id" in d
        assert "correlation_id" in d
        assert "causation_id" in d
        assert "user_id" in d

    def test_tenant_id_value(self) -> None:
        evt = _make_event(tenant_id="acme-corp")
        d = evt.to_dict()
        assert d["tenant_id"] == "acme-corp"

    def test_optional_fields_default_none(self) -> None:
        evt = _make_event()
        d = evt.to_dict()
        assert d["correlation_id"] is None
        assert d["causation_id"] is None
        assert d["user_id"] is None

    def test_optional_fields_populated(self) -> None:
        evt = _make_event(
            correlation_id="req-123",
            causation_id="evt-456",
            user_id="user-789",
        )
        d = evt.to_dict()
        assert d["correlation_id"] == "req-123"
        assert d["causation_id"] == "evt-456"
        assert d["user_id"] == "user-789"

    def test_originator_id_is_string(self) -> None:
        evt = _make_event()
        d = evt.to_dict()
        assert isinstance(d["originator_id"], str)

    def test_timestamp_is_iso_string(self) -> None:
        ts = datetime(2026, 1, 24, 10, 30, tzinfo=UTC)
        evt = _make_event(timestamp=ts)
        d = evt.to_dict()
        assert d["timestamp"] == "2026-01-24T10:30:00+00:00"


@pytest.mark.unit
class TestBaseEventImmutability:
    """Tests for event immutability."""

    def test_frozen(self) -> None:
        evt = _make_event()
        with pytest.raises(AttributeError):
            evt.tenant_id = "other"  # type: ignore[misc]
