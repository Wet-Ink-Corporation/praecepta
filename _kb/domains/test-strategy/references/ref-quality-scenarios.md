# Quality Scenarios

> Testable scenarios for quality attributes

---

## Overview

Quality scenarios define specific, testable situations for each quality attribute. Each scenario follows the format:

**Source** → **Stimulus** → **Environment** → **Response** → **Response Measure**

---

## Security Scenarios

### S1: Unauthorized Access Attempt

| Element | Description |
|---------|-------------|
| **Source** | Authenticated user |
| **Stimulus** | Query for document they don't have permission to view |
| **Environment** | Normal operation |
| **Response** | Document excluded from results, no indication of existence |
| **Measure** | 0 unauthorized documents returned |

```python
# Test implementation
async def test_unauthorized_access_excluded():
    # User A owns document
    doc_id = await create_document(owner="user_a", content="secret")

    # User B queries
    results = await search(user="user_b", query="secret")

    # Document not in results
    assert doc_id not in [r.id for r in results]
    assert "secret" not in str(results)
```

### S2: Cross-Tenant Isolation

| Element | Description |
|---------|-------------|
| **Source** | Authenticated user from Tenant A |
| **Stimulus** | Query that would match Tenant B data |
| **Environment** | Multi-tenant production |
| **Response** | Only Tenant A data returned |
| **Measure** | 0 cross-tenant data exposure |

```python
async def test_tenant_isolation():
    # Create content in different tenants
    await create_document(tenant="acme", content="quarterly report")
    await create_document(tenant="globex", content="quarterly report")

    # Query as Acme user
    results = await search(
        user="alice@acme.com",
        tenant="acme",
        query="quarterly report"
    )

    # Only Acme content returned
    assert all(r.tenant_id == "acme" for r in results)
```

### S3: ACL Propagation

| Element | Description |
|---------|-------------|
| **Source** | Source system (Confluence) |
| **Stimulus** | Permission change on document |
| **Environment** | Normal operation |
| **Response** | ACLs propagated to all derived content |
| **Measure** | Propagation complete within 5 minutes |

```python
async def test_acl_propagation():
    # Create document and chunks
    doc_id = await ingest_document(
        source="confluence",
        page_id="12345",
        acl=["group:engineering"]
    )

    # Update ACL in source
    await confluence.update_permissions(
        page_id="12345",
        add=["group:marketing"]
    )

    # Trigger sync
    await sync_acls(source="confluence", page_id="12345")

    # Verify chunks have updated ACL
    chunks = await get_chunks(document_id=doc_id)
    for chunk in chunks:
        assert "group:marketing" in chunk.acl_principals
```

### S4: Audit Trail Completeness

| Element | Description |
|---------|-------------|
| **Source** | Security auditor |
| **Stimulus** | Request access history for specific document |
| **Environment** | Normal operation |
| **Response** | Complete list of access events |
| **Measure** | 100% of access events captured |

```python
async def test_audit_trail():
    doc_id = await create_document(content="confidential")

    # Multiple access patterns
    await search(user="alice", query="confidential")
    await get_document(user="bob", id=doc_id)
    await search(user="charlie", query="confidential")

    # Retrieve audit log
    audit_events = await get_audit_log(resource_id=doc_id)

    # All access recorded
    assert len(audit_events) >= 3
    users = [e.user_id for e in audit_events]
    assert "alice" in users
    assert "bob" in users
    assert "charlie" in users
```

---

## Reliability Scenarios

### R1: Database Failover

| Element | Description |
|---------|-------------|
| **Source** | Database infrastructure |
| **Stimulus** | Primary database node failure |
| **Environment** | Production under load |
| **Response** | Automatic failover to replica |
| **Measure** | Service recovery < 30 seconds |

```python
async def test_database_failover():
    # Start continuous queries
    query_task = asyncio.create_task(continuous_queries())

    # Simulate primary failure
    await kill_primary_database()

    # Wait for recovery
    await asyncio.sleep(30)

    # Verify queries resume
    recent_results = await query_task.get_recent()
    assert recent_results.success_rate > 0.95
```

### R2: Event Store Replay

| Element | Description |
|---------|-------------|
| **Source** | Operations team |
| **Stimulus** | Request to rebuild projection from events |
| **Environment** | Maintenance window |
| **Response** | Projection rebuilt with correct state |
| **Measure** | State matches expected within 15 minutes |

```python
async def test_projection_rebuild():
    # Create known state
    block = await create_block(title="Test Block")
    await add_entry(block.id, content_id=uuid4())
    await add_entry(block.id, content_id=uuid4())

    # Wipe projection
    await clear_projection("block_summary")

    # Rebuild
    await rebuild_projection("block_summary")

    # Verify state
    summary = await get_block_summary(block.id)
    assert summary.title == "Test Block"
    assert summary.entry_count == 2
```

### R3: Idempotent Retry

| Element | Description |
|---------|-------------|
| **Source** | Ingestion worker |
| **Stimulus** | Network failure during document processing |
| **Environment** | Normal operation |
| **Response** | Retry succeeds, no duplicate content |
| **Measure** | Exactly-once processing |

```python
async def test_idempotent_retry():
    # Start ingestion
    job_id = await start_ingestion(document_url="https://...")

    # Simulate failure mid-processing
    await simulate_network_failure()

    # Retry
    await retry_ingestion(job_id)

    # Verify no duplicates
    chunks = await get_all_chunks()
    unique_ids = set(c.id for c in chunks)
    assert len(chunks) == len(unique_ids)
```

### R4: Concurrent Update Handling

| Element | Description |
|---------|-------------|
| **Source** | Two concurrent users |
| **Stimulus** | Simultaneous updates to same block |
| **Environment** | Normal operation |
| **Response** | One succeeds, one gets concurrency error |
| **Measure** | No lost updates, clear error message |

```python
async def test_concurrent_updates():
    block = await create_block(title="Original")

    # Simulate concurrent updates
    async def update_1():
        await update_block(block.id, title="Update 1")

    async def update_2():
        await asyncio.sleep(0.01)  # Slight delay
        return await update_block(block.id, title="Update 2")

    results = await asyncio.gather(
        update_1(),
        update_2(),
        return_exceptions=True
    )

    # One succeeds, one fails with concurrency error
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, ConcurrencyError)]

    assert len(successes) == 1
    assert len(failures) == 1
```

---

## Performance Scenarios

### P1: Query Latency

| Element | Description |
|---------|-------------|
| **Source** | AI agent |
| **Stimulus** | Semantic search query |
| **Environment** | Normal load |
| **Response** | Top 10 results returned |
| **Measure** | P95 latency < 500ms |

```python
async def test_query_latency():
    latencies = []

    for _ in range(100):
        start = time.perf_counter()
        await search(query="machine learning algorithms", limit=10)
        latencies.append((time.perf_counter() - start) * 1000)

    p95 = sorted(latencies)[94]
    assert p95 < 500, f"P95 latency {p95}ms exceeds 500ms target"
```

### P2: Security Trimming Overhead

| Element | Description |
|---------|-------------|
| **Source** | Query service |
| **Stimulus** | Query requiring security trimming |
| **Environment** | Normal operation |
| **Response** | Results filtered correctly |
| **Measure** | < 50ms additional latency |

```python
async def test_security_trimming_overhead():
    # Query without security (admin bypass)
    start = time.perf_counter()
    await search(query="test", bypass_security=True)
    no_security_time = time.perf_counter() - start

    # Query with security
    start = time.perf_counter()
    await search(query="test", user="alice")
    with_security_time = time.perf_counter() - start

    overhead = (with_security_time - no_security_time) * 1000
    assert overhead < 50, f"Security overhead {overhead}ms exceeds 50ms"
```

### P3: Throughput Under Load

| Element | Description |
|---------|-------------|
| **Source** | Load test |
| **Stimulus** | 1000 concurrent queries per second |
| **Environment** | Production configuration |
| **Response** | All queries processed |
| **Measure** | Error rate < 1%, latency stable |

```python
async def test_throughput():
    async def single_query():
        return await search(query="test query")

    # Run 1000 queries in 1 second
    tasks = [single_query() for _ in range(1000)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    error_rate = len(errors) / len(results)

    assert error_rate < 0.01, f"Error rate {error_rate:.2%} exceeds 1%"
```

### P4: Ingestion Throughput

| Element | Description |
|---------|-------------|
| **Source** | Ingestion service |
| **Stimulus** | Batch of 100 documents |
| **Environment** | Normal operation |
| **Response** | All documents indexed |
| **Measure** | > 100 documents/minute |

```python
async def test_ingestion_throughput():
    documents = [generate_test_document() for _ in range(100)]

    start = time.time()
    await ingest_batch(documents)
    elapsed = time.time() - start

    docs_per_minute = 100 / elapsed * 60
    assert docs_per_minute > 100, f"Throughput {docs_per_minute:.1f}/min below target"
```

---

## Maintainability Scenarios

### M1: New Connector Development

| Element | Description |
|---------|-------------|
| **Source** | Developer |
| **Stimulus** | Requirement to add GitHub connector |
| **Environment** | Development |
| **Response** | Connector implemented and tested |
| **Measure** | Development time < 1 week |

```
Acceptance Criteria:
1. Implement SourceConnector interface
2. Handle authentication (OAuth)
3. Map GitHub permissions to principals
4. Parse markdown content
5. Unit and integration tests pass
6. No changes to core ingestion logic
```

### M2: Context Boundary Enforcement

| Element | Description |
|---------|-------------|
| **Source** | CI/CD pipeline |
| **Stimulus** | Import across context boundaries |
| **Environment** | Build |
| **Response** | Build fails with clear error |
| **Measure** | 0 boundary violations in main |

```python
# import-linter configuration
[tool.importlinter]
root_package = "{Project}"

[[tool.importlinter.contracts]]
name = "Bounded contexts are independent"
type = "independence"
modules = [
    "{Project}.memory",
    "{Project}.ingestion",
    "{Project}.query",
    "{Project}.security",
    "{Project}.graph",
    "{Project}.curation"
]
```

### M3: Production Issue Diagnosis

| Element | Description |
|---------|-------------|
| **Source** | On-call engineer |
| **Stimulus** | User reports slow query |
| **Environment** | Production |
| **Response** | Root cause identified |
| **Measure** | Diagnosis time < 30 minutes |

```
Required Observability:
1. Query trace with timing for each stage
2. Database query execution plans
3. External service latencies
4. Error details with stack traces
5. Correlation across services
```

### M4: Developer Onboarding

| Element | Description |
|---------|-------------|
| **Source** | New team member |
| **Stimulus** | First feature development task |
| **Environment** | Development |
| **Response** | Feature implemented correctly |
| **Measure** | Productive within 2 weeks |

```
Onboarding Support:
1. Architecture documentation (this bible)
2. Local development setup script
3. Example vertical slice to follow
4. Code review from experienced team member
5. Testing patterns documented
```

---

## Scenario Matrix

| ID | Quality | Scenario | Test Type | Priority |
|----|---------|----------|-----------|----------|
| S1 | Security | Unauthorized access | Integration | Critical |
| S2 | Security | Tenant isolation | E2E | Critical |
| S3 | Security | ACL propagation | Integration | High |
| S4 | Security | Audit completeness | Integration | High |
| R1 | Reliability | Database failover | Infrastructure | High |
| R2 | Reliability | Projection rebuild | Integration | Medium |
| R3 | Reliability | Idempotent retry | Integration | High |
| R4 | Reliability | Concurrent updates | Unit | Medium |
| P1 | Performance | Query latency | Load | High |
| P2 | Performance | Security overhead | Performance | Medium |
| P3 | Performance | Throughput | Load | Medium |
| P4 | Performance | Ingestion rate | Performance | Medium |
| M1 | Maintainability | New connector | Manual | Low |
| M2 | Maintainability | Boundary enforcement | CI | High |
| M3 | Maintainability | Issue diagnosis | Manual | Medium |
| M4 | Maintainability | Onboarding | Manual | Low |

---

## See Also

- [Quality Tree](ref-quality-tree.md) - Quality attribute hierarchy
- [Quality Measures](con-quality-measures.md) - Measurement approach
- [Testing Strategy](con-testing-strategy.md) - Test implementation
