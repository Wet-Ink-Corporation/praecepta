"""Tests for all value objects (tenant, user, agent)."""

from __future__ import annotations

import pytest

from praecepta.foundation.domain.agent_value_objects import (
    AgentStatus,
    AgentTypeId,
    APIKeyMetadata,
)
from praecepta.foundation.domain.tenant_value_objects import (
    TenantName,
    TenantSlug,
    TenantStatus,
)
from praecepta.foundation.domain.user_value_objects import (
    DisplayName,
    Email,
    OidcSub,
)

# =============================================================================
# Tenant Value Objects
# =============================================================================


@pytest.mark.unit
class TestTenantSlug:
    """Tests for TenantSlug value object."""

    def test_valid_slug(self) -> None:
        slug = TenantSlug("acme-corp")
        assert slug.value == "acme-corp"

    def test_valid_minimum_length(self) -> None:
        slug = TenantSlug("ab")
        assert slug.value == "ab"

    def test_valid_max_length(self) -> None:
        slug = TenantSlug("a" * 63)
        assert slug.value == "a" * 63

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            TenantSlug("a")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            TenantSlug("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            TenantSlug("a" * 64)

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant slug"):
            TenantSlug("Acme")

    def test_rejects_underscore(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant slug"):
            TenantSlug("acme_corp")

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant slug"):
            TenantSlug("-acme")

    def test_frozen(self) -> None:
        slug = TenantSlug("acme")
        with pytest.raises(AttributeError):
            slug.value = "other"  # type: ignore[misc]


@pytest.mark.unit
class TestTenantName:
    """Tests for TenantName value object."""

    def test_valid_name(self) -> None:
        name = TenantName("Acme Corporation")
        assert name.value == "Acme Corporation"

    def test_strips_whitespace(self) -> None:
        name = TenantName("  Acme  ")
        assert name.value == "Acme"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            TenantName("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            TenantName("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            TenantName("a" * 256)

    def test_max_length_ok(self) -> None:
        name = TenantName("a" * 255)
        assert len(name.value) == 255

    def test_frozen(self) -> None:
        name = TenantName("Acme")
        with pytest.raises(AttributeError):
            name.value = "Other"  # type: ignore[misc]


@pytest.mark.unit
class TestTenantStatus:
    """Tests for TenantStatus enum."""

    def test_all_states(self) -> None:
        assert TenantStatus.PROVISIONING == "PROVISIONING"
        assert TenantStatus.ACTIVE == "ACTIVE"
        assert TenantStatus.SUSPENDED == "SUSPENDED"
        assert TenantStatus.DECOMMISSIONED == "DECOMMISSIONED"

    def test_is_str(self) -> None:
        assert isinstance(TenantStatus.ACTIVE, str)


# =============================================================================
# User Value Objects
# =============================================================================


@pytest.mark.unit
class TestOidcSub:
    """Tests for OidcSub value object."""

    def test_valid_sub(self) -> None:
        sub = OidcSub("auth0|12345")
        assert sub.value == "auth0|12345"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            OidcSub("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            OidcSub("x" * 256)

    def test_max_length_ok(self) -> None:
        sub = OidcSub("x" * 255)
        assert len(sub.value) == 255

    def test_frozen(self) -> None:
        sub = OidcSub("sub-1")
        with pytest.raises(AttributeError):
            sub.value = "other"  # type: ignore[misc]


@pytest.mark.unit
class TestEmail:
    """Tests for Email value object."""

    def test_valid_email(self) -> None:
        email = Email("user@example.com")
        assert email.value == "user@example.com"

    def test_empty_is_valid(self) -> None:
        email = Email("")
        assert email.value == ""

    def test_rejects_no_at(self) -> None:
        with pytest.raises(ValueError, match="Invalid email"):
            Email("notanemail")

    def test_rejects_no_domain(self) -> None:
        with pytest.raises(ValueError, match="Invalid email"):
            Email("user@")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            Email("u" * 250 + "@x.com")

    def test_frozen(self) -> None:
        email = Email("a@b.com")
        with pytest.raises(AttributeError):
            email.value = "c@d.com"  # type: ignore[misc]


@pytest.mark.unit
class TestDisplayName:
    """Tests for DisplayName value object."""

    def test_valid_name(self) -> None:
        name = DisplayName("Jane Doe")
        assert name.value == "Jane Doe"

    def test_strips_whitespace(self) -> None:
        name = DisplayName("  Jane  ")
        assert name.value == "Jane"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            DisplayName("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            DisplayName("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            DisplayName("a" * 256)

    def test_frozen(self) -> None:
        name = DisplayName("Jane")
        with pytest.raises(AttributeError):
            name.value = "Other"  # type: ignore[misc]


# =============================================================================
# Agent Value Objects
# =============================================================================


@pytest.mark.unit
class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_active(self) -> None:
        assert AgentStatus.ACTIVE == "active"

    def test_suspended(self) -> None:
        assert AgentStatus.SUSPENDED == "suspended"

    def test_is_str(self) -> None:
        assert isinstance(AgentStatus.ACTIVE, str)


@pytest.mark.unit
class TestAgentTypeId:
    """Tests for AgentTypeId value object."""

    def test_valid_simple(self) -> None:
        atid = AgentTypeId("workflow-bot")
        assert atid.value == "workflow-bot"

    def test_valid_with_underscores(self) -> None:
        atid = AgentTypeId("my_test_agent")
        assert atid.value == "my_test_agent"

    def test_valid_minimum_length(self) -> None:
        atid = AgentTypeId("ab")
        assert atid.value == "ab"

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValueError, match="2-63 characters"):
            AgentTypeId("a")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="2-63 characters"):
            AgentTypeId("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="2-63 characters"):
            AgentTypeId("a" * 64)

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent type"):
            AgentTypeId("WorkflowBot")

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent type"):
            AgentTypeId("-bot")

    def test_rejects_trailing_hyphen(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent type"):
            AgentTypeId("bot-")

    def test_frozen(self) -> None:
        atid = AgentTypeId("bot")
        with pytest.raises(AttributeError):
            atid.value = "other"  # type: ignore[misc]


@pytest.mark.unit
class TestAPIKeyMetadata:
    """Tests for APIKeyMetadata value object."""

    def test_construction(self) -> None:
        meta = APIKeyMetadata(
            key_id="abc12345",
            key_hash="$2b$12$...",
            created_at="2026-01-24T10:00:00Z",
            status="active",
        )
        assert meta.key_id == "abc12345"
        assert meta.key_hash == "$2b$12$..."
        assert meta.created_at == "2026-01-24T10:00:00Z"
        assert meta.status == "active"

    def test_frozen(self) -> None:
        meta = APIKeyMetadata(
            key_id="abc",
            key_hash="hash",
            created_at="2026-01-01",
            status="active",
        )
        with pytest.raises(AttributeError):
            meta.status = "revoked"  # type: ignore[misc]
