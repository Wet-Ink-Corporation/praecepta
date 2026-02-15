# Technology Stack Reference

## Overview

Complete technology stack for the Python event-sourced modular monolith architecture.

**Version:** 2.0 | **Date:** January 2026

## Core Runtime

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| Language | Python | 3.12+ | Pattern matching, error messages, performance |
| Web Framework | FastAPI | 0.110+ | Async-first, OpenAPI, Pydantic integration |
| Event Sourcing | eventsourcing | 9.5+ | Native Python, PostgreSQL support, built-in projections |
| Validation | Pydantic | 2.x | Type-safe DTOs, settings, serialization |
| ORM | SQLAlchemy | 2.0+ | Async support, mature ecosystem |
| Async Runtime | AnyIO | 4.x | Structured concurrency, cancellation, task groups |

## Data Stores

| Store | Technology | Purpose |
|-------|------------|---------|
| Event Store | PostgreSQL | Aggregate events, notification log, tracking records |
| Graph Projections | Neo4j | Relationship queries, hybrid RAG |
| Cache | Redis | Session cache, rate limiting, ephemeral state |

## Infrastructure

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Package Manager | uv | 10-50x faster than Poetry, native workspaces |
| Task Queue | TaskIQ | Async-native, Redis Stream broker, FastAPI DI integration |
| Auth | External OIDC Provider | OIDC-compliant, pluggable identity provider |
| Observability | OpenTelemetry | Vendor-neutral traces, metrics, logs |
| AI/Agents | Pydantic-AI | Type-safe agent framework, Pydantic integration |

## Development Tools

| Tool | Purpose |
|------|---------|
| Ruff | Linting + formatting |
| mypy | Static type checking |
| pytest | Testing with pytest-asyncio |
| import-linter | Architecture boundary enforcement |

## Environment Variables

```bash
# Event Store
PERSISTENCE_MODULE=eventsourcing.postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=app
POSTGRES_PASSWORD=secret
POSTGRES_DBNAME=events

# Graph Store
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## Key Imports

```python
from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event, DomainEvent
from eventsourcing.projection import Projection, ProjectionRunner
from eventsourcing.system import System, ProcessApplication, SingleThreadedRunner
from eventsourcing.persistence import Tracking, TrackingRecorder
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.utils import get_topic
```

## Quick Commands

```bash
docker compose up -d              # Start environment
uv run pytest --cov=src           # Run tests
uv run mypy src/                  # Type check
uv run ruff check src/ --fix      # Lint
uv run lint-imports               # Validate architecture
```

## See Also

- [Philosophy](con-philosophy.md) - Why these technologies
- [Deployment](ref-deployment.md) - Production configuration
