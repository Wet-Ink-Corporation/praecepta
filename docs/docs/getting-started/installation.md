# Installation

## Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

## Install the Framework

Install the top-level meta-package to get all praecepta packages:

```bash
uv add praecepta
```

Or install individual packages based on what you need:

```bash
# Foundation layer (always required)
uv add praecepta-foundation-domain praecepta-foundation-application

# Infrastructure layer (pick what you need)
uv add praecepta-infra-fastapi          # FastAPI app factory + middleware
uv add praecepta-infra-eventsourcing    # Event store + projections
uv add praecepta-infra-auth             # JWT/JWKS + API key authentication
uv add praecepta-infra-persistence      # PostgreSQL + Redis + RLS
uv add praecepta-infra-observability    # Structured logging + tracing

# Domain layer (pre-built bounded contexts)
uv add praecepta-domain-tenancy         # Multi-tenant management
uv add praecepta-domain-identity        # User + agent identity
```

## Verify Installation

```python
from praecepta.infra.fastapi import create_app

app = create_app()
# All installed packages auto-register via entry-point discovery
```

## Development Setup (Contributing)

To work on praecepta itself:

```bash
git clone https://github.com/wetink/praecepta.git
cd praecepta
make install    # uv sync --dev
make verify     # lint + typecheck + boundaries + test
```
