# Observability

> Logging, tracing, metrics, and monitoring

---

## Overview

{Project} implements comprehensive observability through structured logging, distributed tracing, and metrics collection. This enables debugging, performance analysis, and operational monitoring across all bounded contexts.

---

## Observability Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          OBSERVABILITY STACK                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        COLLECTION                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │ Structured  │  │ Distributed │  │   Metrics   │                 │   │
│  │  │   Logging   │  │   Tracing   │  │ Collection  │                 │   │
│  │  │ (structlog) │  │  (OTEL)     │  │(prometheus) │                 │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │   │
│  └─────────┼────────────────┼────────────────┼─────────────────────────┘   │
│            │                │                │                              │
│            ▼                ▼                ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        EXPORT                                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │   stdout    │  │    OTLP     │  │  /metrics   │                 │   │
│  │  │   (JSON)    │  │  Exporter   │  │  Endpoint   │                 │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │   │
│  └─────────┼────────────────┼────────────────┼─────────────────────────┘   │
│            │                │                │                              │
│            ▼                ▼                ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        STORAGE                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │    Loki     │  │    Tempo    │  │ Prometheus  │                 │   │
│  │  │   (Logs)    │  │  (Traces)   │  │  (Metrics)  │                 │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │   │
│  └─────────┼────────────────┼────────────────┼─────────────────────────┘   │
│            │                │                │                              │
│            └────────────────┼────────────────┘                              │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        VISUALIZATION                                 │   │
│  │                       ┌─────────────┐                               │   │
│  │                       │   Grafana   │                               │   │
│  │                       │ Dashboards  │                               │   │
│  │                       └─────────────┘                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Structured Logging

### Configuration

```python
import structlog
from structlog.typing import Processor

def configure_logging(
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure structured logging."""

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### Context Propagation

```python
from structlog.contextvars import bind_contextvars, clear_contextvars

class RequestContextMiddleware:
    """Middleware to set logging context per request."""

    async def __call__(self, request: Request, call_next):
        # Clear previous context
        clear_contextvars()

        # Extract trace context
        trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
        request.state.trace_id = trace_id

        # Bind context for all logs in this request
        bind_contextvars(
            trace_id=trace_id,
            tenant_id=getattr(request.state, "tenant_id", None),
            user_id=str(getattr(request.state, "user_id", None)),
            path=request.url.path,
            method=request.method,
        )

        response = await call_next(request)

        return response
```

### Logging Patterns

```python
import structlog

logger = structlog.get_logger()

# Domain Events
logger.info(
    "block_created",
    block_id=str(block_id),
    title=title,
    scope_type=scope_type.value,
    owner_id=str(owner_id),
)

# Operations
logger.info(
    "query_executed",
    query_id=str(query_id),
    query_text=query[:100],  # Truncate for privacy
    result_count=len(results),
    duration_ms=duration_ms,
)

# Errors
logger.error(
    "embedding_failed",
    document_id=str(document_id),
    error_type=type(e).__name__,
    error_message=str(e),
    retry_count=retry_count,
)

# Performance
logger.debug(
    "vector_search_completed",
    query_id=str(query_id),
    candidates=candidate_count,
    duration_ms=duration_ms,
)
```

### Log Output Format

```json
{
  "event": "query_executed",
  "timestamp": "2025-01-17T10:30:45.123456Z",
  "level": "info",
  "trace_id": "abc123xyz",
  "tenant_id": "acme-corp",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "path": "/api/v1/query",
  "method": "POST",
  "query_id": "query-789",
  "query_text": "machine learning best practices...",
  "result_count": 25,
  "duration_ms": 245
}
```

---

## Distributed Tracing

### OpenTelemetry Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

def configure_tracing(
    service_name: str,
    otlp_endpoint: str,
) -> None:
    """Configure OpenTelemetry tracing."""
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "service.version": __version__,
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })
    )

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Auto-instrument
    FastAPIInstrumentor.instrument()
    AsyncPGInstrumentor().instrument()
```

### Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class QueryHandler:
    async def handle(self, query: SearchQuery) -> SearchResults:
        with tracer.start_as_current_span(
            "query.search",
            attributes={
                "query.id": str(query.id),
                "query.scope": query.scope.value,
            },
        ) as span:
            # Vector search
            with tracer.start_as_current_span("query.vector_search") as vs_span:
                vector_results = await self._vector_search(query)
                vs_span.set_attribute("result_count", len(vector_results))

            # BM25 search
            with tracer.start_as_current_span("query.bm25_search") as bm25_span:
                bm25_results = await self._bm25_search(query)
                bm25_span.set_attribute("result_count", len(bm25_results))

            # Fusion
            with tracer.start_as_current_span("query.fusion"):
                fused = self._rrf_fusion(vector_results, bm25_results)

            # Security trimming
            with tracer.start_as_current_span("query.security_trim") as st_span:
                trimmed = await self._security_trim(fused, query.user_id)
                st_span.set_attributes({
                    "candidates": len(fused),
                    "allowed": len(trimmed),
                })

            span.set_attribute("final_result_count", len(trimmed))
            return SearchResults(items=trimmed)
```

### Trace Context Propagation

```python
from opentelemetry import trace
from opentelemetry.propagate import inject, extract

class ExternalServiceClient:
    """Client that propagates trace context."""

    async def call(self, endpoint: str, data: dict) -> dict:
        headers = {}
        inject(headers)  # Inject trace context

        async with self._session.post(
            endpoint,
            json=data,
            headers=headers,
        ) as response:
            return await response.json()

class IncomingRequestHandler:
    """Handler that extracts trace context."""

    async def handle(self, request: Request):
        context = extract(request.headers)
        with tracer.start_as_current_span(
            "incoming_request",
            context=context,
        ):
            # Process with correct parent span
            ...
```

---

## Metrics

### Metric Types

```python
from prometheus_client import Counter, Histogram, Gauge, Summary

# Counters - Monotonically increasing
requests_total = Counter(
    "{Project}_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

events_processed = Counter(
    "{Project}_events_processed_total",
    "Total domain events processed",
    ["event_type", "context"],
)

# Histograms - Request durations, sizes
request_duration = Histogram(
    "{Project}_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

query_latency = Histogram(
    "{Project}_query_latency_seconds",
    "Query latency by stage",
    ["stage"],  # vector, bm25, fusion, rerank, security
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Gauges - Current values
active_connections = Gauge(
    "{Project}_active_connections",
    "Current active database connections",
    ["database"],
)

projection_lag = Gauge(
    "{Project}_projection_lag_events",
    "Number of events behind for projection",
    ["projection"],
)

# Summaries - Quantiles
embedding_size = Summary(
    "{Project}_embedding_size_dimensions",
    "Embedding vector dimensions",
)
```

### Instrumenting Code

```python
from contextlib import contextmanager
import time

@contextmanager
def track_latency(histogram: Histogram, labels: dict):
    """Context manager to track operation latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        histogram.labels(**labels).observe(duration)

class QueryService:
    async def search(self, query: SearchQuery) -> SearchResults:
        with track_latency(query_latency, {"stage": "vector"}):
            vector_results = await self._vector_search(query)

        with track_latency(query_latency, {"stage": "bm25"}):
            bm25_results = await self._bm25_search(query)

        with track_latency(query_latency, {"stage": "fusion"}):
            fused = self._rrf_fusion(vector_results, bm25_results)

        with track_latency(query_latency, {"stage": "security"}):
            trimmed = await self._security_trim(fused)

        return SearchResults(items=trimmed)
```

### Key Metrics

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `requests_total` | Counter | method, endpoint, status | Request volume |
| `request_duration_seconds` | Histogram | method, endpoint | Latency distribution |
| `query_latency_seconds` | Histogram | stage | Query pipeline timing |
| `events_processed_total` | Counter | event_type, context | Event throughput |
| `projection_lag_events` | Gauge | projection | Projection health |
| `embedding_requests_total` | Counter | provider, status | External API usage |
| `active_blocks` | Gauge | scope_type | Memory block count |
| `cache_hits_total` | Counter | cache_name | Cache effectiveness |

---

## Health Checks

### Health Endpoint

```python
from fastapi import FastAPI, status
from pydantic import BaseModel
from enum import Enum

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth(BaseModel):
    name: str
    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None

class HealthResponse(BaseModel):
    status: HealthStatus
    components: list[ComponentHealth]
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Database = Depends(get_db),
    redis: Redis = Depends(get_redis),
    spicedb: SpiceDB = Depends(get_spicedb),
) -> HealthResponse:
    """Comprehensive health check."""
    components = []

    # Database check
    components.append(await _check_database(db))

    # Redis check
    components.append(await _check_redis(redis))

    # SpiceDB check
    components.append(await _check_spicedb(spicedb))

    # Neo4j check
    components.append(await _check_neo4j())

    # Determine overall status
    if all(c.status == HealthStatus.HEALTHY for c in components):
        overall = HealthStatus.HEALTHY
    elif any(c.status == HealthStatus.UNHEALTHY for c in components):
        overall = HealthStatus.UNHEALTHY
    else:
        overall = HealthStatus.DEGRADED

    return HealthResponse(
        status=overall,
        components=components,
        version=__version__,
    )

async def _check_database(db: Database) -> ComponentHealth:
    try:
        start = time.perf_counter()
        await db.execute("SELECT 1")
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="postgresql",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as e:
        return ComponentHealth(
            name="postgresql",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )
```

### Liveness vs Readiness

```python
@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe - is the process running?"""
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness(
    db: Database = Depends(get_db),
) -> dict:
    """Readiness probe - can we serve requests?"""
    try:
        await db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not ready",
        )
```

---

## Alerting

### Alert Rules

```yaml
# prometheus-alerts.yml
groups:
  - name: {Project}
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate({Project}_requests_total{status=~"5.."}[5m]))
          / sum(rate({Project}_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate (> 5%)"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # Slow queries
      - alert: SlowQueryLatency
        expr: |
          histogram_quantile(0.95,
            rate({Project}_query_latency_seconds_bucket{stage="total"}[5m])
          ) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 query latency > 500ms"

      # Projection lag
      - alert: ProjectionLag
        expr: {Project}_projection_lag_events > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Projection {{ $labels.projection }} is lagging"
          description: "{{ $value }} events behind"

      # Database connections
      - alert: HighDatabaseConnections
        expr: {Project}_active_connections{database="postgresql"} > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connection count"
```

---

## Dashboards

### Key Dashboard Panels

| Panel | Query | Purpose |
|-------|-------|---------|
| Request Rate | `rate({Project}_requests_total[5m])` | Traffic volume |
| Error Rate | `rate({Project}_requests_total{status=~"5.."}[5m])` | Error tracking |
| P95 Latency | `histogram_quantile(0.95, rate({Project}_request_duration_seconds_bucket[5m]))` | Performance |
| Query Stages | `histogram_quantile(0.95, rate({Project}_query_latency_seconds_bucket[5m])) by (stage)` | Pipeline analysis |
| Projection Lag | `{Project}_projection_lag_events` | Projection health |
| Active Blocks | `{Project}_active_blocks` | Usage tracking |

### Dashboard JSON Template

```json
{
  "dashboard": {
    "title": "{Project} Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate({Project}_requests_total[5m])) by (endpoint)"
          }
        ]
      },
      {
        "title": "P95 Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate({Project}_request_duration_seconds_bucket[5m])) by (le, endpoint))"
          }
        ]
      },
      {
        "title": "Query Pipeline Latency",
        "type": "heatmap",
        "targets": [
          {
            "expr": "sum(rate({Project}_query_latency_seconds_bucket[5m])) by (le, stage)"
          }
        ]
      }
    ]
  }
}
```

---

## Log Aggregation Queries

### Useful Loki Queries

```logql
# Errors in last hour
{app="{Project}"} |= "level=error" | json

# Slow queries (> 500ms)
{app="{Project}"} | json | duration_ms > 500

# Specific trace
{app="{Project}"} | json | trace_id="abc123xyz"

# Events for specific tenant
{app="{Project}"} | json | tenant_id="acme-corp"

# Authentication failures
{app="{Project}"} | json | event="authentication_failed"

# Query patterns
{app="{Project}"} | json | event="query_executed"
  | line_format "{{.query_text}}"
```

---

## See Also

- [Deployment Procedure](../07-deployment/proc-deployment-procedure.md) - Monitoring setup
- [Error Handling](con-error-handling.md) - Error logging patterns
- [Infrastructure](../07-deployment/con-infrastructure.md) - Observability stack
