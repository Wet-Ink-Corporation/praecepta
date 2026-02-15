"""Tests for domain exception hierarchy."""

from __future__ import annotations

from uuid import UUID

import pytest

from praecepta.foundation.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    FeatureDisabledError,
    InvalidStateTransitionError,
    NotFoundError,
    ResourceLimitExceededError,
    ValidationError,
)


@pytest.mark.unit
class TestDomainError:
    """Tests for base DomainError."""

    def test_message_and_code(self) -> None:
        err = DomainError("Something failed")
        assert err.message == "Something failed"
        assert err.error_code == "DOMAIN_ERROR"
        assert err.context == {}

    def test_context_dict(self) -> None:
        ctx = {"key": "value", "count": 42}
        err = DomainError("Failed", context=ctx)
        assert err.context == ctx

    def test_str_without_context(self) -> None:
        err = DomainError("Simple failure")
        assert str(err) == "Simple failure"

    def test_str_with_context(self) -> None:
        err = DomainError("Failed", context={"a": "1"})
        assert str(err) == "Failed (a=1)"

    def test_repr(self) -> None:
        err = DomainError("Failed", context={"a": "1"})
        assert "DomainError" in repr(err)
        assert "Failed" in repr(err)

    def test_is_exception(self) -> None:
        assert issubclass(DomainError, Exception)


@pytest.mark.unit
class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_error_code(self) -> None:
        err = NotFoundError("Resource", "abc")
        assert err.error_code == "RESOURCE_NOT_FOUND"

    def test_message_format(self) -> None:
        err = NotFoundError("Tenant", "acme-corp")
        assert str(err).startswith("Tenant not found: acme-corp")

    def test_uuid_resource_id(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        err = NotFoundError("User", uid)
        assert err.resource_type == "User"
        assert err.resource_id == uid
        assert err.context["resource_id"] == str(uid)

    def test_extra_context(self) -> None:
        err = NotFoundError("Resource", "abc", tenant_id="acme")
        assert err.context["tenant_id"] == "acme"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(NotFoundError, DomainError)


@pytest.mark.unit
class TestValidationError:
    """Tests for ValidationError."""

    def test_error_code(self) -> None:
        err = ValidationError("title", "Too short")
        assert err.error_code == "VALIDATION_ERROR"

    def test_field_and_reason(self) -> None:
        err = ValidationError("email", "Invalid format")
        assert err.field == "email"
        assert err.reason == "Invalid format"

    def test_message_format(self) -> None:
        err = ValidationError("name", "Cannot be empty")
        assert "name" in str(err)
        assert "Cannot be empty" in str(err)

    def test_inherits_domain_error(self) -> None:
        assert issubclass(ValidationError, DomainError)


@pytest.mark.unit
class TestConflictError:
    """Tests for ConflictError."""

    def test_error_code(self) -> None:
        err = ConflictError("Duplicate")
        assert err.error_code == "CONFLICT"

    def test_reason(self) -> None:
        err = ConflictError("Already exists")
        assert err.reason == "Already exists"

    def test_message_format(self) -> None:
        err = ConflictError("Lock failure")
        assert "Conflict: Lock failure" in str(err)

    def test_with_context(self) -> None:
        err = ConflictError("Version mismatch", expected=5, actual=7)
        assert err.context["expected"] == 5
        assert err.context["actual"] == 7

    def test_inherits_domain_error(self) -> None:
        assert issubclass(ConflictError, DomainError)


@pytest.mark.unit
class TestInvalidStateTransitionError:
    """Tests for InvalidStateTransitionError."""

    def test_error_code(self) -> None:
        err = InvalidStateTransitionError("Cannot activate")
        assert err.error_code == "INVALID_STATE_TRANSITION"

    def test_inherits_conflict_error(self) -> None:
        assert issubclass(InvalidStateTransitionError, ConflictError)

    def test_inherits_domain_error(self) -> None:
        assert issubclass(InvalidStateTransitionError, DomainError)


@pytest.mark.unit
class TestFeatureDisabledError:
    """Tests for FeatureDisabledError."""

    def test_error_code(self) -> None:
        err = FeatureDisabledError("feature.test", "acme")
        assert err.error_code == "FEATURE_DISABLED"

    def test_attributes(self) -> None:
        err = FeatureDisabledError("feature.dark_mode", "acme-corp")
        assert err.feature_key == "feature.dark_mode"
        assert err.tenant_id == "acme-corp"

    def test_message_format(self) -> None:
        err = FeatureDisabledError("feature.x", "tenant-1")
        assert "feature.x" in str(err)
        assert "tenant-1" in str(err)

    def test_inherits_domain_error(self) -> None:
        assert issubclass(FeatureDisabledError, DomainError)


@pytest.mark.unit
class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_default_error_code(self) -> None:
        err = AuthenticationError("Token missing")
        assert err.error_code == "AUTHENTICATION_ERROR"

    def test_custom_error_code(self) -> None:
        err = AuthenticationError("Expired", error_code="TOKEN_EXPIRED")
        assert err.error_code == "TOKEN_EXPIRED"

    def test_auth_error_field(self) -> None:
        err = AuthenticationError("Bad token", auth_error="invalid_token")
        assert err.auth_error == "invalid_token"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(AuthenticationError, DomainError)


@pytest.mark.unit
class TestAuthorizationError:
    """Tests for AuthorizationError."""

    def test_error_code(self) -> None:
        err = AuthorizationError("Forbidden")
        assert err.error_code == "AUTHORIZATION_ERROR"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(AuthorizationError, DomainError)


@pytest.mark.unit
class TestResourceLimitExceededError:
    """Tests for ResourceLimitExceededError."""

    def test_error_code(self) -> None:
        err = ResourceLimitExceededError("agents", limit=10, current=10)
        assert err.error_code == "RESOURCE_LIMIT_EXCEEDED"

    def test_attributes(self) -> None:
        err = ResourceLimitExceededError("items", limit=100, current=99)
        assert err.resource == "items"
        assert err.limit == 100
        assert err.current == 99

    def test_message_format(self) -> None:
        err = ResourceLimitExceededError("agents", limit=50, current=50)
        assert "50" in str(err)
        assert "agents" in str(err)

    def test_extra_context(self) -> None:
        err = ResourceLimitExceededError("items", limit=10, current=10, tenant_id="acme")
        assert err.context["tenant_id"] == "acme"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(ResourceLimitExceededError, DomainError)
