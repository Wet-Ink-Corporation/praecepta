"""Structured logging configuration using structlog.

This module provides environment-aware structured logging with:
- JSON output for production environments
- Console output with colors for development
- Automatic correlation ID binding from RequestIdMiddleware
- Sensitive data redaction for security

Usage:
    # During application startup
    from praecepta.infra.observability.logging import configure_logging
    configure_logging()

    # In application code
    from praecepta.infra.observability import get_logger
    logger = get_logger(__name__)
    logger.info("operation_started", user_id="123", action="create")
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from collections.abc import MutableMapping

# Type alias for structlog processor
Processor = structlog.types.Processor

# Sensitive field names for redaction
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "secret",
        "ssn",
        "credit_card",
        "bearer",
        "credential",
    }
)

REDACTED_VALUE: str = "***REDACTED***"


class LoggingSettings(BaseSettings):
    """Logging configuration settings from environment variables.

    Loads configuration from environment variables:
    - LOG_LEVEL: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - ENVIRONMENT: Environment name (development, staging, production, test)

    Attributes:
        log_level: Minimum log level to output. Default: INFO
        environment: Environment name for format selection. Default: development

    Example:
        >>> settings = LoggingSettings()
        >>> settings.use_json_logs
        False  # development uses console format

        >>> settings = LoggingSettings(log_level="DEBUG", environment="production")
        >>> settings.use_json_logs
        True  # production uses JSON format
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Minimum log level to output",
    )
    environment: str = Field(
        default="development",
        alias="ENVIRONMENT",
        description="Environment name for format selection",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: Any) -> str:
        """Normalize log level to uppercase.

        Args:
            v: Log level value (string or other).

        Returns:
            Uppercase log level string.
        """
        if isinstance(v, str):
            return v.upper()
        return str(v)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a known level.

        Args:
            v: Log level string.

        Returns:
            Validated log level.

        Raises:
            ValueError: If log level is not a valid Python logging level.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid_levels:
            msg = f"log_level must be one of {valid_levels}"
            raise ValueError(msg)
        return v

    @property
    def use_json_logs(self) -> bool:
        """Determine if JSON logs should be used.

        Returns:
            True for production environment, False otherwise.
        """
        return self.environment == "production"

    @property
    def log_level_int(self) -> int:
        """Convert log level string to logging module constant.

        Returns:
            Integer log level constant from logging module.
        """
        return getattr(logging, self.log_level, logging.INFO)


class SensitiveDataProcessor:
    """Structlog processor to redact sensitive fields from log context.

    Redacts values for fields matching:
    1. Exact field names in SENSITIVE_FIELDS (case-insensitive)
    2. Field names containing "password" or "token" as substrings

    Example:
        >>> processor = SensitiveDataProcessor()
        >>> event_dict = {"event": "login", "password": "secret123"}
        >>> result = processor(None, "info", event_dict)
        >>> result["password"]
        '***REDACTED***'
    """

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        """Redact sensitive fields in event_dict.

        Args:
            logger: Logger instance (unused).
            method_name: Log method name (unused).
            event_dict: Dictionary of log context fields.

        Returns:
            Modified event_dict with sensitive values redacted.
        """
        for key in list(event_dict.keys()):
            if self._is_sensitive(key):
                event_dict[key] = REDACTED_VALUE
        return event_dict

    def _is_sensitive(self, key: str) -> bool:
        """Check if key indicates sensitive data.

        Args:
            key: Field name to check.

        Returns:
            True if field should be redacted, False otherwise.
        """
        key_lower = key.lower()
        # Exact match against known sensitive field names
        if key_lower in SENSITIVE_FIELDS:
            return True
        # Substring match for compound names (e.g., user_password, auth_token)
        return "password" in key_lower or "token" in key_lower


@lru_cache(maxsize=1)
def get_logging_settings() -> LoggingSettings:
    """Get cached LoggingSettings instance.

    Returns singleton LoggingSettings instance, cached for efficiency.
    Clear cache with ``get_logging_settings.cache_clear()`` for testing.

    Returns:
        Singleton LoggingSettings instance.
    """
    return LoggingSettings()


def configure_logging(settings: LoggingSettings | None = None) -> None:
    """Configure structlog for structured logging.

    Configures structlog with:
    - Context variable merging (for correlation IDs from RequestIdMiddleware)
    - Log level filtering
    - ISO 8601 timestamps (UTC)
    - Sensitive data redaction
    - Environment-aware rendering (JSON for production, console for development)

    Should be called once during application startup (in lifespan handler).

    Args:
        settings: Optional LoggingSettings instance. If not provided,
            settings are loaded from environment variables.

    Example:
        >>> from praecepta.infra.observability.logging import configure_logging
        >>> configure_logging()  # Uses environment variables

        >>> from praecepta.infra.observability.logging import LoggingSettings
        >>> settings = LoggingSettings(log_level="DEBUG", environment="production")
        >>> configure_logging(settings)
    """
    if settings is None:
        settings = get_logging_settings()

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        SensitiveDataProcessor(),
    ]

    # Add format_exc_info before renderer for exception formatting
    processors.append(structlog.processors.format_exc_info)

    # Add renderer based on environment
    if settings.use_json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.typing.WrappedLogger:
    """Get a structlog logger bound to the given name.

    Creates a structured logger that includes the module name in all log
    entries. The logger inherits context from RequestIdMiddleware (request_id)
    and any additional bound context.

    Args:
        name: Logger name (typically __name__ from calling module).
            If None, returns unbound logger.

    Returns:
        Bound structlog logger with name context.

    Example:
        >>> from praecepta.infra.observability import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("request_started", path="/health", method="GET")
    """
    logger = structlog.get_logger()
    if name is not None:
        logger = logger.bind(logger=name)
    return logger
