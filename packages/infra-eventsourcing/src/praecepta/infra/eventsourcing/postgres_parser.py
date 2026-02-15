"""Parse DATABASE_URL to individual POSTGRES_* environment variables.

The eventsourcing library does not support DATABASE_URL format. This module
provides utilities to parse connection strings into the required format.

Example:
    >>> from praecepta.infra.eventsourcing.postgres_parser import (
    ...     parse_database_url,
    ... )
    >>> params = parse_database_url("postgresql://user:pass@localhost:5432/mydb")
    >>> params['postgres_dbname']
    'mydb'
"""

from __future__ import annotations

from typing import TypedDict
from urllib.parse import ParseResult, urlparse


class PostgresConnectionParams(TypedDict):
    """Type-safe representation of PostgreSQL connection parameters.

    These parameters map directly to the POSTGRES_* environment variables
    expected by the eventsourcing library.
    """

    postgres_dbname: str
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str


class DatabaseURLParseError(ValueError):
    """Raised when DATABASE_URL cannot be parsed.

    This exception is raised when the connection string is malformed or
    missing required components.
    """


def parse_database_url(database_url: str) -> PostgresConnectionParams:
    """Parse DATABASE_URL connection string to individual parameters.

    Args:
        database_url: PostgreSQL connection string in format:
            postgresql://user:password@host:port/dbname
            postgres://user:password@host:port/dbname

    Returns:
        Dictionary with postgres_dbname, postgres_host, postgres_port,
        postgres_user, postgres_password keys.

    Raises:
        DatabaseURLParseError: If URL is invalid or missing required components.

    Examples:
        >>> params = parse_database_url("postgresql://user:pass@localhost:5432/mydb")
        >>> params['postgres_dbname']
        'mydb'
        >>> params['postgres_port']
        5432

        >>> params = parse_database_url("postgres://user:pass@db.example.com/mydb")
        >>> params['postgres_host']
        'db.example.com'
        >>> params['postgres_port']  # defaults to 5432
        5432
    """
    try:
        parsed: ParseResult = urlparse(database_url)
    except Exception as e:
        msg = f"Invalid DATABASE_URL format: {e}"
        raise DatabaseURLParseError(msg) from e

    # Validate scheme
    if parsed.scheme not in ("postgresql", "postgres"):
        msg = f"Invalid scheme '{parsed.scheme}'. Expected 'postgresql' or 'postgres'."
        raise DatabaseURLParseError(msg)

    # Extract components with validation
    if not parsed.username:
        msg = "DATABASE_URL missing username"
        raise DatabaseURLParseError(msg)

    if not parsed.password:
        msg = "DATABASE_URL missing password"
        raise DatabaseURLParseError(msg)

    if not parsed.hostname:
        msg = "DATABASE_URL missing hostname"
        raise DatabaseURLParseError(msg)

    # Database name from path
    dbname = parsed.path.lstrip("/") if parsed.path else ""
    if not dbname:
        msg = "DATABASE_URL missing database name in path"
        raise DatabaseURLParseError(msg)

    # Port defaults to 5432
    port = parsed.port or 5432

    return PostgresConnectionParams(
        postgres_dbname=dbname,
        postgres_host=parsed.hostname,
        postgres_port=port,
        postgres_user=parsed.username,
        postgres_password=parsed.password,
    )


def parse_database_url_safe(database_url: str | None) -> PostgresConnectionParams | None:
    """Safely parse DATABASE_URL, returning None if invalid or missing.

    This is a lenient version of parse_database_url that returns None
    instead of raising exceptions for invalid input.

    Args:
        database_url: Optional DATABASE_URL connection string.

    Returns:
        Parsed parameters if valid, None otherwise.

    Examples:
        >>> params = parse_database_url_safe(None)
        >>> params is None
        True

        >>> params = parse_database_url_safe("invalid")
        >>> params is None
        True

        >>> params = parse_database_url_safe("postgresql://user:pass@localhost:5432/mydb")
        >>> params is not None
        True
    """
    if not database_url:
        return None

    try:
        return parse_database_url(database_url)
    except DatabaseURLParseError:
        return None
