# Namespace Packages

Praecepta is a monorepo with 11 packages that all share the `praecepta.*` namespace. This is made possible by **PEP 420 implicit namespace packages** — a Python feature where directories without `__init__.py` files are treated as namespace packages, allowing multiple physical directories to merge into a single logical namespace.

## The Rule

**Only the leaf package directory gets an `__init__.py` file.** All intermediate directories in the namespace hierarchy must **not** have `__init__.py`.

```
packages/infra-fastapi/src/
  praecepta/                      # NO __init__.py
    infra/                        # NO __init__.py
      fastapi/                    # Leaf — HAS __init__.py
        __init__.py               # Public API with __all__
        py.typed                  # PEP 561 type marker
        app_factory.py
        settings.py
        middleware/
          __init__.py
          request_id.py
```

## Why This Matters

If you add an `__init__.py` to `src/praecepta/` in one package, Python treats it as a regular package and stops looking for other `praecepta` directories. This means all other praecepta packages become unimportable.

**Directories that must NEVER have `__init__.py`:**

- `src/praecepta/`
- `src/praecepta/foundation/`
- `src/praecepta/infra/`
- `src/praecepta/domain/`
- `src/praecepta/integration/`

## Package Layout Template

When creating a new package:

```
packages/{name}/
├── pyproject.toml
├── src/
│   └── praecepta/                    # NO __init__.py
│       └── {layer}/{name}/
│           ├── __init__.py           # Leaf package — public API
│           └── py.typed              # PEP 561 marker
└── tests/
    └── test_{name}.py
```

## The `__init__.py` Pattern

The leaf `__init__.py` re-exports the package's public API and declares `__all__`:

```python
"""My package — brief description."""

from my_package.module_a import Foo, Bar
from my_package.module_b import Baz

__all__ = [
    "Bar",
    "Baz",
    "Foo",
]
```

## Build Configuration

Each package uses hatchling and must specify the correct package root:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/praecepta"]
```

The `packages = ["src/praecepta"]` directive tells hatchling to include the namespace tree from `src/`.

## Mypy Configuration

The root `pyproject.toml` configures mypy to find all packages:

```toml
[tool.mypy]
namespace_packages = true
explicit_package_bases = true
mypy_path = "packages/foundation-domain/src:packages/foundation-application/src:..."
```

Both `namespace_packages` and `explicit_package_bases` must be `true` for mypy to resolve cross-package imports correctly.

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `__init__.py` in `src/praecepta/` | `ModuleNotFoundError` for other packages | Delete the file |
| `__init__.py` in `src/praecepta/infra/` | Only one infra package importable | Delete the file |
| Missing `py.typed` in leaf | mypy reports missing stubs | Add empty `py.typed` to leaf directory |
| `packages = ["src"]` in hatchling | Installs a top-level `src` package | Use `packages = ["src/praecepta"]` |
