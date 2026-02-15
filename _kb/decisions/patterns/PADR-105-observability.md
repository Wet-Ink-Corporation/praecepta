<!-- Derived from {Project} PADR-105-observability -->
# PADR-105: Logging and Observability

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Pattern, Operations

---

## Context

{Project} requires comprehensive observability for:

- Debugging issues in production
- Performance monitoring and optimization
- Security auditing and compliance
- Understanding system behavior

The observability stack must support:

- Distributed tracing (across bounded contexts)
- Structured logging
- Metrics collection
- Correlation between logs, traces, and metrics

## Decision

**We will implement observability using OpenTelemetry and structlog**, with the following components:

- **Tracing:** OpenTelemetry SDK
- **Logging:** structlog with JSON output
- **Metrics:** OpenTelemetry Metrics API
- **Correlation:** Trace context propagation

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    {Project} APPLICATION                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   structlog │  │ OpenTelemetry│ │ OpenTelemetry│         │
│  │   (Logging) │  │  (Tracing)   │ │  (Metrics)   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                   OTEL Collector                            │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Jaeger  │    │   Loki   │    │Prometheus│
    │ (Traces) │    │  (Logs)  │    │(Metrics) │
    └──────────┘    └──────────┘    └──────────┘
```

## Structured Logging

### Configuration

```python
# shared/observability/logging.py
import structlog
from structlog.contextvars import merge_contextvars

def configure_logging(env: str = "production"):
    """Configure structured logging."""

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_context,  # Custom processor
    ]

    if env == "development":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ])

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )

def add_trace_context(logger, method_name, event_dict):
    """Add OpenTelemetry trace context to log entries."""
    from opentelemetry import trace

    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")

    return event_dict
```

### Logger Usage

```python
# In application code
import structlog

logger = structlog.get_logger()

class CreateBlockHandler:
    async def handle(self, command: CreateBlockCommand) -> UUID:
        logger.info(
            "creating_block",
            title=command.title,
            scope_type=command.scope_type,
            owner_id=command.owner_id
        )

        block = Order(...)
        await self._repository.save(block)

        logger.info(
            "block_created",
            block_id=str(block.id),
            title=block.title
        )

        return block.id
```

### Log Output (JSON)

```json
{
  "timestamp": "2025-01-17T10:30:00.123Z",
  "level": "info",
  "event": "block_created",
  "block_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Research Notes",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "tenant_id": "acme",
  "user_id": "user-123"
}
```

## Distributed Tracing

### Setup

```python
# shared/observability/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def configure_tracing(service_name: str, otlp_endpoint: str):
    """Configure OpenTelemetry tracing."""

    provider = TracerProvider(
        resource=Resource.create({
            SERVICE_NAME: service_name,
            SERVICE_VERSION: "1.0.0"
        })
    )

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    # Auto-instrumentation
    FastAPIInstrumentor.instrument()
    AsyncPGInstrumentor.instrument()
    HTTPXClientInstrumentor.instrument()

    return trace.get_tracer(__name__)
```

### Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class HybridRetriever:
    async def retrieve(self, query: str, user_principals: list[str]) -> list[Result]:
        with tracer.start_as_current_span("hybrid_retrieval") as span:
            span.set_attribute("query.length", len(query))
            span.set_attribute("user.principals_count", len(user_principals))

            # Parallel retrieval with child spans
            with tracer.start_as_current_span("vector_search"):
                semantic = await self._vector_search(query, user_principals)
                span.set_attribute("results.count", len(semantic))

            with tracer.start_as_current_span("bm25_search"):
                keyword = await self._bm25_search(query, user_principals)

            with tracer.start_as_current_span("graph_search"):
                graph = await self._graph_search(query, user_principals)

            with tracer.start_as_current_span("fusion_and_rerank"):
                results = self._fusion_rerank([semantic, keyword, graph])

            span.set_attribute("final.results_count", len(results))
            return results
```

## Metrics

### Setup

```python
# shared/observability/metrics.py
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

def configure_metrics(service_name: str, otlp_endpoint: str):
    """Configure OpenTelemetry metrics."""

    provider = MeterProvider(
        resource=Resource.create({SERVICE_NAME: service_name}),
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=otlp_endpoint),
                export_interval_millis=60000
            )
        ]
    )

    metrics.set_meter_provider(provider)
    return metrics.get_meter(__name__)
```

### Application Metrics

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

# Counters
block_created_counter = meter.create_counter(
    name="{Project}.blocks.created",
    description="Number of resources created",
    unit="1"
)

# Histograms
retrieval_duration = meter.create_histogram(
    name="{Project}.retrieval.duration",
    description="Time spent in retrieval operations",
    unit="ms"
)

# Gauges (via callback)
def get_active_blocks():
    # Query database for count
    return db.fetchval("SELECT COUNT(*) FROM orders WHERE archived = false")

meter.create_observable_gauge(
    name="{Project}.blocks.active",
    callbacks=[lambda options: [Observation(get_active_blocks())]],
    description="Number of active resources"
)

# Usage
class CreateBlockHandler:
    async def handle(self, command: CreateBlockCommand) -> UUID:
        block = Order(...)
        await self._repository.save(block)

        block_created_counter.add(
            1,
            attributes={
                "scope_type": command.scope_type,
                "tenant_id": command.tenant_id
            }
        )

        return block.id
```

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `{Project}.blocks.created` | Counter | Blocks created |
| `{Project}.retrieval.duration` | Histogram | Retrieval latency |
| `{Project}.retrieval.results` | Histogram | Result count distribution |
| `{Project}.security.access_denied` | Counter | Access denials |
| `{Project}.events.published` | Counter | Events published |
| `{Project}.blocks.active` | Gauge | Active block count |

## Context Propagation

### Request Context

```python
# shared/observability/context.py
import structlog
from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

class ObservabilityMiddleware:
    async def __call__(self, request: Request, call_next):
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request_id_var.set(request_id)

        # Set user context from JWT
        if hasattr(request.state, "user"):
            tenant_id_var.set(request.state.user.tenant_id)
            user_id_var.set(request.state.user.id)

        # Bind to structlog context
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            tenant_id=tenant_id_var.get(),
            user_id=user_id_var.get()
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
```

## Audit Logging

### Security Events

```python
# shared/observability/audit.py
import structlog
from enum import Enum

class AuditEvent(Enum):
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    BLOCK_CREATED = "block_created"
    BLOCK_ARCHIVED = "block_archived"
    CONTENT_ACCESSED = "content_accessed"

audit_logger = structlog.get_logger("audit")

class AuditLogger:
    def log(
        self,
        event: AuditEvent,
        resource_type: str,
        resource_id: str,
        action: str,
        **extra
    ):
        audit_logger.info(
            event.value,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            user_id=user_id_var.get(),
            tenant_id=tenant_id_var.get(),
            **extra
        )

# Usage
audit = AuditLogger()

class SecurityService:
    async def check_permission(self, user_id, permission, resource_type, resource_id):
        allowed = await self._spicedb.check(...)

        audit.log(
            AuditEvent.ACCESS_GRANTED if allowed else AuditEvent.ACCESS_DENIED,
            resource_type=resource_type,
            resource_id=resource_id,
            action=permission
        )

        return allowed
```

## Configuration

### Environment Variables

```bash
# Observability configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME={Project}
LOG_LEVEL=INFO
LOG_FORMAT=json  # or "console" for development
```

### FastAPI Integration

```python
# main.py
from fastapi import FastAPI
from shared.observability import configure_logging, configure_tracing, configure_metrics

app = FastAPI()

# Configure observability
configure_logging(env=settings.ENVIRONMENT)
tracer = configure_tracing(
    service_name="{Project}",
    otlp_endpoint=settings.OTEL_ENDPOINT
)
meter = configure_metrics(
    service_name="{Project}",
    otlp_endpoint=settings.OTEL_ENDPOINT
)

# Add middleware
app.add_middleware(ObservabilityMiddleware)
```

## Related Decisions

- PADR-103: Error Handling (log error events)
- PADR-106: Configuration Management (observability config)

## References

- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [structlog Documentation](https://www.structlog.org/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
