# Workspace & PEP 420 Namespace Package Conventions

## Overview

Praecepta is a uv workspaces monorepo with 11 packages under a single `praecepta.*` namespace. All packages use **PEP 420 implicit namespace packages** so that multiple packages can contribute modules under the same `praecepta` top-level namespace without conflicting `__init__.py` files.

---

## PEP 420 Implicit Namespace Packages

Intermediate directories in the namespace hierarchy must **not** contain `__init__.py` files. Python's import system treats directories without `__init__.py` as namespace packages, allowing multiple physical directories (one per workspace package) to merge into a single logical namespace.

Directories that must **never** have `__init__.py`:

- `src/praecepta/`
- `src/praecepta/foundation/`
- `src/praecepta/infra/`
- `src/praecepta/domain/`
- `src/praecepta/integration/`

---

## Leaf-Only `__init__.py` Pattern

Only the leaf package directory gets an `__init__.py` with explicit `__all__` exports. The leaf is the terminal namespace segment that contains the actual source modules.

Example from `infra-fastapi`:

```
packages/infra-fastapi/src/
  praecepta/                          # NO __init__.py (namespace)
    infra/                            # NO __init__.py (namespace)
      fastapi/                        # Leaf package
        __init__.py                   # Has __init__.py with __all__
        py.typed                      # PEP 561 marker
        app_factory.py
        settings.py
        _health.py
        error_handlers.py
        lifespan.py
        middleware/                    # Sub-package of leaf
          __init__.py
          request_id.py
          request_context.py
          tenant_state.py
        dependencies/
          __init__.py
          feature_flags.py
          resource_limits.py
```

The leaf `__init__.py` re-exports public API and declares `__all__`:

```python
# praecepta/infra/fastapi/__init__.py
from praecepta.infra.fastapi.app_factory import create_app
from praecepta.infra.fastapi.settings import AppSettings, CORSSettings
# ... other imports

__all__ = [
    "AppSettings",
    "CORSSettings",
    "create_app",
    # ...
]
```

---

## PEP 561 `py.typed` Marker

Every leaf package directory contains a `py.typed` marker file (empty) so that mypy and other type checkers recognize the package as typed. The marker goes in the same directory as the leaf `__init__.py`:

```
packages/infra-fastapi/src/praecepta/infra/fastapi/py.typed
packages/foundation-domain/src/praecepta/foundation/domain/py.typed
```

---

## Workspace Configuration

### Root `pyproject.toml`

The root `pyproject.toml` declares the workspace and maps all workspace packages:

```toml
[tool.uv]
package = false

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
praecepta-foundation-domain = { workspace = true }
praecepta-foundation-application = { workspace = true }
praecepta-infra-fastapi = { workspace = true }
praecepta-infra-eventsourcing = { workspace = true }
praecepta-infra-auth = { workspace = true }
praecepta-infra-persistence = { workspace = true }
praecepta-infra-observability = { workspace = true }
praecepta-infra-taskiq = { workspace = true }
praecepta-domain-tenancy = { workspace = true }
praecepta-domain-identity = { workspace = true }
praecepta-integration-tenancy-identity = { workspace = true }
```

### Per-Package `pyproject.toml`

Each package declares its own workspace dependencies and uses hatchling as the build backend:

```toml
[project]
name = "praecepta-infra-fastapi"
version = "0.1.0"
dependencies = [
    "praecepta-foundation-domain",
    "praecepta-foundation-application",
    "fastapi>=0.115",
    "pydantic-settings>=2.0",
]

[tool.uv.sources]
praecepta-foundation-domain = { workspace = true }
praecepta-foundation-application = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/praecepta"]
```

The `packages = ["src/praecepta"]` directive tells hatchling to include the `praecepta` namespace tree from the `src/` directory.

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Adding `__init__.py` to `src/praecepta/` | `ModuleNotFoundError` for other packages sharing the namespace | Delete the file; only leaf directories get `__init__.py` |
| Adding `__init__.py` to `src/praecepta/infra/` | Namespace collision; only one infra package importable at a time | Delete the file |
| Missing `py.typed` in leaf directory | mypy reports `Skipping analyzing "praecepta.infra.fastapi": module is installed, but missing library stubs` | Add empty `py.typed` to the leaf package directory |
| `packages = ["src"]` instead of `["src/praecepta"]` in hatchling config | Build installs a top-level `src` package | Use `packages = ["src/praecepta"]` |
| Missing `namespace_packages = true` in mypy config | mypy cannot resolve cross-package imports | Set `namespace_packages = true` and `explicit_package_bases = true` in `[tool.mypy]` |

---

## See Also

- [con-package-types.md](../concepts/con-package-types.md) -- Package type taxonomy
- [ref-package-structure.md](ref-package-structure.md) -- Feature-slice directory layout
- PADR-002 -- Namespace package decision
