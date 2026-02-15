"""OpenTelemetry tracing configuration for distributed tracing.

This module provides environment-aware distributed tracing with:
- Configurable exporters (OTLP, Jaeger, Console, None)
- FastAPI auto-instrumentation for HTTP spans
- Service resource attributes (name, version)
- Graceful startup and shutdown

Usage:
    # During application startup (in lifespan handler)
    from praecepta.infra.observability.tracing import configure_tracing
    configure_tracing(app)

    # Shutdown during application shutdown
    from praecepta.infra.observability.tracing import shutdown_tracing
    shutdown_tracing()
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from fastapi import FastAPI

# Module-level variable for TracerProvider reference (needed for shutdown)
_tracer_provider: TracerProvider | None = None


class TracingSettings(BaseSettings):
    """OpenTelemetry tracing configuration from environment variables.

    Loads configuration from environment variables:
    - OTEL_SERVICE_NAME: Service name for traces (default: praecepta-app)
    - OTEL_SERVICE_VERSION: Service version (default: unknown)
    - OTEL_EXPORTER_TYPE: Exporter type - otlp, jaeger, console, none (default: none)
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint
    - OTEL_EXPORTER_OTLP_HEADERS: Auth headers as key1=val1,key2=val2
    - OTEL_EXPORTER_JAEGER_ENDPOINT: Jaeger collector endpoint

    Attributes:
        service_name: Service name for trace resource attributes.
        service_version: Service version for trace resource attributes.
        exporter_type: Exporter type (otlp, jaeger, console, none).
        otlp_endpoint: OTLP collector gRPC endpoint.
        otlp_headers: OTLP auth headers as comma-separated key=value pairs.
        jaeger_endpoint: Jaeger collector HTTP endpoint.

    Example:
        >>> settings = TracingSettings()
        >>> settings.is_enabled
        False  # default is "none"

        >>> settings = TracingSettings(exporter_type="console")
        >>> settings.is_enabled
        True
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    service_name: str = Field(
        default="praecepta-app",
        alias="OTEL_SERVICE_NAME",
        description="Service name for trace resource attributes",
    )
    service_version: str = Field(
        default="unknown",
        alias="OTEL_SERVICE_VERSION",
        description="Service version for trace resource attributes",
    )
    exporter_type: str = Field(
        default="none",
        alias="OTEL_EXPORTER_TYPE",
        description="Exporter type: otlp, jaeger, console, none",
    )
    otlp_endpoint: str = Field(
        default="http://localhost:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description="OTLP collector gRPC endpoint",
    )
    otlp_headers: str = Field(
        default="",
        alias="OTEL_EXPORTER_OTLP_HEADERS",
        description="OTLP auth headers as key1=val1,key2=val2",
    )
    jaeger_endpoint: str = Field(
        default="http://localhost:14268/api/traces",
        alias="OTEL_EXPORTER_JAEGER_ENDPOINT",
        description="Jaeger collector HTTP endpoint",
    )

    @field_validator("exporter_type", mode="before")
    @classmethod
    def normalize_exporter_type(cls, v: Any) -> str:
        """Normalize exporter type to lowercase.

        Args:
            v: Exporter type value.

        Returns:
            Lowercase exporter type string.
        """
        if isinstance(v, str):
            return v.lower()
        return str(v)

    @field_validator("exporter_type")
    @classmethod
    def validate_exporter_type(cls, v: str) -> str:
        """Validate exporter type is a known type.

        Args:
            v: Exporter type string.

        Returns:
            Validated exporter type.

        Raises:
            ValueError: If exporter type is not valid.
        """
        valid_types = {"otlp", "jaeger", "console", "none"}
        if v not in valid_types:
            msg = f"exporter_type must be one of {valid_types}"
            raise ValueError(msg)
        return v

    @property
    def is_enabled(self) -> bool:
        """Check if tracing is enabled.

        Returns:
            True if exporter_type is not "none", False otherwise.
        """
        return self.exporter_type != "none"

    @property
    def otlp_headers_dict(self) -> dict[str, str]:
        """Parse OTLP headers from comma-separated key=value pairs.

        Returns:
            Dictionary of header key-value pairs.

        Example:
            >>> settings = TracingSettings(otlp_headers="key1=val1,key2=val2")
            >>> settings.otlp_headers_dict
            {'key1': 'val1', 'key2': 'val2'}
        """
        if not self.otlp_headers:
            return {}
        result: dict[str, str] = {}
        for pair in self.otlp_headers.split(","):
            if "=" in pair:
                # Split on first = only to handle values with = in them
                key, value = pair.split("=", 1)
                result[key.strip()] = value.strip()
        return result


@lru_cache(maxsize=1)
def get_tracing_settings() -> TracingSettings:
    """Get cached TracingSettings instance.

    Returns singleton TracingSettings instance. Clear cache with
    ``get_tracing_settings.cache_clear()`` for testing.

    Returns:
        Singleton TracingSettings instance.
    """
    return TracingSettings()


def _create_exporter(settings: TracingSettings) -> SpanExporter:
    """Create span exporter based on settings.

    Args:
        settings: TracingSettings with exporter configuration.

    Returns:
        Configured SpanExporter instance.

    Raises:
        ValueError: If exporter_type is not recognized.
    """
    if settings.exporter_type == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(  # type: ignore[no-any-return]
            endpoint=settings.otlp_endpoint,
            headers=settings.otlp_headers_dict if settings.otlp_headers_dict else None,
        )
    elif settings.exporter_type == "jaeger":
        try:
            from opentelemetry.exporter.jaeger.thrift import (  # type: ignore[import-not-found]
                JaegerExporter,
            )

            exporter: SpanExporter = JaegerExporter(
                collector_endpoint=settings.jaeger_endpoint,
            )
            return exporter
        except ImportError as exc:
            msg = (
                "Jaeger exporter not available. "
                "Install with: pip install opentelemetry-exporter-jaeger"
            )
            raise ImportError(msg) from exc
    elif settings.exporter_type == "console":
        return ConsoleSpanExporter()
    else:
        msg = f"Unknown exporter type: {settings.exporter_type}"
        raise ValueError(msg)


def configure_tracing(app: FastAPI, settings: TracingSettings | None = None) -> None:
    """Configure OpenTelemetry tracing for the FastAPI application.

    Initializes the OpenTelemetry SDK with:
    - TracerProvider with service resource attributes
    - BatchSpanProcessor for async span export
    - Configured exporter (OTLP, Jaeger, or Console)
    - FastAPI auto-instrumentation for HTTP spans

    Should be called once during application startup (in lifespan handler)
    AFTER configure_logging() to ensure trace context can bind to structlog.

    Args:
        app: FastAPI application instance for instrumentation.
        settings: Optional TracingSettings. If None, loads from environment.

    Note:
        When exporter_type is "none", this function returns immediately
        without initializing any tracing infrastructure.

    Example:
        >>> from fastapi import FastAPI
        >>> from praecepta.infra.observability.tracing import configure_tracing
        >>> app = FastAPI()
        >>> configure_tracing(app)
    """
    global _tracer_provider

    if settings is None:
        settings = get_tracing_settings()

    # Early exit if tracing is disabled
    if not settings.is_enabled:
        return

    # Create resource with service metadata
    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
        }
    )

    # Create and configure TracerProvider
    provider = TracerProvider(resource=resource)

    # Create exporter and processor
    exporter = _create_exporter(settings)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Store reference for shutdown
    _tracer_provider = provider

    # Instrument FastAPI
    from opentelemetry.instrumentation.fastapi import (  # type: ignore[import-not-found]
        FastAPIInstrumentor,
    )

    FastAPIInstrumentor.instrument_app(app)


def shutdown_tracing() -> None:
    """Gracefully shutdown tracing infrastructure.

    Flushes pending spans and shuts down the TracerProvider.
    Safe to call multiple times (idempotent).

    Should be called during application shutdown (in lifespan handler).

    Example:
        >>> from praecepta.infra.observability.tracing import shutdown_tracing
        >>> shutdown_tracing()  # Flushes and shuts down
        >>> shutdown_tracing()  # Safe to call again (no-op)
    """
    global _tracer_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None
