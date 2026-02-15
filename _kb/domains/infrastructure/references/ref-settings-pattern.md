# Settings Pattern Reference

## Overview

Praecepta uses Pydantic v2 `BaseSettings` for 12-factor environment-based configuration. Each infrastructure package defines its own settings class with a distinct environment variable prefix, validation, and a cached singleton accessor.

---

## Standard Structure

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class MySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MY_",
        extra="ignore",
    )

    field_name: str = Field(default="value", description="What this field controls")

@lru_cache(maxsize=1)
def get_my_settings() -> MySettings:
    return MySettings()
```

Key conventions:
- `extra="ignore"` so unknown environment variables do not cause validation errors
- Every field has a `default` and `description`
- Accessor function uses `@lru_cache(maxsize=1)` for singleton behavior

---

## Env Prefix Convention

| Package | Settings Class | Env Prefix | Example Variable |
|---------|---------------|------------|-----------------|
| infra-fastapi | `AppSettings` | `APP_` | `APP_TITLE`, `APP_DEBUG` |
| infra-fastapi | `CORSSettings` | `CORS_` | `CORS_ALLOW_ORIGINS` |
| infra-auth | `AuthSettings` | `AUTH_` | `AUTH_ISSUER`, `AUTH_DEV_BYPASS` |
| infra-persistence | `DatabaseSettings` | `DATABASE_` | `DATABASE_HOST`, `DATABASE_PASSWORD` |
| infra-observability | `TracingSettings` | _(none, uses aliases)_ | `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_TYPE` |
| infra-observability | `LoggingSettings` | _(none, uses aliases)_ | `LOG_LEVEL`, `ENVIRONMENT` |
| infra-eventsourcing | `EventSourcingSettings` | _(none)_ | `POSTGRES_DBNAME`, `POSTGRES_HOST` |

TracingSettings and LoggingSettings use `env_prefix=""` with `alias` on each field to match standard OpenTelemetry environment variable names (e.g., `OTEL_SERVICE_NAME`).

---

## Singleton Pattern

All settings accessors use `@lru_cache(maxsize=1)` to ensure settings are loaded once per process:

```python
@lru_cache(maxsize=1)
def get_tracing_settings() -> TracingSettings:
    """Get cached TracingSettings instance.

    Clear cache with ``get_tracing_settings.cache_clear()`` for testing.
    """
    return TracingSettings()
```

Some packages use module-level singletons instead (e.g., `DatabaseSettings` is instantiated inside `_get_database_url()`), but `@lru_cache` is the preferred pattern.

---

## Sensitive Fields

Use `repr=False` on fields containing passwords, secrets, or API keys. This prevents them from appearing in logs, debug output, or `repr()`:

```python
# From DatabaseSettings
password: str = Field(
    default="postgres",
    repr=False,
    description="PostgreSQL password",
)

# From AuthSettings
oauth_client_secret: str = Field(
    default="",
    repr=False,  # Security: never log client secret
    description="OAuth application client_secret",
)

# From EventSourcingSettings
postgres_password: str = Field(
    ...,
    repr=False,
    description="PostgreSQL password (hidden in logs)",
)
```

---

## Validation Patterns

### Comma-Separated String Parsing

`CORSSettings` parses comma-separated environment variables into lists:

```python
class CORSSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORS_", extra="ignore")

    allow_origins: list[str] = Field(default=["*"])

    @field_validator("allow_origins", "allow_methods", "allow_headers", mode="before")
    @classmethod
    def _parse_comma_separated(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return v
        return ["*"]
```

Usage: `CORS_ALLOW_ORIGINS=http://localhost:3000,https://app.example.com`

### Normalization Validators

`TracingSettings` and `LoggingSettings` normalize enum-like string fields:

```python
@field_validator("exporter_type", mode="before")
@classmethod
def normalize_exporter_type(cls, v: Any) -> str:
    if isinstance(v, str):
        return v.lower()
    return str(v)

@field_validator("exporter_type")
@classmethod
def validate_exporter_type(cls, v: str) -> str:
    valid_types = {"otlp", "jaeger", "console", "none"}
    if v not in valid_types:
        msg = f"exporter_type must be one of {valid_types}"
        raise ValueError(msg)
    return v
```

### Range Constraints

Numeric fields use Pydantic's `ge`/`le` constraints:

```python
# From AuthSettings
jwks_cache_ttl: int = Field(default=300, ge=30, le=86400)

# From EventSourcingSettings
postgres_pool_size: int = Field(default=5, ge=1, le=50)
```

### Alias Fields

For standard environment variable names that do not match a prefix convention:

```python
class TracingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    service_name: str = Field(
        default="praecepta-app",
        alias="OTEL_SERVICE_NAME",
    )
```

The `populate_by_name=True` config allows construction by field name (`service_name=...`) in addition to alias.

---

## Computed Properties

Settings classes use `@property` for derived values:

```python
# From DatabaseSettings
@property
def database_url(self) -> str:
    return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

# From TracingSettings
@property
def is_enabled(self) -> bool:
    return self.exporter_type != "none"

# From LoggingSettings
@property
def use_json_logs(self) -> bool:
    return self.environment == "production"
```

---

## Testing

Construct settings directly with overrides -- no environment variables needed:

```python
def test_tracing_disabled_by_default():
    settings = TracingSettings()
    assert not settings.is_enabled

def test_cors_parses_comma_separated():
    settings = CORSSettings(allow_origins="http://a.com,http://b.com")
    assert settings.allow_origins == ["http://a.com", "http://b.com"]
```

When testing code that calls `get_*_settings()`, clear the cache between tests:

```python
from praecepta.infra.observability.tracing import get_tracing_settings

def test_with_custom_settings(monkeypatch):
    get_tracing_settings.cache_clear()
    monkeypatch.setenv("OTEL_EXPORTER_TYPE", "console")
    settings = get_tracing_settings()
    assert settings.is_enabled
    # Clean up
    get_tracing_settings.cache_clear()
```

---

## See Also

- PADR-106 -- Settings architecture decision
- [ref-tech-stack.md](ref-tech-stack.md) -- Technology stack overview
