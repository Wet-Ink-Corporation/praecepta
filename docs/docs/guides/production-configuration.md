# Production Configuration

This guide covers environment variables, database configuration, and deployment patterns for running praecepta in production.

## Event Store Environment Variables

The event store is configured via environment variables. The `event_store_lifespan` hook (priority 100) bridges settings into `os.environ` at startup so that all `Application[UUID]` subclasses receive the correct configuration.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_DBNAME` | PostgreSQL database name | `myapp` |
| `POSTGRES_HOST` | Database hostname | `db.example.com` |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_USER` | Database user | `app_user` |
| `POSTGRES_PASSWORD` | Database password | `secret` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PERSISTENCE_MODULE` | `eventsourcing.postgres` | Event sourcing persistence backend |
| `CREATE_TABLE` | `true` | Auto-create event store tables on startup |
| `POSTGRES_SCHEMA` | *(none)* | PostgreSQL schema for event store tables |
| `DATABASE_URL` | *(none)* | Connection string (alternative to individual `POSTGRES_*` vars) |

### `PERSISTENCE_MODULE` — Critical Setting

The underlying `eventsourcing` library defaults `PERSISTENCE_MODULE` to `eventsourcing.popo` (plain-old Python objects — in-memory storage). Praecepta's `EventSourcingSettings` defaults to `eventsourcing.postgres`, and the environment bridging ensures this value reaches `Application` subclasses.

However, you should **always set `PERSISTENCE_MODULE` explicitly** in production:

```bash
PERSISTENCE_MODULE=eventsourcing.postgres
```

If `PERSISTENCE_MODULE` is not set, the framework logs a warning during startup and bridges the default from settings. Relying on implicit bridging works, but an explicit setting makes the configuration auditable and removes any ambiguity.

### Using `DATABASE_URL`

If your deployment platform provides a `DATABASE_URL` connection string (common with Heroku, Railway, Render, etc.), the framework parses it automatically:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

Individual `POSTGRES_*` variables take precedence over parsed `DATABASE_URL` values, so you can use `DATABASE_URL` as a base and override specific fields:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
POSTGRES_SCHEMA=myapp   # Override just the schema
```

## Projection Polling Configuration

Projections run via a background polling thread that reads events from the shared PostgreSQL notification log. Configuration is via `PROJECTION_*` environment variables:

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `PROJECTION_POLL_INTERVAL` | `1.0` | 0.1–60.0 | Seconds between poll cycles |
| `PROJECTION_POLL_TIMEOUT` | `10.0` | 1.0–120.0 | Max seconds for graceful shutdown |
| `PROJECTION_POLL_ENABLED` | `true` | — | Set to `false` to disable projection processing |

### Tuning the Poll Interval

- **Lower values** (e.g. `0.5`) reduce the delay between an event being written and the projection being updated, at the cost of more frequent database queries.
- **Higher values** (e.g. `5.0`) reduce database polling overhead, suitable for systems where near-real-time read model updates are not required.
- For most deployments, the default of `1.0` second provides a good balance.

### Disabling Projections

Set `PROJECTION_POLL_ENABLED=false` to start the application without running projections. This is useful for:

- **API-only deployments** where projections run in a separate process
- **Migration or maintenance windows** where projection processing should be paused
- **Development** when you only need the write side

## Lifespan Hook Ordering

The eventsourcing package registers two lifespan hooks with specific priorities:

| Hook | Priority | Purpose |
|------|----------|---------|
| `event_store_lifespan` | 100 | Bridges `EventSourcingSettings` to `os.environ`, initialises `EventStoreFactory` singleton |
| `projection_runner_lifespan` | 200 | Discovers projections and applications, starts `ProjectionPoller` instances |

Priority 100 runs before 200, which is required because `Application` subclasses (used inside the poller) read their configuration from `os.environ` — the bridge must run first.

## Deployment Patterns

### Single-Process (Simple)

Both the API and projections run in the same process. This is the default when you use `create_app()`:

```bash
PERSISTENCE_MODULE=eventsourcing.postgres
POSTGRES_DBNAME=myapp
POSTGRES_HOST=localhost
POSTGRES_USER=app
POSTGRES_PASSWORD=secret
PROJECTION_POLL_ENABLED=true
```

The API handles HTTP requests while projections poll in a background thread.

### Separate Projection Worker

For larger deployments, run projections in a dedicated process:

**API process:**
```bash
PROJECTION_POLL_ENABLED=false
# ... other POSTGRES_* vars
```

**Projection worker process:**
```bash
PROJECTION_POLL_ENABLED=true
PROJECTION_POLL_INTERVAL=0.5   # Lower for faster updates
# ... same POSTGRES_* vars (shared database)
```

Both processes connect to the same PostgreSQL database. The API writes events, and the projection worker reads them from the shared notification log.

### Dockerfile Layer Separation

When using entry-point auto-discovery, changing a package's `pyproject.toml` entry points invalidates the Docker layer that installs dependencies. Structure your Dockerfile to separate dependency installation from code:

```dockerfile
# Layer 1: Dependencies (cached unless pyproject.toml changes)
COPY pyproject.toml uv.lock ./
COPY packages/*/pyproject.toml packages/*/
RUN uv sync --no-dev --frozen

# Layer 2: Application code (changes frequently)
COPY packages/ packages/
COPY src/ src/
```

This way, adding a new projection handler (code change) does not invalidate the dependency layer. Only changes to entry point declarations in `pyproject.toml` trigger a full dependency reinstall.
