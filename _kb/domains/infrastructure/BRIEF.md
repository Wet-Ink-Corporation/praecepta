# Infrastructure Domain

PostgreSQL, Redis, Neo4j, Docker, and configuration management.

## Mental Model

Three datastores: PostgreSQL (event store + projections), Neo4j (graph database), Redis (task queue + cache). All managed via Docker Compose for development. Configuration via environment variables with type-safe Pydantic Settings (PPADR-106).

## Key Patterns

- **PostgreSQL:** Event store tables, projection tables, RLS policies
- **Redis:** TaskIQ background tasks, session cache
- **Neo4j:** Graph projections, Cypher queries
- **Config:** `pydantic-settings` with `.env` files (PADR-106)
- **Migrations:** Alembic for schema evolution

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/patterns/PADR-106-configuration.md` | Config patterns |
| `_kb/decisions/strategic/PADR-005-task-queue.md` | Redis/TaskIQ rationale |
| `references/con-infrastructure.md` | Infrastructure setup |
| `references/ref-tech-stack.md` | Technology inventory |
| `references/ref-settings-pattern.md` | BaseSettings convention across packages |
