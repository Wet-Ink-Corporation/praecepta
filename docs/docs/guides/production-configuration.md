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

## Projection Configuration

Projections use PostgreSQL LISTEN/NOTIFY for push-based event delivery via `SubscriptionProjectionRunner`. This replaces the previous polling-based `ProjectionPoller` (removed in v2.0.0).

### Connection Pool Settings

Each projection creates two small connection pools: one for the upstream application (reading events) and one for the tracking recorder (writing position). These use separate, smaller pool sizes to minimize connection usage:

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `POSTGRES_PROJECTION_POOL_SIZE` | `2` | 1–20 | Base pool size for projection contexts |
| `POSTGRES_PROJECTION_MAX_OVERFLOW` | `3` | 0–20 | Max overflow for projection pools |
| `MAX_PROJECTION_RUNNERS` | `8` | 1–32 | Cap on total projection runners |
| `POSTGRES_MAX_CONNECTIONS` | `100` | — | Used for budget warning (not enforced) |

### Connection Budget

At startup, the framework logs an estimated connection budget:

```text
Connection pool budget: 3 API app(s) (24 max conn) + 4 projection(s) x 2 pools (40 max conn) = 64 estimated total
```

If the estimate exceeds `POSTGRES_MAX_CONNECTIONS`, a warning is logged suggesting you reduce projection pool sizes or increase the PostgreSQL connection limit.

**Typical budget for 3 API apps + 4 projections:**

| Component                      | Pools | Max per pool | Total    |
| ------------------------------ | ----- | ------------ | -------- |
| API Applications               | 3     | 5 + 10 = 15  | 45       |
| Projection upstream apps       | 4     | 2 + 3 = 5    | 20       |
| Projection tracking recorders  | 4     | 2 + 3 = 5    | 20       |
| SQLAlchemy (read models)       | 1     | ~20          | 20       |
| **Total**                      |       |              | **~105** |

To reduce this, lower `POSTGRES_PROJECTION_POOL_SIZE` to `1` and `POSTGRES_PROJECTION_MAX_OVERFLOW` to `1`:

```bash
POSTGRES_PROJECTION_POOL_SIZE=1
POSTGRES_PROJECTION_MAX_OVERFLOW=1
```

This brings projection connection usage from 40 to 16, yielding ~81 total.

## Lifespan Hook Ordering

The eventsourcing package registers two lifespan hooks with specific priorities:

| Hook                         | Priority | Purpose                                             |
| ---------------------------- | -------- | --------------------------------------------------- |
| `event_store_lifespan`       | 100      | Bridges settings to `os.environ`, inits event store |
| `projection_runner_lifespan` | 200      | Discovers projections, starts subscription runners  |

Priority 100 runs before 200, which is required because `Application` subclasses (used inside the projection runners) read their configuration from `os.environ` — the bridge must run first.

## Deployment Patterns

### Single-Process (Simple)

Both the API and projections run in the same process. This is the default when you use `create_app()`:

```bash
PERSISTENCE_MODULE=eventsourcing.postgres
POSTGRES_DBNAME=myapp
POSTGRES_HOST=localhost
POSTGRES_USER=app
POSTGRES_PASSWORD=secret
```

The API handles HTTP requests while projection runners process events via LISTEN/NOTIFY in background threads.

### Separate Projection Worker

For larger deployments, run projections in a dedicated process. Use `MAX_PROJECTION_RUNNERS=0` or avoid registering projection entry points in the API process:

**API process:**
```bash
MAX_PROJECTION_RUNNERS=0
# ... other POSTGRES_* vars
```

**Projection worker process:**
```bash
POSTGRES_PROJECTION_POOL_SIZE=2
POSTGRES_PROJECTION_MAX_OVERFLOW=3
# ... same POSTGRES_* vars (shared database)
```

Both processes connect to the same PostgreSQL database. The API writes events, and the projection worker receives them via LISTEN/NOTIFY.

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
