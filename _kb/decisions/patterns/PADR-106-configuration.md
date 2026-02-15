<!-- Derived from {Project} PADR-106-configuration -->
# PADR-106: Configuration Management

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Pattern, Operations

---

## Context

{Project} requires configuration management that:

- Supports multiple environments (development, staging, production)
- Validates configuration at startup
- Handles secrets securely
- Provides type safety for configuration values
- Enables easy testing with different configurations

## Decision

**We will use Pydantic Settings** for configuration management with environment variable loading and validation.

### Configuration Structure

```
config/
├── __init__.py
├── settings.py          # Main settings class
├── database.py          # Database-specific settings
├── security.py          # Security settings
├── observability.py     # Logging/tracing settings
└── features.py          # Feature flags

.env                     # Local development (not committed)
.env.example             # Template for developers
```

### Settings Implementation

**Real-World Example: Event Sourcing Configuration**

```python
# src/{Project}/shared/infrastructure/config/eventsourcing.py
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class EventSourcingSettings(BaseSettings):
    """Configuration for eventsourcing library with PostgreSQL.

    Implemented in S-000-002-001 as foundational infrastructure.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL connection (required by eventsourcing library)
    postgres_dbname: str = Field(..., description="PostgreSQL database name")
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(..., description="PostgreSQL user")
    postgres_password: str = Field(
        ...,
        repr=False,  # Hidden in logs/repr
        description="PostgreSQL password"
    )

    # Connection pooling
    postgres_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Base connection pool size"
    )
    postgres_max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Additional connections beyond pool size"
    )

    # Table management
    create_table: bool = Field(
        default=True,
        description="Auto-create tables (dev: true, prod: false)"
    )

    @field_validator("postgres_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate PostgreSQL port is in valid range."""
        if not 1 <= v <= 65535:
            msg = "postgres_port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    @field_validator("create_table")
    @classmethod
    def validate_create_table_for_production(cls, v: bool) -> bool:
        """Warn if CREATE_TABLE=true in production."""
        import os
        import warnings

        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production" and v:
            warnings.warn(
                "CREATE_TABLE=true in production. Use migrations instead.",
                UserWarning,
                stacklevel=2,
            )
        return v

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment dict for eventsourcing Factory."""
        return {
            "POSTGRES_DBNAME": self.postgres_dbname,
            "POSTGRES_HOST": self.postgres_host,
            "POSTGRES_PORT": str(self.postgres_port),
            "POSTGRES_USER": self.postgres_user,
            "POSTGRES_PASSWORD": self.postgres_password,
            "POSTGRES_POOL_SIZE": str(self.postgres_pool_size),
            "POSTGRES_MAX_OVERFLOW": str(self.postgres_max_overflow),
            "CREATE_TABLE": str(self.create_table).lower(),
        }
```

**Generic Database Settings Pattern:**

```python
# config/settings.py (for application-level database connections)
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "{Project}"
    user: str = "{Project}"
    password: str = Field(..., repr=False)  # Required, hidden in logs
    pool_min: int = 5
    pool_max: int = 20

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

class Neo4jSettings(BaseSettings):
    """Neo4j connection settings."""
    model_config = SettingsConfigDict(env_prefix="NEO4J_")

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = Field(..., repr=False)

class SecuritySettings(BaseSettings):
    """Security and authentication settings."""
    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    jwt_secret: str = Field(..., repr=False)
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    spicedb_endpoint: str = "localhost:50051"
    spicedb_token: str = Field(..., repr=False)

class ObservabilitySettings(BaseSettings):
    """Observability and logging settings."""
    model_config = SettingsConfigDict(env_prefix="OTEL_")

    service_name: str = "{Project}"
    exporter_endpoint: str = "http://localhost:4317"
    log_level: str = "INFO"
    log_format: str = "json"  # or "console"

class EmbeddingSettings(BaseSettings):
    """Embedding and retrieval settings."""
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    provider: str = "voyage"  # or "openai"
    model: str = "voyage-3"
    api_key: str = Field(..., repr=False)
    dimensions: int = 1024

class FeatureFlags(BaseSettings):
    """Feature flags for gradual rollout."""
    model_config = SettingsConfigDict(env_prefix="FEATURE_")

    graph_search_enabled: bool = True
    async_projections: bool = True
    rate_limiting: bool = True

class Settings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )

    # Application
    app_name: str = "{Project}"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Environment Files

```bash
# .env.example (committed to repo)
# Application
ENVIRONMENT=development
DEBUG=true

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME={Project}
DB_USER={Project}
DB_PASSWORD=change_me_in_production

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_me

# Security
SECURITY_JWT_SECRET=development_secret_change_in_production
SECURITY_SPICEDB_ENDPOINT=localhost:50051
SECURITY_SPICEDB_TOKEN=dev_token

# Embeddings
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-3
EMBEDDING_API_KEY=your_api_key_here

# Observability
OTEL_SERVICE_NAME={Project}
OTEL_EXPORTER_ENDPOINT=http://localhost:4317
OTEL_LOG_LEVEL=DEBUG
OTEL_LOG_FORMAT=console

# Features
FEATURE_GRAPH_SEARCH_ENABLED=true
FEATURE_ASYNC_PROJECTIONS=true
```

## Usage Patterns

### Dependency Injection

```python
# api/dependencies.py
from fastapi import Depends
from functools import lru_cache

from config.settings import Settings, get_settings

def get_db_connection(settings: Settings = Depends(get_settings)):
    """Get database connection from settings."""
    return create_connection(settings.database.url)

def get_security_service(settings: Settings = Depends(get_settings)):
    """Get configured security service."""
    return SecurityService(
        spicedb_endpoint=settings.security.spicedb_endpoint,
        spicedb_token=settings.security.spicedb_token
    )
```

### In Handlers

```python
from config.settings import get_settings

settings = get_settings()

class CreateBlockHandler:
    def __init__(self):
        self._db_url = settings.database.url
        # Or better: inject via DI
```

### Testing with Override

```python
# tests/conftest.py
import pytest
from config.settings import Settings, get_settings

@pytest.fixture
def test_settings():
    """Override settings for testing."""
    return Settings(
        environment="test",
        debug=True,
        database=DatabaseSettings(
            host="localhost",
            port=5433,  # Test database port
            name="{project}_test",
            password="test"
        ),
        security=SecuritySettings(
            jwt_secret="test_secret",
            spicedb_token="test_token"
        )
    )

@pytest.fixture
def app(test_settings):
    """Create app with test settings."""
    from main import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    return app
```

## Secrets Management

### Development

Use `.env` file (not committed):

```bash
# .env
DB_PASSWORD=my_dev_password
SECURITY_JWT_SECRET=my_dev_secret
```

### Production

Use environment variables or secrets manager:

```python
# config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if os.getenv("ENVIRONMENT") != "production" else None,
        secrets_dir="/run/secrets" if os.getenv("ENVIRONMENT") == "production" else None
    )
```

### Docker Secrets

```yaml
# compose.yaml
services:
  {Project}:
    secrets:
      - db_password
      - jwt_secret
    environment:
      - DB_PASSWORD_FILE=/run/secrets/db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

## Validation

### Startup Validation

```python
# main.py
from config.settings import get_settings
from pydantic import ValidationError

def create_app():
    try:
        settings = get_settings()
    except ValidationError as e:
        print("Configuration error:")
        for error in e.errors():
            print(f"  - {error['loc']}: {error['msg']}")
        raise SystemExit(1)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug
    )

    # ... configure app with settings

    return app
```

### Custom Validators

```python
from pydantic import field_validator, model_validator

class DatabaseSettings(BaseSettings):
    pool_min: int = 5
    pool_max: int = 20

    @model_validator(mode='after')
    def validate_pool_sizes(self) -> 'DatabaseSettings':
        if self.pool_min > self.pool_max:
            raise ValueError("pool_min must be <= pool_max")
        return self

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("port must be between 1 and 65535")
        return v
```

## Feature Flags

```python
# Usage in code
from config.settings import get_settings

settings = get_settings()

class HybridRetriever:
    async def retrieve(self, query: str, user_principals: list[str]):
        results = []

        # Vector search always enabled
        results.append(await self._vector_search(query, user_principals))

        # Graph search is feature-flagged
        if settings.features.graph_search_enabled:
            results.append(await self._graph_search(query, user_principals))

        return self._fusion(results)
```

## Environment-Specific Configuration

```python
# config/environments.py
from config.settings import Settings

def get_development_settings() -> Settings:
    return Settings(
        environment="development",
        debug=True,
        observability=ObservabilitySettings(
            log_level="DEBUG",
            log_format="console"
        )
    )

def get_production_settings() -> Settings:
    return Settings(
        environment="production",
        debug=False,
        observability=ObservabilitySettings(
            log_level="INFO",
            log_format="json"
        )
    )
```

## Related Decisions

- PADR-105: Observability (observability settings)
- PADR-104: Testing (test configuration overrides)

## References

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [12-Factor App - Config](https://12factor.net/config)
