"""Unit tests for praecepta.foundation.application.context."""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.foundation.application.context import (
    NoRequestContextError,
    RequestContext,
    clear_principal_context,
    clear_request_context,
    get_current_context,
    get_current_correlation_id,
    get_current_principal,
    get_current_tenant_id,
    get_current_user_id,
    get_optional_principal,
    set_principal_context,
    set_request_context,
)
from praecepta.foundation.domain.principal import Principal, PrincipalType


class TestRequestContext:
    @pytest.mark.unit
    def test_construction(self) -> None:
        uid = uuid4()
        ctx = RequestContext(
            tenant_id="acme-corp",
            user_id=uid,
            correlation_id="corr-123",
        )
        assert ctx.tenant_id == "acme-corp"
        assert ctx.user_id == uid
        assert ctx.correlation_id == "corr-123"

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        ctx = RequestContext(
            tenant_id="t",
            user_id=uuid4(),
            correlation_id="c",
        )
        with pytest.raises(AttributeError):
            ctx.tenant_id = "other"  # type: ignore[misc]


class TestRequestContextLifecycle:
    @pytest.mark.unit
    def test_get_raises_when_no_context(self) -> None:
        with pytest.raises(NoRequestContextError):
            get_current_context()

    @pytest.mark.unit
    def test_set_get_clear_lifecycle(self) -> None:
        uid = uuid4()
        token = set_request_context("tenant-1", uid, "corr-abc")
        try:
            ctx = get_current_context()
            assert ctx.tenant_id == "tenant-1"
            assert ctx.user_id == uid
            assert ctx.correlation_id == "corr-abc"
        finally:
            clear_request_context(token)

        # After clear, should raise
        with pytest.raises(NoRequestContextError):
            get_current_context()

    @pytest.mark.unit
    def test_get_current_tenant_id(self) -> None:
        token = set_request_context("my-tenant", uuid4(), "c")
        try:
            assert get_current_tenant_id() == "my-tenant"
        finally:
            clear_request_context(token)

    @pytest.mark.unit
    def test_get_current_user_id(self) -> None:
        uid = uuid4()
        token = set_request_context("t", uid, "c")
        try:
            assert get_current_user_id() == uid
        finally:
            clear_request_context(token)

    @pytest.mark.unit
    def test_get_current_correlation_id(self) -> None:
        token = set_request_context("t", uuid4(), "my-corr")
        try:
            assert get_current_correlation_id() == "my-corr"
        finally:
            clear_request_context(token)

    @pytest.mark.unit
    def test_tenant_id_raises_without_context(self) -> None:
        with pytest.raises(NoRequestContextError):
            get_current_tenant_id()

    @pytest.mark.unit
    def test_user_id_raises_without_context(self) -> None:
        with pytest.raises(NoRequestContextError):
            get_current_user_id()

    @pytest.mark.unit
    def test_correlation_id_raises_without_context(self) -> None:
        with pytest.raises(NoRequestContextError):
            get_current_correlation_id()


class TestPrincipalContext:
    def _make_principal(self) -> Principal:
        return Principal(
            subject="user|abc",
            tenant_id="acme",
            user_id=uuid4(),
            roles=("admin",),
            email="user@acme.com",
            principal_type=PrincipalType.USER,
        )

    @pytest.mark.unit
    def test_get_principal_raises_without_context(self) -> None:
        with pytest.raises(NoRequestContextError):
            get_current_principal()

    @pytest.mark.unit
    def test_set_get_clear_principal(self) -> None:
        principal = self._make_principal()
        token = set_principal_context(principal)
        try:
            result = get_current_principal()
            assert result.subject == principal.subject
            assert result.tenant_id == principal.tenant_id
        finally:
            clear_principal_context(token)

        # After clear, should raise
        with pytest.raises(NoRequestContextError):
            get_current_principal()

    @pytest.mark.unit
    def test_get_optional_principal_returns_none(self) -> None:
        assert get_optional_principal() is None

    @pytest.mark.unit
    def test_get_optional_principal_returns_principal(self) -> None:
        principal = self._make_principal()
        token = set_principal_context(principal)
        try:
            result = get_optional_principal()
            assert result is not None
            assert result.subject == principal.subject
        finally:
            clear_principal_context(token)

    @pytest.mark.unit
    def test_isolated_between_tests_1(self) -> None:
        """Verify no state leaks from previous tests."""
        assert get_optional_principal() is None
        with pytest.raises(NoRequestContextError):
            get_current_context()

    @pytest.mark.unit
    def test_isolated_between_tests_2(self) -> None:
        """Verify no state leaks from previous tests (run after _1)."""
        assert get_optional_principal() is None
        with pytest.raises(NoRequestContextError):
            get_current_context()
