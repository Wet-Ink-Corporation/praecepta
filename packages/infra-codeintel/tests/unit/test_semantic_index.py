"""Unit tests for LanceDB semantic index helpers."""

from __future__ import annotations

import pytest

from praecepta.infra.codeintel.index.semantic_index import _sql_str


@pytest.mark.unit
class TestSqlStr:
    """Tests for the SQL string escaping helper (S-1)."""

    def test_plain_string_unchanged(self) -> None:
        assert _sql_str("hello") == "hello"

    def test_single_quote_doubled(self) -> None:
        assert _sql_str("O'Brien") == "O''Brien"

    def test_multiple_quotes(self) -> None:
        assert _sql_str("it's a 'test'") == "it''s a ''test''"

    def test_sql_injection_pattern(self) -> None:
        """Classic injection string must be harmlessly escaped."""
        injected = "'; DROP TABLE symbols; --"
        escaped = _sql_str(injected)
        # Must not contain unescaped closing quote before semicolon
        assert escaped == "''; DROP TABLE symbols; --"

    def test_empty_string(self) -> None:
        assert _sql_str("") == ""

    def test_no_quotes_no_change(self) -> None:
        assert _sql_str("mod.auth.login") == "mod.auth.login"
