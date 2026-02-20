# Praecepta Framework Issues — 2026-02-18

Raised from integration experience in `redkiln`. These are gaps where the framework
promises "batteries included" but leaves consumers to work around fundamental
infrastructure problems.

---

## Issue 1: `projection_runner_lifespan` uses `SingleThreadedRunner` — broken for any real deployment

**Severity:** Critical  
**Component:** `praecepta-infra-eventsourcing` → `projection_lifespan.py`

### Problem

`projection_runner_lifespan` creates a `ProjectionRunner` with the default
`SingleThreadedRunner`. The eventsourcing library's `SingleThreadedRunner` (and
`MultiThreadedRunner`) are **in-process only** — the leader application directly
prompts the follower thread when it writes events. This works in tests where the
same runner instance owns both the upstream app and the projection.

In a real FastAPI deployment:

- The API's `CoreApplication` instance writes events (one connection pool)
- The runner's internal `CoreApplication` instance is a *separate object* (different connection pool)
- No in-process prompt ever fires between them
- Result: projections never process any events written by the API

This is not a configuration problem — it is a fundamental architectural mismatch.
The eventsourcing library's own documentation recommends gRPC or manual
`pull_and_process` polling for cross-process consumption.

### Evidence

```python
# projection_runner_lifespan creates:
runner = ProjectionRunner(projections=..., upstream_application=CoreApplication)
# → SingleThreadedRunner(System([[CoreApplication, ProjectionA], ...]))
# → runner.get(CoreApplication) is a DIFFERENT instance than app.state.core_app
# → events written via app.state.core_app never prompt the runner's follower threads
```

### Fix

Replace `SingleThreadedRunner` with a **polling loop** that calls
`pull_and_process("CoreApplication")` on a background thread, reading from the
shared PostgreSQL notification log. This is the correct cross-process pattern.

```python
# Correct pattern for cross-process projection consumption:
def _run_poll_loop(projections, stop_flag):
    pipes = [[CoreApplication, proj_cls] for proj_cls in projections]
    runner = SingleThreadedRunner(System(pipes=pipes))
    runner.start()
    while not stop_flag.is_set():
        for proj_cls in projections:
            runner.get(proj_cls).pull_and_process("CoreApplication")
        stop_flag.wait(timeout=1.0)
    runner.stop()

thread = threading.Thread(target=_run_poll_loop, daemon=True)
thread.start()
```

The `projection_runner_lifespan` contribution should use this pattern (or
`MultiThreadedRunner` with a DB-polling adapter) rather than the in-process runner.

---

## Issue 2: `event_store` lifespan contribution is registered but unused by `CoreApplication`

**Severity:** High  
**Component:** `praecepta-infra-eventsourcing` → `lifespan.py`

### Problem

The `event_store` lifespan (priority 100) calls `get_event_store()` which
initialises a `PostgresInfrastructureFactory` singleton. However, `CoreApplication`
(the eventsourcing `Application` subclass) does **not** use this factory — it
constructs its own infrastructure directly from environment variables via the
eventsourcing library's `InfrastructureFactory`.

The result: two separate connection pools exist at runtime (one from `get_event_store()`,
one from `CoreApplication`), and the `event_store` lifespan's `close()` call on
shutdown does not close `CoreApplication`'s pool.

### Fix

Either:
- `CoreApplication` should be constructed using the `EventStoreFactory` from
  `get_event_store()`, sharing one pool; or
- The `event_store` lifespan should be removed/documented as only relevant for
  direct `get_event_store()` usage (not for `Application` subclasses); or
- Document clearly which pattern consumers should use and ensure they don't conflict.

---

## Issue 3: No `PERSISTENCE_MODULE` default in compose/deployment guidance

**Severity:** High  
**Component:** `praecepta-infra-eventsourcing` docs / deployment guidance

### Problem

`CoreApplication` uses in-memory storage by default (eventsourcing library default).
Without `PERSISTENCE_MODULE=eventsourcing.postgres` in the environment, all events
are lost on restart and projections have nothing to consume. This is a silent failure
— the API appears to work, events are "saved", but nothing persists.

The framework provides `EventSourcingSettings` which defaults
`persistence_module = "eventsourcing.postgres"`, but `CoreApplication` doesn't use
`EventSourcingSettings` — it reads `PERSISTENCE_MODULE` directly from the process
environment via the eventsourcing library.

### Fix

- Document the required environment variables prominently in the framework README
- Consider making `CoreApplication` (or a base class) read from `EventSourcingSettings`
  so the default is postgres, not in-memory
- Add a startup warning log if `PERSISTENCE_MODULE` is not set

---

## Issue 4: `pyproject.toml` entry point changes require image rebuild (no hot-reload path)

**Severity:** Medium  
**Component:** Dockerfile pattern / developer experience

### Problem

Entry points are baked into the installed package's `.dist-info/entry_points.txt`.
In the Docker dev setup, `./src` is volume-mounted for hot-reload, but
`pyproject.toml` is not — it's `COPY`'d at build time. Adding a new
`praecepta.lifespan` entry point requires:

1. Edit `pyproject.toml`
2. Full image rebuild (~15 min due to large deps: torch, CUDA, etc.)
3. Container restart

The workaround (`docker compose exec api uv pip install --no-deps -e .`) works but
is not documented and is fragile (lost on container restart).

### Fix

- The Dockerfile should separate the `uv sync` (deps) layer from the
  `uv pip install -e .` (project metadata) layer — `pyproject.toml` changes should
  only invalidate the cheap final layer, not the multi-GB deps layer
- The `python-deps` stage currently `COPY`s `pyproject.toml` before `uv sync`,
  which means any entry point addition busts the entire dep cache

Recommended Dockerfile structure:
```dockerfile
# python-deps stage: only uv.lock drives this layer
COPY uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

# runtime stage: pyproject.toml only needed for final install
COPY pyproject.toml README.md ./
RUN uv pip install --no-deps -e .
```

---

## Issue 5: `ProjectionRunner` does not expose `runner_class` override via `projection_runner_lifespan`

**Severity:** Medium  
**Component:** `praecepta-infra-eventsourcing` → `projection_lifespan.py`

### Problem

`ProjectionRunner.__init__` accepts a `runner_class` parameter, but
`projection_runner_lifespan` hardcodes `ProjectionRunner(projections=..., upstream_application=...)`
with no way for consumers to override the runner class via configuration or entry
points. Even if a consumer wanted to use `MultiThreadedRunner`, they'd have to
replace the entire lifespan contribution.

### Fix

Support configuration via environment variable or settings:

```python
# e.g. PROJECTION_RUNNER_CLASS=MultiThreadedRunner
runner_class = _resolve_runner_class_from_env()
runner = ProjectionRunner(..., runner_class=runner_class)
```

Or expose a hook/override mechanism so consumers can configure the runner without
replacing the entire lifespan.

---

## Summary

| # | Issue | Severity | Affects |
|---|-------|----------|---------|
| 1 | `projection_runner_lifespan` uses in-process runner — broken cross-process | **Critical** | All deployments |
| 2 | `event_store` lifespan creates unused connection pool | High | All deployments |
| 3 | No postgres persistence default / silent in-memory fallback | High | All deployments |
| 4 | Entry point changes require full image rebuild | Medium | Developer experience |
| 5 | `runner_class` not configurable via `projection_runner_lifespan` | Medium | Advanced consumers |

Issues 1 and 3 are the ones that caused the most pain in this integration — the
framework appeared to work (no errors, projections "started") but silently did
nothing. A batteries-included framework should either work correctly out of the box
or fail loudly with a clear error message.
