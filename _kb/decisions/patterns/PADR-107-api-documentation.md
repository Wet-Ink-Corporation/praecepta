<!-- Derived from {Project} PADR-107-api-documentation -->
# PADR-107: API Documentation Standards

**Status:** Accepted
**Date:** 2025-02-02
**Deciders:** Architecture Team
**Categories:** Pattern, API

---

## Context

{Project} provides a RESTful API that requires comprehensive, accurate documentation for:

- AI agent developers consuming the API
- Internal development teams maintaining the codebase
- API client SDK generation (stable operation IDs)
- Interactive testing via documentation UIs

We selected Scalar as the primary documentation UI due to its modern design, better code examples, and superior interactive testing experience compared to Swagger UI.

## Decision

We adopt a comprehensive API documentation standard using **Scalar as the primary documentation UI** alongside Swagger UI and ReDoc, with strict requirements for OpenAPI metadata.

### Documentation Endpoints

| Path | Tool | Purpose |
|------|------|---------|
| `/scalar` | Scalar | Primary interactive documentation (recommended) |
| `/docs` | Swagger UI | Alternative, FastAPI default |
| `/redoc` | ReDoc | Reference documentation |
| `/openapi.json` | OpenAPI | Machine-readable specification |

### Operation ID Convention

All endpoints **MUST** have an `operation_id` following the pattern: `{context}_{action}_{resource}`

Examples:

- `memory_create_block` - Create a order
- `memory_get_block` - Get a single block
- `memory_query_blocks` - Query blocks with filters
- `memory_add_membership` - Add membership to block
- `health_get_status` - Get health status
- `health_get_readiness` - Check readiness

This convention:

- Provides clear context for future multi-context expansion
- Generates readable SDK method names
- Matches existing vertical slice folder naming

### Required Endpoint Metadata

Every endpoint decorator **MUST** include:

```python
@router.post(
    "/path",
    response_model=ResponseModel,
    summary="Short description",           # Required: < 50 chars
    description="Detailed explanation.",   # Required: full context
    operation_id="context_action_resource", # Required: unique ID
    responses={                            # Required: all status codes
        201: {"description": "Success case"},
        400: {"description": "Validation error"},
        404: {"description": "Not found"},
    },
)
```

### Pydantic Model Requirements

All request/response models **MUST** include:

1. **Class docstring** - Describes the model purpose
2. **Field descriptions** - Every field uses `Field(description=...)`
3. **JSON schema examples** - Realistic example data via `model_config`

```python
class CreateBlockRequest(BaseModel):
    """Request body for block creation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Q1 2025 Product Roadmap",
                    "scope_type": "PROJECT",
                    "scope_id": "123e4567-e89b-12d3-a456-426614174000",
                    "memory_category": "WORKING",
                    "tags": ["roadmap", "product"],
                }
            ]
        }
    )

    title: str = Field(..., min_length=1, max_length=255, description="Block display name")
    scope_type: ScopeType = Field(..., description="Organizational scope level")
    # ... all fields with descriptions
```

### Security Scheme Documentation

Document security requirements in OpenAPI even before enforcement:

```python
SECURITY_SCHEMES = {
    "TenantHeader": {
        "type": "apiKey",
        "in": "header",
        "name": "X-Tenant-ID",
        "description": "Multi-tenant isolation identifier (required)",
    },
    "UserHeader": {
        "type": "apiKey",
        "in": "header",
        "name": "X-User-ID",
        "description": "Acting user identifier for audit trails",
    },
}
```

### Tags Metadata

Each bounded context defines tag metadata for sidebar organization:

```python
TAGS_METADATA = [
    {
        "name": "health",
        "description": "Health check and readiness endpoints for Kubernetes probes.",
    },
    {
        "name": "memory",
        "description": "order management for AI agent context organization.",
    },
]
```

## Implementation Notes

### Configuration

OpenAPI settings are managed via `APISettings` in `shared/infrastructure/config/api.py`:

- `scalar_url` - Scalar documentation path (default: `/scalar`)
- `api_contact_name`, `api_contact_email` - Contact metadata
- `api_license_name` - License information

### Custom OpenAPI Schema

The OpenAPI schema is customized in `main.py` to add security schemes and external docs that FastAPI doesn't natively support:

```python
def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(...)
    schema["components"]["securitySchemes"] = SECURITY_SCHEMES
    schema["externalDocs"] = EXTERNAL_DOCS
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi
```

## Rationale

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Scalar as primary | Coexist with Swagger | Modern UI, better DX, zero migration risk |
| Operation ID format | `{context}_{action}_{resource}` | Stable SDK generation, clear naming |
| Mandatory examples | `json_schema_extra.examples` | Interactive "Try It" functionality |
| Security schemes | Document early | Prepares consumers for future auth |

## Consequences

### Positive

1. **Consistent documentation** - All endpoints follow the same pattern
2. **SDK stability** - Fixed operation IDs enable reliable code generation
3. **Interactive testing** - Scalar with examples enables quick API exploration
4. **Self-documenting** - Reduces need for external documentation

### Negative

1. **Maintenance overhead** - Examples must stay synchronized with code
2. **Verbose models** - Each model requires `model_config` with examples

### Mitigations

| Risk | Mitigation |
|------|------------|
| Stale examples | Code review checklist includes example validation |
| Missing operation IDs | Linting rule to enforce presence |
| Inconsistent naming | ADR serves as reference; PR review |

## Alternatives Considered

| Alternative | Rejection Reason |
|-------------|------------------|
| Swagger UI only | Less modern, inferior interactive experience |
| No examples | Poor DX, "Try It" unusable without sample data |
| Auto-generated operation IDs | Unstable across refactors, breaks SDK consumers |

## Related Decisions

- [PADR-101: Vertical Slice Architecture](../patterns/PADR-101-vertical-slices.md) - Endpoint organization
- [PADR-102: Hexagonal Ports](../patterns/PADR-102-hexagonal-ports.md) - API as primary adapter
- [PADR-103: Error Handling](../patterns/PADR-103-error-handling.md) - RFC 7807 responses

## References

- [OpenAPI 3.1 Specification](https://spec.openapis.org/oas/v3.1.0)
- [Scalar Documentation](https://guides.scalar.com/)
- [FastAPI Metadata Documentation](https://fastapi.tiangolo.com/tutorial/metadata/)
- [scalar-fastapi PyPI](https://pypi.org/project/scalar-fastapi/)
