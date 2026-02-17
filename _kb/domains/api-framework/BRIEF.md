# API Framework Domain

FastAPI routes, DTOs, error handling, and middleware stack.

## Mental Model

FastAPI provides the HTTP layer. Each bounded context has an `api/` module with routers. Request/response DTOs use Pydantic v2. Error handling follows a consistent exception → HTTP status mapping (PADR-103). OpenAPI docs auto-generated (PADR-107).

## Key Patterns

- **Routers:** Per-context router, mounted on main app
- **DTOs:** Pydantic `BaseModel` for request/response, separate from domain models
- **Error mapping:** Domain exceptions → HTTP status codes (PADR-103)
- **Middleware:** JWT auth → tenant context → request logging (priority-ordered, PADR-122)
- **Auto-discovery:** `create_app()` discovers routers, middleware, error handlers, lifespan hooks via entry points (PADR-122)
- **Depends:** Application singleton via `Depends()` (PADR-110)
- **Sync/async:** Command endpoints `def`, query endpoints `async def` (PADR-109)

## File Layout

```
context/api/
├── router.py          # Route definitions
├── dependencies.py    # FastAPI Depends
└── dtos.py           # Request/Response models
```

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/patterns/PADR-103-error-handling.md` | Error handling patterns |
| `_kb/decisions/patterns/PADR-107-api-documentation.md` | OpenAPI conventions |
| `_kb/decisions/patterns/PADR-109-sync-first-eventsourcing.md` | Sync vs async endpoints |
| `_kb/decisions/patterns/PADR-110-application-lifecycle.md` | Depends singleton |
| `references/con-error-handling.md` | Error architecture |
| `references/ref-error-handling.md` | Error code reference |
| `references/ref-app-factory.md` | App factory API, entry point groups, contribution types |
| `references/ref-request-context.md` | Request context architecture and usage |
| `references/proc-add-contribution.md` | How to add routers, middleware, lifespan hooks |
