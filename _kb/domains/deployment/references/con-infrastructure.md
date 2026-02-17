# Infrastructure

> Container topology, services, and databases

---

## Overview

{Project} deploys as a modular monolith with multiple supporting services. The architecture supports both local development (Docker Compose) and production deployment (Azure Container Apps).

---

## Container Topology

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              {Project} DEPLOYMENT                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                          LOAD BALANCER / INGRESS                        │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                          │
│      ┌───────────────────────────────┼───────────────────────────────┐         │
│      │                               │                               │         │
│      ▼                               ▼                               ▼         │
│  ┌─────────┐                    ┌─────────┐                    ┌─────────┐     │
│  │   API   │                    │   API   │                    │   API   │     │
│  │ (main)  │                    │ (main)  │                    │ (main)  │     │
│  │  :8000  │                    │  :8000  │                    │  :8000  │     │
│  └────┬────┘                    └────┬────┘                    └────┬────┘     │
│       │                              │                              │          │
│       └──────────────────────────────┼──────────────────────────────┘          │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                          BACKGROUND SERVICES                              │ │
│  │                                                                           │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │   Ingestion  │  │    Graph     │  │    Index     │  │   Curation   │ │ │
│  │  │   Worker     │  │  Projection  │  │  Projection  │  │   Processor  │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                          DATA STORES                                      │ │
│  │                                                                           │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │  PostgreSQL  │  │    Neo4j     │  │    Redis     │  │   SpiceDB    │ │ │
│  │  │  (Events +   │  │   (Graph)    │  │   (Cache)    │  │   (AuthZ)    │ │ │
│  │  │   pgvector)  │  │              │  │              │  │              │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                          EXTERNAL SERVICES                                │ │
│  │                                                                           │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │  Voyage AI   │  │   Cohere     │  │   OpenAI     │               │ │
│  │  │ (Embeddings) │  │ (Reranking)  │  │  (Extract)   │               │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Services

### Application Services

| Service | Image | Replicas | Purpose |
|---------|-------|----------|---------|
| `api` | `{Project}:latest` | 3+ | FastAPI main application |
| `ingestion-worker` | `{Project}:latest` | 1-3 | Document processing |
| `graph-projection` | `{Project}:latest` | 1 | Neo4j projection runner |
| `index-projection` | `{Project}:latest` | 1 | Vector/BM25 projection |
| `curation-processor` | `{Project}:latest` | 1 | Curation rule processor |

### API Service

```yaml
# Main application
service: api
command: uvicorn {project}.main:app --host 0.0.0.0 --port 8000
resources:
  cpu: 1.0
  memory: 2Gi
scaling:
  min: 3
  max: 10
  target_cpu: 70%
health_check:
  path: /health
  interval: 30s
```

### Background Workers

```yaml
# Ingestion worker
service: ingestion-worker
command: python -m {Project}.ingestion.worker
resources:
  cpu: 2.0
  memory: 4Gi
scaling:
  min: 1
  max: 5
  target_queue_length: 100

# Graph projection (single instance for ordering)
service: graph-projection
command: python -m {Project}.graph.projection_runner
resources:
  cpu: 0.5
  memory: 1Gi
replicas: 1  # Must be single instance
```

---

## Data Stores

### PostgreSQL (Event Store + pgvector + ParadeDB)

| Aspect | Configuration |
|--------|---------------|
| **Version** | PostgreSQL 15+ |
| **Extensions** | pgvector, pg_search (ParadeDB) |
| **Purpose** | Event store, vector index, BM25 index, tracking |
| **Scaling** | Vertical (single primary) |

```yaml
# Docker Compose
postgres:
  image: paradedb/paradedb:latest  # Includes pgvector + pg_search
  environment:
    POSTGRES_DB: {Project}
    POSTGRES_USER: {Project}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
```

### Neo4j (Knowledge Graph)

| Aspect | Configuration |
|--------|---------------|
| **Version** | Neo4j 5.x |
| **Edition** | Community (dev) / Enterprise (prod) |
| **Purpose** | Knowledge graph, entity resolution, traversal |
| **Scaling** | Vertical or cluster (Enterprise) |

```yaml
neo4j:
  image: neo4j:5-community
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    NEO4J_PLUGINS: '["apoc"]'
  volumes:
    - neo4j_data:/data
  ports:
    - "7474:7474"  # Browser
    - "7687:7687"  # Bolt
```

### Redis (Cache)

| Aspect | Configuration |
|--------|---------------|
| **Version** | Redis 7.x |
| **Purpose** | Session cache, rate limiting, task queue |
| **Scaling** | Cluster mode (production) |

```yaml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
  ports:
    - "6379:6379"
```

### SpiceDB (Authorization)

| Aspect | Configuration |
|--------|---------------|
| **Version** | SpiceDB latest |
| **Purpose** | ReBAC permission checks |
| **Storage** | PostgreSQL |

```yaml
spicedb:
  image: authzed/spicedb
  command: serve
  environment:
    SPICEDB_GRPC_PRESHARED_KEY: ${SPICEDB_KEY}
    SPICEDB_DATASTORE_ENGINE: postgres
    SPICEDB_DATASTORE_CONN_URI: postgres://spicedb:${SPICEDB_DB_PASSWORD}@postgres:5432/spicedb
  ports:
    - "50051:50051"  # gRPC
```

---

## External Services

### Authentication

Authentication is handled by an external OIDC provider (e.g., Auth0, Okta, Keycloak). The provider issues JWTs validated by the application's auth middleware. See [PADR-116](../../../decisions/patterns/PADR-116-jwt-auth-jwks.md) for JWT validation patterns.

### AI Services

| Service | API | Purpose |
|---------|-----|---------|
| **Voyage AI** | voyage.ai | Query/document embeddings |
| **Cohere** | cohere.com | Cross-encoder reranking |
| **OpenAI** | openai.com | Entity extraction, contextual headers |

```yaml
# Environment configuration
environment:
  VOYAGE_API_KEY: ${VOYAGE_API_KEY}
  COHERE_API_KEY: ${COHERE_API_KEY}
  OPENAI_API_KEY: ${OPENAI_API_KEY}
```

---

## Environment Configurations

### Development (Docker Compose)

```
┌──────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  All services run locally via Docker Compose                 │
│                                                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   API   │  │Postgres │  │  Neo4j  │  │  Redis  │        │
│  │  :8000  │  │  :5432  │  │  :7687  │  │  :6379  │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│                                                               │
│  ┌─────────┐  ┌─────────┐                                   │
│  │SpiceDB  │  │ Workers │                                   │
│  │  :50051 │  │ (1 each)│                                   │
│  └─────────┘  └─────────┘                                   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Production (Azure)

| Component | Azure Service | Configuration |
|-----------|---------------|---------------|
| API | Container Apps | Auto-scaling, 3-10 replicas |
| Workers | Container Apps | Job-based, auto-scaling |
| PostgreSQL | Azure Database for PostgreSQL | Flexible Server, pgvector |
| Neo4j | Neo4j AuraDB | Managed cloud |
| Redis | Azure Cache for Redis | Premium tier |
| SpiceDB | Container Apps | Dedicated container |

```
┌──────────────────────────────────────────────────────────────┐
│                    AZURE PRODUCTION                           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Azure Container Apps Environment          │  │
│  │                                                        │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │  │
│  │  │   API   │  │   API   │  │   API   │  (3-10)     │  │
│  │  └─────────┘  └─────────┘  └─────────┘              │  │
│  │                                                        │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │  │
│  │  │Ingestion│  │  Graph  │  │  Index  │  Workers     │  │
│  │  │ Worker  │  │Projection│ │Projection│              │  │
│  │  └─────────┘  └─────────┘  └─────────┘              │  │
│  │                                                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┼────────────────────────────────┐ │
│  │                       │  Azure Managed Services        │ │
│  │                       │                                │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ Azure DB for PostgreSQL (pgvector + ParadeDB)   │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │ Neo4j AuraDB│  │Azure Redis  │                      │ │
│  │  │   Cloud     │  │   Premium   │                      │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Resource Requirements

### Development

| Service | CPU | Memory | Storage |
|---------|-----|--------|---------|
| API | 0.5 | 1Gi | - |
| PostgreSQL | 1.0 | 2Gi | 10Gi |
| Neo4j | 1.0 | 2Gi | 5Gi |
| Redis | 0.25 | 512Mi | 1Gi |
| SpiceDB | 0.25 | 512Mi | - |

### Production (per replica)

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| API | 1.0 | 2Gi | Auto-scales 3-10 |
| Ingestion Worker | 2.0 | 4Gi | Memory for embeddings |
| Graph Projection | 0.5 | 1Gi | Single replica |
| Index Projection | 0.5 | 1Gi | Single replica |

---

## Network Configuration

### Ports

| Service | Port | Protocol | Access |
|---------|------|----------|--------|
| API | 8000 | HTTP | External (via LB) |
| PostgreSQL | 5432 | TCP | Internal only |
| Neo4j Bolt | 7687 | TCP | Internal only |
| Redis | 6379 | TCP | Internal only |
| SpiceDB | 50051 | gRPC | Internal only |

### Security Groups

```
┌─────────────────────────────────────────────────────────────────┐
│                      NETWORK SECURITY                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PUBLIC SUBNET                                                  │
│  └── Load Balancer (443, 80 → 8000)                            │
│                                                                  │
│  PRIVATE SUBNET                                                 │
│  ├── API containers                                             │
│  ├── Worker containers                                          │
│  └── All data stores (no public access)                        │
│                                                                  │
│  EGRESS                                                         │
│  ├── Voyage AI API (HTTPS)                                     │
│  ├── Cohere API (HTTPS)                                        │
│  ├── OpenAI API (HTTPS)                                        │
│  └── Source system connectors (varies)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## See Also

- [Deployment Configs](ref-deployment-configs.md) - Docker/K8s configurations
- [Deployment Procedure](proc-deployment-procedure.md) - Step-by-step guide
- [Observability](../../observability/references/con-observability.md) - Monitoring setup
