"""Tests for identifier value objects."""

from __future__ import annotations

from uuid import UUID

import pytest

from praecepta.foundation.domain.identifiers import TenantId, UserId


@pytest.mark.unit
class TestTenantId:
    """Tests for TenantId value object."""

    def test_valid_simple_slug(self) -> None:
        tid = TenantId("acme")
        assert tid.value == "acme"

    def test_valid_slug_with_hyphens(self) -> None:
        tid = TenantId("acme-corp")
        assert tid.value == "acme-corp"

    def test_valid_slug_with_numbers(self) -> None:
        tid = TenantId("abc-123")
        assert tid.value == "abc-123"

    def test_valid_single_char(self) -> None:
        tid = TenantId("a")
        assert tid.value == "a"

    def test_valid_single_digit(self) -> None:
        tid = TenantId("1")
        assert tid.value == "1"

    def test_valid_multiple_hyphens(self) -> None:
        tid = TenantId("big-bank-nyc")
        assert tid.value == "big-bank-nyc"

    def test_str_returns_value(self) -> None:
        tid = TenantId("acme-corp")
        assert str(tid) == "acme-corp"

    def test_frozen_immutability(self) -> None:
        tid = TenantId("acme")
        with pytest.raises(AttributeError):
            tid.value = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        assert TenantId("acme") == TenantId("acme")

    def test_inequality(self) -> None:
        assert TenantId("acme") != TenantId("other")

    # --- Invalid formats ---

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("")

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("Acme")

    def test_rejects_underscores(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("acme_corp")

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("acme corp")

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("-acme")

    def test_rejects_trailing_hyphen(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("acme-")

    def test_rejects_consecutive_hyphens(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("acme--corp")

    def test_rejects_special_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("acme@corp")

    def test_rejects_dots(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant ID format"):
            TenantId("acme.corp")


@pytest.mark.unit
class TestUserId:
    """Tests for UserId value object."""

    def test_wraps_uuid(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        user_id = UserId(uid)
        assert user_id.value == uid

    def test_str_returns_uuid_string(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        user_id = UserId(uid)
        assert str(user_id) == "550e8400-e29b-41d4-a716-446655440000"

    def test_frozen_immutability(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        user_id = UserId(uid)
        with pytest.raises(AttributeError):
            user_id.value = UUID("00000000-0000-0000-0000-000000000000")  # type: ignore[misc]

    def test_equality(self) -> None:
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        assert UserId(uid) == UserId(uid)

    def test_inequality(self) -> None:
        uid1 = UUID("550e8400-e29b-41d4-a716-446655440000")
        uid2 = UUID("00000000-0000-0000-0000-000000000000")
        assert UserId(uid1) != UserId(uid2)
