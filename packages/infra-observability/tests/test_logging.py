"""Unit tests for praecepta.infra.observability.logging."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from praecepta.infra.observability.logging import (
    REDACTED_VALUE,
    LoggingSettings,
    SensitiveDataProcessor,
    configure_logging,
    get_logger,
    get_logging_settings,
)


class TestLoggingSettings:
    @pytest.mark.unit
    def test_default_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = LoggingSettings()
            assert settings.log_level == "INFO"
            assert settings.environment == "development"

    @pytest.mark.unit
    def test_use_json_logs_production(self) -> None:
        settings = LoggingSettings(environment="production")
        assert settings.use_json_logs is True

    @pytest.mark.unit
    def test_use_json_logs_development(self) -> None:
        settings = LoggingSettings(environment="development")
        assert settings.use_json_logs is False

    @pytest.mark.unit
    def test_log_level_int(self) -> None:
        settings = LoggingSettings(log_level="DEBUG")
        assert settings.log_level_int == logging.DEBUG

    @pytest.mark.unit
    def test_normalize_log_level_lowercase(self) -> None:
        settings = LoggingSettings(log_level="debug")
        assert settings.log_level == "DEBUG"

    @pytest.mark.unit
    def test_invalid_log_level(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            LoggingSettings(log_level="INVALID")

    @pytest.mark.unit
    def test_from_env_vars(self) -> None:
        env = {"LOG_LEVEL": "WARNING", "ENVIRONMENT": "production"}
        with patch.dict("os.environ", env, clear=True):
            settings = LoggingSettings()
            assert settings.log_level == "WARNING"
            assert settings.environment == "production"


class TestSensitiveDataProcessor:
    @pytest.mark.unit
    def test_redacts_exact_match(self) -> None:
        processor = SensitiveDataProcessor()
        event_dict: dict[str, object] = {"event": "login", "password": "secret123"}
        result = processor(None, "info", event_dict)
        assert result["password"] == REDACTED_VALUE

    @pytest.mark.unit
    def test_redacts_substring_match(self) -> None:
        processor = SensitiveDataProcessor()
        event_dict: dict[str, object] = {
            "event": "auth",
            "user_password": "secret",
        }
        result = processor(None, "info", event_dict)
        assert result["user_password"] == REDACTED_VALUE

    @pytest.mark.unit
    def test_preserves_non_sensitive(self) -> None:
        processor = SensitiveDataProcessor()
        event_dict: dict[str, object] = {"event": "test", "user_id": "123"}
        result = processor(None, "info", event_dict)
        assert result["user_id"] == "123"

    @pytest.mark.unit
    def test_redacts_case_insensitive(self) -> None:
        processor = SensitiveDataProcessor()
        event_dict: dict[str, object] = {"event": "test", "API_KEY": "abc123"}
        result = processor(None, "info", event_dict)
        assert result["API_KEY"] == REDACTED_VALUE


class TestConfigureLogging:
    @pytest.mark.unit
    def test_configure_with_default_settings(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            get_logging_settings.cache_clear()
            configure_logging()
            # Verify structlog is configured (no exception means success)

    @pytest.mark.unit
    def test_configure_with_custom_settings(self) -> None:
        settings = LoggingSettings(log_level="DEBUG", environment="production")
        configure_logging(settings)
        # JSON renderer should be active for production


class TestGetLogger:
    @pytest.mark.unit
    def test_returns_bound_logger(self) -> None:
        configure_logging(LoggingSettings(log_level="DEBUG"))
        logger = get_logger("test.module")
        # Logger should be a structlog bound logger
        assert logger is not None

    @pytest.mark.unit
    def test_returns_unbound_logger_when_no_name(self) -> None:
        configure_logging(LoggingSettings(log_level="DEBUG"))
        logger = get_logger()
        assert logger is not None
