# Quality Measures

> How quality is ensured, measured, and monitored

---

## Overview

This document describes how {Project}'s quality attributes are measured and monitored. It covers metrics, tooling, and processes for continuous quality assurance.

---

## Measurement Framework

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        QUALITY MEASUREMENT FRAMEWORK                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          COLLECTION                                   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│  │  │   Metrics    │  │    Logs      │  │   Traces     │                │  │
│  │  │ (Prometheus) │  │   (Loki)     │  │  (Tempo)     │                │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                               │                                              │
│                               ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          ANALYSIS                                     │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│  │  │  Dashboards  │  │    Alerts    │  │   Reports    │                │  │
│  │  │  (Grafana)   │  │(Alertmanager)│  │ (Scheduled)  │                │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                               │                                              │
│                               ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          ACTION                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│  │  │   On-Call    │  │  Automation  │  │   Review     │                │  │
│  │  │  Response    │  │  (Scaling)   │  │   (Weekly)   │                │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Measures

### Metrics

| Metric | Formula | Target | Alert Threshold |
|--------|---------|--------|-----------------|
| Unauthorized access rate | `auth_denied / total_requests` | 0% | > 0 |
| Security trimming latency | `P95(trimming_duration)` | < 50ms | > 100ms |
| ACL sync lag | `time_since_last_sync` | < 5 min | > 10 min |
| Token validation failures | `count(jwt_invalid)` | Near 0 | > 10/min |

### Prometheus Queries

```promql
# Unauthorized access attempts
sum(rate({Project}_access_denied_total[5m])) by (reason)

# Security trimming latency
histogram_quantile(0.95,
  rate({Project}_security_trimming_seconds_bucket[5m])
)

# ACL sync freshness
time() - {Project}_acl_last_sync_timestamp
```

### Audit Reports

```sql
-- Weekly security report
SELECT
    DATE_TRUNC('day', timestamp) as day,
    COUNT(*) FILTER (WHERE outcome = 'DENIED') as access_denied,
    COUNT(*) FILTER (WHERE outcome = 'SUCCESS') as access_granted,
    COUNT(DISTINCT user_id) as unique_users
FROM audit_log
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1;
```

---

## Reliability Measures

### Metrics

| Metric | Formula | Target | Alert Threshold |
|--------|---------|--------|-----------------|
| Availability | `uptime / total_time` | 99.9% | < 99.5% |
| Error rate | `errors / requests` | < 0.1% | > 1% |
| Event store lag | `max(position) - min(projection_position)` | < 100 | > 1000 |
| Recovery time | `time_to_healthy` | < 15 min | > 30 min |

### Prometheus Queries

```promql
# Service availability
avg_over_time(up{job="{Project}"}[24h]) * 100

# Error rate by endpoint
sum(rate({Project}_requests_total{status=~"5.."}[5m])) by (endpoint)
/ sum(rate({Project}_requests_total[5m])) by (endpoint)

# Projection lag
{Project}_projection_lag_events
```

### SLO Dashboard

```yaml
# SLO definition
slo:
  name: {Project}-availability
  target: 99.9
  window: 30d
  indicator:
    good: {Project}_requests_total{status!~"5.."}
    total: {Project}_requests_total
```

---

## Performance Measures

### Metrics

| Metric | Formula | Target | Alert Threshold |
|--------|---------|--------|-----------------|
| Query P95 latency | `histogram_quantile(0.95, ...)` | < 500ms | > 750ms |
| Query P99 latency | `histogram_quantile(0.99, ...)` | < 1000ms | > 1500ms |
| Throughput | `sum(rate(requests[1m]))` | > 1000 QPS | < 500 QPS |
| Ingestion rate | `rate(documents_ingested)` | > 100/min | < 50/min |

### Prometheus Queries

```promql
# Query latency by stage
histogram_quantile(0.95,
  sum(rate({Project}_query_latency_seconds_bucket[5m])) by (le, stage)
)

# Request throughput
sum(rate({Project}_requests_total[1m]))

# Ingestion throughput
sum(rate({Project}_documents_ingested_total[5m])) * 60
```

### Load Testing

```python
# locust load test
from locust import HttpUser, task, between

class QueryUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(10)
    def search_query(self):
        self.client.post("/api/v1/query/search", json={
            "query": "machine learning",
            "limit": 10
        })

    @task(3)
    def get_block(self):
        self.client.get(f"/api/v1/memory/blocks/{self.block_id}")
```

---

## Relevance Measures

### Metrics

| Metric | Formula | Description | Target |
|--------|---------|-------------|--------|
| MRR@10 | Mean Reciprocal Rank at 10 | Relevance of top results | > 0.7 |
| Precision@5 | Relevant / Retrieved at 5 | Result quality | > 0.8 |
| Recall@20 | Found / Total Relevant at 20 | Coverage | > 0.6 |
| Reranking lift | `(reranked_mrr - base_mrr) / base_mrr` | Reranking improvement | > 20% |

### Evaluation Pipeline

```python
class RelevanceEvaluator:
    """Evaluate retrieval quality against golden dataset."""

    async def evaluate(self, golden_set: list[GoldenQuery]) -> Metrics:
        results = []

        for query in golden_set:
            retrieved = await self.search(query.text)
            results.append(EvaluationResult(
                query_id=query.id,
                retrieved_ids=[r.id for r in retrieved],
                relevant_ids=query.relevant_ids,
            ))

        return Metrics(
            mrr_at_10=self._compute_mrr(results, k=10),
            precision_at_5=self._compute_precision(results, k=5),
            recall_at_20=self._compute_recall(results, k=20),
        )

    def _compute_mrr(self, results, k: int) -> float:
        """Mean Reciprocal Rank."""
        reciprocal_ranks = []
        for r in results:
            for i, doc_id in enumerate(r.retrieved_ids[:k]):
                if doc_id in r.relevant_ids:
                    reciprocal_ranks.append(1 / (i + 1))
                    break
            else:
                reciprocal_ranks.append(0)
        return sum(reciprocal_ranks) / len(reciprocal_ranks)
```

### A/B Testing

```python
class RelevanceExperiment:
    """A/B test for relevance improvements."""

    async def run_experiment(
        self,
        control: SearchConfig,
        treatment: SearchConfig,
        query_set: list[str],
    ) -> ExperimentResult:
        control_metrics = []
        treatment_metrics = []

        for query in query_set:
            # Control
            control_results = await self.search(query, config=control)
            control_metrics.append(self._score(control_results))

            # Treatment
            treatment_results = await self.search(query, config=treatment)
            treatment_metrics.append(self._score(treatment_results))

        return ExperimentResult(
            control_mean=statistics.mean(control_metrics),
            treatment_mean=statistics.mean(treatment_metrics),
            p_value=self._t_test(control_metrics, treatment_metrics),
        )
```

---

## Maintainability Measures

### Metrics

| Metric | Tool | Target | Measurement |
|--------|------|--------|-------------|
| Test coverage | pytest-cov | 80%+ | CI/CD |
| Cyclomatic complexity | radon | < 10 | Pre-commit |
| Import boundaries | import-linter | 0 violations | CI/CD |
| Documentation coverage | interrogate | > 80% | CI/CD |

### Static Analysis

```yaml
# pyproject.toml
[tool.ruff]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
addopts = "--cov={Project} --cov-report=term-missing --cov-fail-under=80"
```

### Code Quality Dashboard

```promql
# Build duration trend
avg_over_time(github_workflow_duration_seconds{workflow="build"}[7d])

# Test pass rate
sum(github_workflow_status{status="success"})
/ sum(github_workflow_status)

# Lines of code growth
{Project}_lines_of_code
```

---

## Quality Gates

### Pull Request Gates

| Gate | Tool | Threshold | Block |
|------|------|-----------|-------|
| Unit tests | pytest | 100% pass | Yes |
| Coverage | pytest-cov | > 80% | Yes |
| Type checking | mypy | 0 errors | Yes |
| Linting | ruff | 0 errors | Yes |
| Import boundaries | import-linter | 0 violations | Yes |
| Security scan | bandit | No high severity | Yes |

### CI Pipeline

```yaml
# .github/workflows/quality.yml
name: Quality Gates

on: [pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Unit Tests
        run: pytest tests/unit --cov={Project} --cov-fail-under=80

      - name: Type Check
        run: mypy {Project}

      - name: Lint
        run: ruff check {Project}

      - name: Import Boundaries
        run: lint-imports

      - name: Security Scan
        run: bandit -r {Project} -ll
```

### Release Gates

| Gate | Criteria | Owner |
|------|----------|-------|
| Integration tests pass | All tests green | CI |
| Performance regression | < 10% degradation | CI |
| Security review | No new vulnerabilities | Security team |
| Documentation updated | Architecture docs current | Tech writer |
| Changelog updated | Release notes complete | PM |

---

## Reporting

### Daily Health Report

```
{Project} Daily Health Report - 2025-01-17

Availability: 99.97% (target: 99.9%) ✓
Error Rate: 0.03% (target: < 0.1%) ✓
P95 Latency: 387ms (target: < 500ms) ✓
Security Incidents: 0 ✓

Top Issues:
- None

Recommendations:
- System healthy, no action required
```

### Weekly Quality Review

| Metric | This Week | Last Week | Trend |
|--------|-----------|-----------|-------|
| Availability | 99.95% | 99.92% | ↑ |
| Error Rate | 0.04% | 0.05% | ↑ |
| P95 Query Latency | 412ms | 398ms | ↓ |
| Test Coverage | 84.2% | 83.8% | ↑ |
| Open Bugs | 12 | 15 | ↑ |

---

## See Also

- [Quality Tree](ref-quality-tree.md) - Quality attribute hierarchy
- [Quality Scenarios](ref-quality-scenarios.md) - Testable scenarios
- [Observability](../08-crosscutting/con-observability.md) - Monitoring infrastructure
