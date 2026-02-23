"""Unit tests for praecepta.infra.observability.tracing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praecepta.infra.observability.tracing import (
    TracingSettings,
    get_tracing_settings,
    shutdown_tracing,
)


class TestTracingSettings:
    @pytest.mark.unit
    def test_default_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = TracingSettings()
            assert settings.service_name == "praecepta-app"
            assert settings.service_version == "unknown"
            assert settings.exporter_type == "none"
            assert settings.is_enabled is False

    @pytest.mark.unit
    def test_is_enabled_when_console(self) -> None:
        settings = TracingSettings(exporter_type="console")
        assert settings.is_enabled is True

    @pytest.mark.unit
    def test_normalize_exporter_type(self) -> None:
        settings = TracingSettings(exporter_type="CONSOLE")
        assert settings.exporter_type == "console"

    @pytest.mark.unit
    def test_invalid_exporter_type(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            TracingSettings(exporter_type="invalid")

    @pytest.mark.unit
    def test_otlp_headers_dict_empty(self) -> None:
        settings = TracingSettings()
        assert settings.otlp_headers_dict == {}

    @pytest.mark.unit
    def test_otlp_headers_dict_parsed(self) -> None:
        settings = TracingSettings(otlp_headers="key1=val1,key2=val2")
        assert settings.otlp_headers_dict == {"key1": "val1", "key2": "val2"}

    @pytest.mark.unit
    def test_otlp_headers_dict_value_with_equals(self) -> None:
        settings = TracingSettings(otlp_headers="auth=token=abc123")
        assert settings.otlp_headers_dict == {"auth": "token=abc123"}

    @pytest.mark.unit
    def test_from_env_vars(self) -> None:
        env = {
            "OTEL_SERVICE_NAME": "my-service",
            "OTEL_SERVICE_VERSION": "1.0.0",
            "OTEL_EXPORTER_TYPE": "console",
        }
        with patch.dict("os.environ", env, clear=True):
            settings = TracingSettings()
            assert settings.service_name == "my-service"
            assert settings.service_version == "1.0.0"
            assert settings.exporter_type == "console"


class TestTracingSampleRate:
    @pytest.mark.unit
    def test_default_sample_rate(self) -> None:
        settings = TracingSettings()
        assert settings.sample_rate == 1.0

    @pytest.mark.unit
    def test_custom_sample_rate(self) -> None:
        settings = TracingSettings(sample_rate=0.5)
        assert settings.sample_rate == 0.5

    @pytest.mark.unit
    def test_sample_rate_from_env(self) -> None:
        with patch.dict("os.environ", {"OTEL_TRACE_SAMPLE_RATE": "0.25"}, clear=True):
            settings = TracingSettings()
            assert settings.sample_rate == 0.25

    @pytest.mark.unit
    def test_sample_rate_bounds(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            TracingSettings(sample_rate=-0.1)
        with pytest.raises(Exception):  # noqa: B017
            TracingSettings(sample_rate=1.5)

    @pytest.mark.unit
    def test_sampler_passed_to_provider(self) -> None:
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        from praecepta.infra.observability.tracing import configure_tracing

        settings = TracingSettings(exporter_type="console", sample_rate=0.42)
        app = MagicMock()

        # Stub the optional instrumentation module so the import inside
        # configure_tracing succeeds even when the package is not installed.
        fake_mod = ModuleType("opentelemetry.instrumentation.fastapi")
        fake_mod.FastAPIInstrumentor = MagicMock()  # type: ignore[attr-defined]
        sys.modules["opentelemetry.instrumentation"] = ModuleType("opentelemetry.instrumentation")
        sys.modules["opentelemetry.instrumentation.fastapi"] = fake_mod

        try:
            with (
                patch("praecepta.infra.observability.tracing.TracerProvider") as mock_provider_cls,
                patch("praecepta.infra.observability.tracing.trace"),
            ):
                mock_provider = MagicMock()
                mock_provider_cls.return_value = mock_provider

                configure_tracing(app, settings=settings)

                # Verify TracerProvider was called with a TraceIdRatioBased sampler
                call_kwargs = mock_provider_cls.call_args
                sampler = call_kwargs.kwargs.get("sampler") or call_kwargs[1].get("sampler")
                assert isinstance(sampler, TraceIdRatioBased)
        finally:
            sys.modules.pop("opentelemetry.instrumentation.fastapi", None)
            sys.modules.pop("opentelemetry.instrumentation", None)


class TestShutdownTracing:
    @pytest.mark.unit
    def test_shutdown_idempotent(self) -> None:
        # Should not raise even when no provider is set
        shutdown_tracing()
        shutdown_tracing()  # Second call is also safe


class TestGetTracingSettings:
    @pytest.mark.unit
    def test_returns_cached_instance(self) -> None:
        get_tracing_settings.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            s1 = get_tracing_settings()
            s2 = get_tracing_settings()
            assert s1 is s2
        get_tracing_settings.cache_clear()
