# Deployment Configurations

> Docker Compose and production configurations

---

## Docker Compose (Development)

### Current State (Data Stores Only)

The current `compose.yaml` provides only the data store infrastructure for local development:

```yaml
# compose.yaml (Current)
services:
  postgres:
    image: postgres:17-bookworm
    container_name: {Project}-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-{Project}_dev}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.26-community
    container_name: {Project}-neo4j
    environment:
      NEO4J_AUTH: ${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-password}
    ports:
      - "${NEO4J_HTTP_PORT:-7474}:7474"
      - "${NEO4J_BOLT_PORT:-7687}:7687"
    volumes:
      - neo4j-data:/data

  redis:
    image: redis:7.4-bookworm
    container_name: {Project}-redis
    command: redis-server --save 60 1 --loglevel warning
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis-data:/data

volumes:
  postgres-data:
  neo4j-data:
  redis-data:
```

**Usage:**

```bash
# Start data stores
docker compose up -d

# Run application locally
uv run uvicorn {project}.main:app --reload
```

---

### Future State (Full Stack)

> **NOTE:** This configuration shows the complete production target architecture.
> SpiceDB, workers, and projection runners are not yet implemented.

```yaml
# compose.yaml (Future State - Full Stack)
# NOTE: Current development uses minimal compose.yaml with only data stores.
# This configuration shows the complete production target architecture.

services:
  # =====================
  # APPLICATION SERVICES
  # =====================

  api:
    build: .
    command: uvicorn {project}.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://{Project}:{Project}@postgres:5432/{Project}
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
      - REDIS_URL=redis://redis:6379
      - SPICEDB_ENDPOINT=spicedb:50051
      - SPICEDB_KEY=${SPICEDB_KEY:-somerandomkeyhere}
      - VOYAGE_API_KEY=${VOYAGE_API_KEY}
      - COHERE_API_KEY=${COHERE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./src:/app/src
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_started
      spicedb:
        condition: service_started

  ingestion-worker:
    build: .
    command: python -m {Project}.ingestion.worker
    environment:
      <<: *common-env
    depends_on:
      - api

  graph-projection:
    build: .
    command: python -m {Project}.graph.projection_runner
    environment:
      <<: *common-env
    depends_on:
      - api
    deploy:
      replicas: 1  # Must be single instance

  index-projection:
    build: .
    command: python -m {Project}.query.projection_runner
    environment:
      <<: *common-env
    depends_on:
      - api
    deploy:
      replicas: 1

  # =====================
  # DATA STORES
  # =====================

  postgres:
    image: paradedb/paradedb:latest
    environment:
      POSTGRES_DB: {Project}
      POSTGRES_USER: {Project}
      POSTGRES_PASSWORD: {Project}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {Project}"]
      interval: 10s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-password}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_max__size: 1G
    volumes:
      - neo4j_data:/data
    ports:
      - "7474:7474"
      - "7687:7687"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  spicedb:
    image: authzed/spicedb
    command: serve
    environment:
      SPICEDB_GRPC_PRESHARED_KEY: ${SPICEDB_KEY:-somerandomkeyhere}
      SPICEDB_DATASTORE_ENGINE: memory
    ports:
      - "50051:50051"
      - "8443:8443"  # REST gateway

volumes:
  postgres_data:
  neo4j_data:
  redis_data:

# Shared environment anchor
x-common-env: &common-env
  DATABASE_URL: postgresql://{Project}:{Project}@postgres:5432/{Project}
  NEO4J_URI: bolt://neo4j:7687
  NEO4J_USER: neo4j
  NEO4J_PASSWORD: ${NEO4J_PASSWORD:-password}
  REDIS_URL: redis://redis:6379
  SPICEDB_ENDPOINT: spicedb:50051
  SPICEDB_KEY: ${SPICEDB_KEY:-somerandomkeyhere}
```

---

## Database Initialization

### PostgreSQL Init Script

```sql
-- scripts/init-db.sql

-- Create extension for vector similarity
CREATE EXTENSION IF NOT EXISTS vector;

-- Create extension for BM25 search (ParadeDB)
CREATE EXTENSION IF NOT EXISTS pg_search;

-- Create databases for services
CREATE DATABASE spicedb;

-- Create user for SpiceDB
CREATE USER spicedb WITH PASSWORD 'spicedb';
GRANT ALL PRIVILEGES ON DATABASE spicedb TO spicedb;

-- Event store tables
CREATE TABLE IF NOT EXISTS stored_events (
    id                BIGSERIAL PRIMARY KEY,
    originator_id     UUID NOT NULL,
    originator_version INT NOT NULL,
    topic             TEXT NOT NULL,
    state             BYTEA NOT NULL,
    timestamp         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (originator_id, originator_version)
);

CREATE INDEX idx_events_originator ON stored_events(originator_id);
CREATE INDEX idx_events_topic ON stored_events(topic);

-- Notification log
CREATE TABLE IF NOT EXISTS notification_log (
    id              BIGSERIAL PRIMARY KEY,
    notification_id UUID NOT NULL UNIQUE,
    topic           TEXT NOT NULL,
    state           BYTEA NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_topic ON notification_log(topic);

-- Vector index table
CREATE TABLE IF NOT EXISTS chunk_vectors (
    chunk_id        UUID PRIMARY KEY,
    document_id     UUID NOT NULL,
    embedding       vector(1024),
    acl_principals  TEXT[] NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunk_vectors_embedding ON chunk_vectors
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_chunk_vectors_acl ON chunk_vectors
    USING GIN (acl_principals);
```

---

## SpiceDB Schema

```zed
-- schema.zed

definition user {}

definition group {
    relation member: user
}

definition tenant {
    relation admin: user
    relation member: user | group#member

    permission manage = admin
    permission view = member + admin
}

definition folder {
    relation owner: user
    relation parent: folder
    relation viewer: user | group#member | tenant#member

    permission view = viewer + owner + parent->view
    permission edit = owner + parent->edit
}

definition document {
    relation owner: user
    relation parent: folder
    relation viewer: user | group#member | tenant#member

    permission view = viewer + owner + parent->view
    permission edit = owner
}

definition chunk {
    relation parent: document

    permission view = parent->view
}

definition memory_block {
    relation owner: user
    relation participant: user | group#member

    permission view = participant + owner
    permission edit = owner
    permission manage = owner
    permission add_content = participant + owner
}

definition entity {
    relation source: document

    permission view = source->view
}
```

---

## Environment Variables

### Development (.env)

```bash
# Database
POSTGRES_PASSWORD={Project}
NEO4J_PASSWORD=password

# Security
SPICEDB_KEY=dev-key-change-in-production
JWT_SECRET=dev-jwt-secret-change-in-production

# AI Services (required)
VOYAGE_API_KEY=your-voyage-api-key
COHERE_API_KEY=your-cohere-api-key
OPENAI_API_KEY=your-openai-api-key

# Observability (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
LOG_LEVEL=DEBUG
```

### Production

```bash
# Database (from Azure Key Vault)
DATABASE_URL=${KV_DATABASE_URL}
NEO4J_URI=${KV_NEO4J_URI}
NEO4J_PASSWORD=${KV_NEO4J_PASSWORD}
REDIS_URL=${KV_REDIS_URL}

# Security (from Key Vault)
SPICEDB_KEY=${KV_SPICEDB_KEY}
JWT_PUBLIC_KEY=${KV_JWT_PUBLIC_KEY}

# AI Services (from Key Vault)
VOYAGE_API_KEY=${KV_VOYAGE_API_KEY}
COHERE_API_KEY=${KV_COHERE_API_KEY}
OPENAI_API_KEY=${KV_OPENAI_API_KEY}

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.internal:4317
LOG_LEVEL=INFO
APPLICATIONINSIGHTS_CONNECTION_STRING=${KV_APPINSIGHTS_CONN}
```

---

## Azure Container Apps (Production)

### Bicep Template

```bicep
// infrastructure/main.bicep

param location string = resourceGroup().location
param environmentName string
param containerAppEnvName string = '${environmentName}-env'

// Container App Environment
resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    daprAIConnectionString: applicationInsights.properties.ConnectionString
    zoneRedundant: true
  }
}

// API Container App
resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${environmentName}-api'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      secrets: [
        { name: 'database-url', keyVaultUrl: '${keyVault.properties.vaultUri}secrets/database-url' }
        { name: 'voyage-api-key', keyVaultUrl: '${keyVault.properties.vaultUri}secrets/voyage-api-key' }
        // ... other secrets
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${containerRegistry.properties.loginServer}/{Project}:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'VOYAGE_API_KEY', secretRef: 'voyage-api-key' }
            // ... other env vars
          ]
        }
      ]
      scale: {
        minReplicas: 3
        maxReplicas: 10
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// Worker Container Apps (similar pattern)
resource ingestionWorker 'Microsoft.App/containerApps@2023-05-01' = {
  // ... ingestion worker configuration
}

resource graphProjection 'Microsoft.App/containerApps@2023-05-01' = {
  // Single replica for ordering
  properties: {
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}
```

---

## Health Checks

### API Health Endpoint

```python
# src/{project}/api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Comprehensive health check."""
    checks = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    # Overall status
    healthy = all(v == "healthy" for v in checks.values())

    return {
        "status": "healthy" if healthy else "unhealthy",
        "checks": checks,
    }

@router.get("/ready")
async def readiness_check():
    """Quick readiness probe."""
    return {"status": "ready"}

@router.get("/live")
async def liveness_check():
    """Quick liveness probe."""
    return {"status": "alive"}
```

---

## See Also

- [Infrastructure](con-infrastructure.md) - Service topology
- [Deployment Procedure](proc-deployment-procedure.md) - Step-by-step guide
- [Observability](../../observability/references/con-observability.md) - Monitoring configuration
