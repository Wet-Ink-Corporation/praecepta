"""Application settings for the praecepta FastAPI app factory.

Provides Pydantic Settings for FastAPI configuration, CORS policy,
and auto-discovery filtering.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CORSSettings(BaseSettings):
    """CORS policy configuration.

    Environment variables use the ``CORS_`` prefix (e.g., ``CORS_ALLOW_ORIGINS``).
    Comma-separated strings are automatically parsed into lists.
    """

    model_config = SettingsConfigDict(env_prefix="CORS_", extra="ignore")

    allow_origins: list[str] = Field(default=["*"])
    allow_methods: list[str] = Field(default=["*"])
    allow_headers: list[str] = Field(default=["*"])
    allow_credentials: bool = Field(default=False)
    expose_headers: list[str] = Field(default=["X-Request-ID"])

    @field_validator(
        "allow_origins",
        "allow_methods",
        "allow_headers",
        "expose_headers",
        mode="before",
    )
    @classmethod
    def _parse_comma_separated(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return v
        return ["*"]

    @model_validator(mode="after")
    def _validate_credentials_with_wildcard(self) -> CORSSettings:
        if self.allow_credentials and self.allow_origins == ["*"]:
            msg = (
                "CORS allow_credentials=True cannot be used with allow_origins=['*']. "
                "Browsers will reject the response. Specify explicit origins instead."
            )
            raise ValueError(msg)
        return self


def _default_version() -> str:
    """Resolve default app version from package metadata."""
    try:
        from importlib.metadata import version

        return version("praecepta-infra-fastapi")
    except Exception:
        return "0.0.0"


class AppSettings(BaseSettings):
    """Application factory settings.

    Environment variables use the ``APP_`` prefix (e.g., ``APP_TITLE``).
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        extra="ignore",
    )

    title: str = Field(default="Praecepta Application")
    version: str = Field(default=_default_version())
    description: str = Field(default="")
    docs_url: str | None = Field(default="/docs")
    redoc_url: str | None = Field(default="/redoc")
    openapi_url: str | None = Field(default="/openapi.json")
    debug: bool = Field(default=False)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    # Discovery filtering
    exclude_groups: frozenset[str] = Field(default=frozenset())
    exclude_entry_points: frozenset[str] = Field(default=frozenset())
