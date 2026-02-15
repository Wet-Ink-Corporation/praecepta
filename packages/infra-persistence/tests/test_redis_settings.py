"""Unit tests for praecepta.infra.persistence.redis_settings."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praecepta.infra.persistence.redis_settings import RedisSettings


class TestRedisSettings:
    @pytest.mark.unit
    def test_default_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = RedisSettings()
            assert settings.redis_host == "localhost"
            assert settings.redis_port == 6379
            assert settings.redis_db == 0
            assert settings.redis_password is None
            assert settings.redis_pool_size == 10

    @pytest.mark.unit
    def test_get_url_without_password(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = RedisSettings()
            assert settings.get_url() == "redis://localhost:6379/0"

    @pytest.mark.unit
    def test_get_url_with_password(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = RedisSettings(redis_password="secret")
            assert settings.get_url() == "redis://:secret@localhost:6379/0"

    @pytest.mark.unit
    def test_get_url_returns_redis_url_if_set(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = RedisSettings(redis_url="redis://custom:6380/2")
            assert settings.get_url() == "redis://custom:6380/2"

    @pytest.mark.unit
    def test_from_url_basic(self) -> None:
        settings = RedisSettings.from_url("redis://myhost:6380/3")
        assert settings.redis_host == "myhost"
        assert settings.redis_port == 6380
        assert settings.redis_db == 3
        assert settings.redis_url == "redis://myhost:6380/3"

    @pytest.mark.unit
    def test_from_url_with_password(self) -> None:
        settings = RedisSettings.from_url("redis://:mypass@myhost:6380/1")
        assert settings.redis_password == "mypass"
        assert settings.redis_host == "myhost"

    @pytest.mark.unit
    def test_from_url_invalid_scheme(self) -> None:
        with pytest.raises(ValueError, match="Invalid Redis URL scheme"):
            RedisSettings.from_url("http://localhost:6379/0")

    @pytest.mark.unit
    def test_from_url_invalid_db_number(self) -> None:
        with pytest.raises(ValueError, match="Invalid database number"):
            RedisSettings.from_url("redis://localhost:6379/notanumber")

    @pytest.mark.unit
    def test_validate_port_invalid(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            RedisSettings(redis_port=0)

    @pytest.mark.unit
    def test_validate_port_valid(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = RedisSettings(redis_port=6380)
            assert settings.redis_port == 6380
