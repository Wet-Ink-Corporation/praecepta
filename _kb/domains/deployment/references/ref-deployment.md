# Deployment Reference

## Overview

Docker Compose configuration for development and production deployment patterns.

## Docker Compose (Development)

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      - PERSISTENCE_MODULE=eventsourcing.postgres
      - POSTGRES_HOST=postgres
    depends_on:
      - postgres
      - neo4j

  graph-projection:
    build: .
    command: python -m dog_school.infrastructure.run_graph_projection
    environment:
      - PERSISTENCE_MODULE=eventsourcing.postgres
      - POSTGRES_HOST=postgres
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      - postgres
      - neo4j

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: events
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - neo4j_data:/data

volumes:
  postgres_data:
  neo4j_data:
```

## Service Architecture

| Service | Purpose | Scaling |
|---------|---------|---------|
| `app` | FastAPI main application | Horizontal (stateless) |
| `graph-projection` | Neo4j materialised view | Single instance (ordered processing) |
| `postgres` | Event store + notification log | Vertical (single primary) |
| `neo4j` | Graph queries | Vertical or cluster |

## Production (Azure Container Apps)

| Component | Azure Service |
|-----------|---------------|
| Main app | Container App with auto-scaling |
| Graph projection | Separate Container App |
| Event store | Azure Database for PostgreSQL (Flexible Server) |
| Graph store | Neo4j AuraDB |
| Auth | External OIDC provider |

## Running Projections

The graph projection runs as a separate process:

```python
# src/dog_school/infrastructure/run_graph_projection.py
def main():
    with ProjectionRunner(
        application_class=DogSchoolApplication,
        projection_class=DogGraphProjection,
        view_class=DogGraphView,
        env={
            "PERSISTENCE_MODULE": "eventsourcing.postgres",
            "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", "password"),
        },
    ) as runner:
        signal.signal(signal.SIGINT, lambda *_: runner.stop())
        signal.signal(signal.SIGTERM, lambda *_: runner.stop())
        runner.run_forever()
```

## Startup Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f app
docker compose logs -f graph-projection

# Stop
docker compose down
```

## Key Points

- Main app and projections run as separate containers
- PostgreSQL stores events; Neo4j stores graph projections
- Projections run as single instances for ordered processing
- Main app scales horizontally (stateless)

## See Also

- [Technology Stack](ref-tech-stack.md) - Technology choices
- [Neo4j Projections](con-neo4j-projection.md) - Graph projection details
