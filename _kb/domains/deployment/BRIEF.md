# Deployment Domain

Docker Compose, database migrations, CI/CD, and operational procedures.

## Mental Model

Development via Docker Compose (PostgreSQL, Neo4j, Redis). Database migrations via Alembic. Pre-commit hooks enforce code quality. Conventional commits with Commitizen.

## Key Patterns

- **Docker Compose:** `docker compose up -d` starts all services
- **Migrations:** `uv run alembic upgrade head` / `revision --autogenerate`
- **Pre-commit:** ruff, mypy, commitizen validation
- **Git workflow:** Feature branches, conventional commits, PR review

## Commands

```bash
docker compose up -d              # Start services
uv run alembic upgrade head       # Run migrations
uv run uvicorn {project}.main:app --reload  # Start API
```

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `references/con-infrastructure.md` | Container specs |
| `references/proc-deployment-procedure.md` | Deployment steps |
| `references/ref-deployment-configs.md` | Environment configs |
| `references/ref-deployment.md` | Production deployment |
