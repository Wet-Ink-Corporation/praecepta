"""Tests for Principal value object."""

from __future__ import annotations

from uuid import UUID

import pytest

from praecepta.foundation.domain.principal import Principal, PrincipalType


@pytest.mark.unit
class TestPrincipalType:
    """Tests for PrincipalType enum."""

    def test_user_value(self) -> None:
        assert PrincipalType.USER == "user"

    def test_agent_value(self) -> None:
        assert PrincipalType.AGENT == "agent"

    def test_is_str(self) -> None:
        assert isinstance(PrincipalType.USER, str)


@pytest.mark.unit
class TestPrincipal:
    """Tests for Principal frozen dataclass."""

    def test_construction_minimal(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        p = Principal(subject="sub-123", tenant_id="acme", user_id=uid)
        assert p.subject == "sub-123"
        assert p.tenant_id == "acme"
        assert p.user_id == uid
        assert p.roles == ()
        assert p.email is None
        assert p.principal_type == PrincipalType.USER

    def test_construction_full(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        p = Principal(
            subject="sub-123",
            tenant_id="acme",
            user_id=uid,
            roles=("admin", "user"),
            email="user@example.com",
            principal_type=PrincipalType.AGENT,
        )
        assert p.roles == ("admin", "user")
        assert p.email == "user@example.com"
        assert p.principal_type == PrincipalType.AGENT

    def test_frozen_immutability(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        p = Principal(subject="sub-123", tenant_id="acme", user_id=uid)
        with pytest.raises(AttributeError):
            p.subject = "other"  # type: ignore[misc]

    def test_frozen_immutability_tenant_id(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        p = Principal(subject="sub-123", tenant_id="acme", user_id=uid)
        with pytest.raises(AttributeError):
            p.tenant_id = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        p1 = Principal(subject="sub", tenant_id="acme", user_id=uid)
        p2 = Principal(subject="sub", tenant_id="acme", user_id=uid)
        assert p1 == p2

    def test_inequality(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        p1 = Principal(subject="sub-1", tenant_id="acme", user_id=uid)
        p2 = Principal(subject="sub-2", tenant_id="acme", user_id=uid)
        assert p1 != p2
