# infra-taskiq -- Library Usage Audit

**Upstream Library:** TaskIQ >=0.11, taskiq-redis >=1.2
**RAG Status:** AMBER
**Checklist:** 4/11 passed

## Findings

| ID | Severity | Checklist | Description | File:Line | Recommendation |
|----|----------|-----------|-------------|-----------|----------------|
| F-01 | LOW | TQ-1 PASS | Broker correctly uses `RedisStreamBroker` (stream-based, not the deprecated `ListQueueBroker`). | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:67` | None |
| F-02 | LOW | TQ-2 PASS | Result backend sets `result_ex_time=3600` (1-hour TTL), preventing indefinite accumulation. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:63` | None |
| F-03 | LOW | TQ-3 PASS | TaskIQ defaults to JSON serialization; no pickle override is configured. Secure by default. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:67` | None |
| F-04 | LOW | TQ-4 PASS | Scheduler uses `TaskiqScheduler` with `LabelScheduleSource` and `ListRedisScheduleSource` -- TaskIQ's built-in mechanisms. No custom cron. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:75-81` | None |
| F-05 | HIGH | TQ-5 FAIL | No worker startup/shutdown hooks are registered. The broker has `startup()` and `shutdown()` coroutines that must be called, but no hook wiring exists. The package does not integrate with TaskIQ's `@broker.on_event(TaskiqEvents.WORKER_STARTUP)` or equivalent. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py` (absent) | Add `@broker.on_event` handlers or integrate via a `LifespanContribution` that calls `broker.startup()` / `broker.shutdown()`. |
| F-06 | HIGH | TQ-6 FAIL | Configuration uses bare `os.getenv("REDIS_URL", ...)` instead of a `pydantic_settings.BaseSettings` subclass with `env_prefix`. Every other infra package (`infra-persistence`, `infra-auth`, `infra-observability`, `infra-fastapi`, `infra-eventsourcing`) uses the `BaseSettings` pattern. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:48-57` | Create a `TaskIQSettings(BaseSettings)` class with fields for `redis_url`, `result_ttl`, etc., using `SettingsConfigDict(env_prefix="TASKIQ_")`. Add `pydantic-settings` to `pyproject.toml` dependencies. |
| F-07 | CRITICAL | TQ-7 FAIL | No `LifespanContribution` is registered for broker lifecycle management. The `pyproject.toml` has no `[project.entry-points."praecepta.lifespan"]` section. Compare with `infra-eventsourcing` and `infra-observability` which both provide lifespan contributions. Without this, the broker is never properly started or shut down by the application. | `packages/infra-taskiq/pyproject.toml` (absent) | Create a lifespan hook that calls `broker.startup()` on app start and `broker.shutdown()` on app teardown. Register it as `[project.entry-points."praecepta.lifespan"] taskiq = "praecepta.infra.taskiq:lifespan_contribution"`. |
| F-08 | MEDIUM | TQ-8 FAIL | Broker, result_backend, and scheduler are module-level singletons instantiated at import time (`broker.py:61-81`). This means importing the module triggers Redis URL resolution and object construction immediately, which can fail if the environment is not yet configured. Other packages use factory functions or lazy initialization. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:61-81` | Convert to a factory function (e.g., `create_broker()`) or use lazy initialization via `functools.lru_cache`. The `__init__.py` re-exports should reference factories, not pre-built instances. |
| F-09 | MEDIUM | TQ-9 FAIL | No error handling patterns exist in the package. No custom exception types, no retry configuration, no dead-letter queue setup. Other infra packages define domain-specific exceptions and register error handlers via entry points. | `packages/infra-taskiq/src/praecepta/infra/taskiq/` (absent) | At minimum, add retry middleware configuration (`taskiq.middlewares.retry.RetryMiddleware`). Consider defining `TaskIQError` exception hierarchy and a contribution to `praecepta.error_handlers`. |
| F-10 | MEDIUM | TQ-10 FAIL | The task queue reads `REDIS_URL` from the same environment variable used by `infra-persistence`'s `RedisSettings` and `redis_client.py`. Both default to `redis://localhost:6379/0`. There is no separation or explicit documentation of sharing. Under load, task queue traffic and persistence traffic compete on the same Redis connection/database. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:57` vs `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:78` | Use a dedicated env var (e.g., `TASKIQ_REDIS_URL`) with the `TaskIQSettings` class, defaulting to `REDIS_URL` as fallback. Document the resource separation strategy. |
| F-11 | CRITICAL | TQ-11 FAIL | Broker `shutdown()` is never called during application exit. There is no lifespan hook, no atexit handler, and no `__del__` method. This can lead to unacknowledged messages in Redis Streams and leaked connections. | `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py` (absent) | This is directly addressed by implementing F-07 (LifespanContribution). The shutdown path of the lifespan hook must call `await broker.shutdown()`. |

## Narrative

The `infra-taskiq` package makes correct choices at the library API level: it uses `RedisStreamBroker` for reliable delivery with acknowledgements (TQ-1), configures result TTL to prevent unbounded accumulation (TQ-2), relies on JSON serialization by default (TQ-3), and uses TaskIQ's built-in scheduling infrastructure (TQ-4). These four items pass cleanly.

However, the package has significant **convention and lifecycle gaps** that place it well behind the maturity of sibling infra packages:

**Most critical** is the complete absence of lifecycle management (TQ-7, TQ-11). The broker is instantiated at module import time but never has `startup()` or `shutdown()` called on it. In a FastAPI application using `create_app()`, other packages like `infra-eventsourcing` and `infra-observability` register `LifespanContribution` hooks that are automatically discovered and executed. The taskiq package has no such registration, meaning:
- Redis Stream consumer groups are never initialized
- Connections are never cleanly closed on shutdown
- Unacknowledged messages may be lost

**Configuration** (TQ-6) uses raw `os.getenv()` instead of the `pydantic_settings.BaseSettings` pattern used consistently across all other infra packages. This breaks the established configuration contract and prevents type-safe validation, `.env` file support, and prefixed environment variables.

**Resource separation** (TQ-10) is ambiguous -- both taskiq and persistence read `REDIS_URL` with identical defaults, meaning they silently share the same Redis database. This is the same class of "convention gap" anti-pattern identified in the projection remediation audit.

**Module-level instantiation** (TQ-8) means the broker is constructed as a side effect of `import praecepta.infra.taskiq`, which can cause import-time failures and makes testing harder (the test file has to use `patch.dict` for every test).

The package appears to be in early scaffold state and needs a second pass to bring it in line with the patterns established by other infrastructure packages. The two CRITICAL findings (F-07 and F-11) should be addressed first, as they represent potential data loss in production (unacknowledged Redis Stream messages).
