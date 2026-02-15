"""Tests for PostgreSQL DATABASE_URL parser."""

from __future__ import annotations

import pytest

from praecepta.infra.eventsourcing.postgres_parser import (
    DatabaseURLParseError,
    parse_database_url,
    parse_database_url_safe,
)


@pytest.mark.unit
class TestParseDatabaseUrl:
    """Tests for parse_database_url()."""

    def test_valid_postgresql_url(self) -> None:
        result = parse_database_url("postgresql://user:pass@localhost:5432/mydb")
        assert result["postgres_dbname"] == "mydb"
        assert result["postgres_host"] == "localhost"
        assert result["postgres_port"] == 5432
        assert result["postgres_user"] == "user"
        assert result["postgres_password"] == "pass"

    def test_valid_postgres_scheme(self) -> None:
        result = parse_database_url("postgres://user:pass@localhost:5432/mydb")
        assert result["postgres_dbname"] == "mydb"

    def test_default_port(self) -> None:
        result = parse_database_url("postgresql://user:pass@dbhost/mydb")
        assert result["postgres_port"] == 5432

    def test_custom_port(self) -> None:
        result = parse_database_url("postgresql://user:pass@dbhost:15432/mydb")
        assert result["postgres_port"] == 15432

    def test_remote_host(self) -> None:
        result = parse_database_url("postgresql://user:pass@db.example.com:5432/prod")
        assert result["postgres_host"] == "db.example.com"
        assert result["postgres_dbname"] == "prod"

    def test_special_chars_in_password(self) -> None:
        result = parse_database_url("postgresql://user:p%40ss%23word@localhost:5432/mydb")
        assert result["postgres_password"] == "p%40ss%23word"

    def test_invalid_scheme_raises(self) -> None:
        with pytest.raises(DatabaseURLParseError, match="Invalid scheme"):
            parse_database_url("mysql://user:pass@localhost:5432/mydb")

    def test_missing_username_raises(self) -> None:
        with pytest.raises(DatabaseURLParseError, match="missing username"):
            parse_database_url("postgresql://:pass@localhost:5432/mydb")

    def test_missing_password_raises(self) -> None:
        with pytest.raises(DatabaseURLParseError, match="missing password"):
            parse_database_url("postgresql://user@localhost:5432/mydb")

    def test_missing_hostname_raises(self) -> None:
        with pytest.raises(DatabaseURLParseError, match="missing hostname"):
            parse_database_url("postgresql://user:pass@/mydb")

    def test_missing_dbname_raises(self) -> None:
        with pytest.raises(DatabaseURLParseError, match="missing database name"):
            parse_database_url("postgresql://user:pass@localhost:5432/")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(DatabaseURLParseError):
            parse_database_url("")

    def test_result_is_typed_dict(self) -> None:
        result = parse_database_url("postgresql://user:pass@localhost:5432/mydb")
        # Verify all expected keys are present
        expected_keys = {
            "postgres_dbname",
            "postgres_host",
            "postgres_port",
            "postgres_user",
            "postgres_password",
        }
        assert set(result.keys()) == expected_keys


@pytest.mark.unit
class TestParseDatabaseUrlSafe:
    """Tests for parse_database_url_safe()."""

    def test_none_returns_none(self) -> None:
        assert parse_database_url_safe(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_database_url_safe("") is None

    def test_invalid_url_returns_none(self) -> None:
        assert parse_database_url_safe("invalid") is None

    def test_invalid_scheme_returns_none(self) -> None:
        assert parse_database_url_safe("mysql://user:pass@localhost/db") is None

    def test_valid_url_returns_params(self) -> None:
        result = parse_database_url_safe("postgresql://user:pass@localhost:5432/mydb")
        assert result is not None
        assert result["postgres_dbname"] == "mydb"
        assert result["postgres_user"] == "user"

    def test_missing_required_field_returns_none(self) -> None:
        assert parse_database_url_safe("postgresql://user@localhost:5432/mydb") is None
