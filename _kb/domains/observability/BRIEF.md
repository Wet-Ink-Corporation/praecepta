# Observability Domain

Logging, tracing, metrics, and health checks across the platform.

## Mental Model

Structured logging with correlation IDs. OpenTelemetry-compatible tracing. Health checks for all external dependencies. Every request gets a trace span; domain events create child spans (PADR-105).

## Key Patterns

- **Logging:** Structured JSON, `structlog` with context binding
- **Tracing:** Span creation per request, propagated through context
- **Metrics:** Delta counter projections for aggregate metrics
- **Health:** Liveness + readiness endpoints checking DB, Neo4j, Redis

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/patterns/PADR-105-observability.md` | Observability patterns |
| `references/con-observability.md` | Observability overview |
| `references/ref-infra-delta-counter-projection.md` | Delta counter pattern |
