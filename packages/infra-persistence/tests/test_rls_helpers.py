"""Unit tests for praecepta.infra.persistence.rls_helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praecepta.infra.persistence.rls_helpers import (
    _validate_identifier,
    create_tenant_isolation_policy,
    disable_rls,
    drop_tenant_isolation_policy,
    enable_rls,
)


class TestEnableRls:
    @pytest.mark.unit
    def test_enable_without_force(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            enable_rls("my_table")
            mock_op.execute.assert_called_once_with(
                "ALTER TABLE my_table ENABLE ROW LEVEL SECURITY"
            )

    @pytest.mark.unit
    def test_enable_with_force(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            enable_rls("my_table", force=True)
            assert mock_op.execute.call_count == 2
            mock_op.execute.assert_any_call("ALTER TABLE my_table ENABLE ROW LEVEL SECURITY")
            mock_op.execute.assert_any_call("ALTER TABLE my_table FORCE ROW LEVEL SECURITY")


class TestDisableRls:
    @pytest.mark.unit
    def test_disable(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            disable_rls("my_table")
            mock_op.execute.assert_called_once_with(
                "ALTER TABLE my_table DISABLE ROW LEVEL SECURITY"
            )


class TestCreateTenantIsolationPolicy:
    @pytest.mark.unit
    def test_default_policy_name(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            create_tenant_isolation_policy("my_table")
            sql = mock_op.execute.call_args[0][0]
            assert "tenant_isolation_policy" in sql
            assert "my_table" in sql
            assert "current_setting('app.current_tenant', true)" in sql

    @pytest.mark.unit
    def test_with_cast_type(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            create_tenant_isolation_policy("my_table", cast_type="uuid")
            sql = mock_op.execute.call_args[0][0]
            assert "::uuid" in sql

    @pytest.mark.unit
    def test_custom_policy_name(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            create_tenant_isolation_policy("my_table", policy_name="custom_policy")
            sql = mock_op.execute.call_args[0][0]
            assert "custom_policy" in sql


class TestDropTenantIsolationPolicy:
    @pytest.mark.unit
    def test_default_policy_name(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            drop_tenant_isolation_policy("my_table")
            mock_op.execute.assert_called_once_with(
                "DROP POLICY IF EXISTS tenant_isolation_policy ON my_table"
            )

    @pytest.mark.unit
    def test_custom_policy_name(self) -> None:
        with patch("praecepta.infra.persistence.rls_helpers.op") as mock_op:
            drop_tenant_isolation_policy("my_table", policy_name="custom_policy")
            mock_op.execute.assert_called_once_with(
                "DROP POLICY IF EXISTS custom_policy ON my_table"
            )


class TestValidateIdentifier:
    @pytest.mark.unit
    def test_valid_identifiers(self) -> None:
        assert _validate_identifier("my_table") == "my_table"
        assert _validate_identifier("users") == "users"
        assert _validate_identifier("tenant_isolation_policy") == "tenant_isolation_policy"
        assert _validate_identifier("uuid") == "uuid"
        assert _validate_identifier("_private") == "_private"

    @pytest.mark.unit
    def test_rejects_semicolons(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("my_table; DROP TABLE users")

    @pytest.mark.unit
    def test_rejects_quotes(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("my_table'--")

    @pytest.mark.unit
    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("my table")

    @pytest.mark.unit
    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("MyTable")

    @pytest.mark.unit
    def test_rejects_dashes(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("my-table")

    @pytest.mark.unit
    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("")

    @pytest.mark.unit
    def test_rejects_starts_with_number(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            _validate_identifier("1table")


class TestSqlInjectionPrevention:
    @pytest.mark.unit
    def test_enable_rls_rejects_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            enable_rls("users; DROP TABLE users")

    @pytest.mark.unit
    def test_disable_rls_rejects_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            disable_rls("users; DROP TABLE users")

    @pytest.mark.unit
    def test_create_policy_rejects_table_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            create_tenant_isolation_policy("users; DROP TABLE users")

    @pytest.mark.unit
    def test_create_policy_rejects_cast_type_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            create_tenant_isolation_policy("my_table", cast_type="uuid; DROP TABLE users")

    @pytest.mark.unit
    def test_create_policy_rejects_policy_name_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            create_tenant_isolation_policy("my_table", policy_name="pol'; DROP TABLE users--")

    @pytest.mark.unit
    def test_drop_policy_rejects_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL"):
            drop_tenant_isolation_policy("users; DROP TABLE users")
