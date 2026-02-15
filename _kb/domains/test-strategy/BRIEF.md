# Test Strategy Domain

Testing patterns, fixtures, coverage targets, and CI verification.

## Mental Model

Three test layers: unit (fast, no deps), integration (testcontainers for PostgreSQL/Redis), acceptance (end-to-end API). TDD is constitutional (Article II): tests first, then implementation. Coverage target: 80% minimum (PADR-104).

## Invariants

- Unit tests must not touch external systems
- Integration tests use testcontainers (ephemeral containers)
- All tests are tenant-isolated (unique tenant_id per test)
- Story markers (`@pytest.mark.story("S-NNN")`) trace tests to requirements

## Key Patterns

- **Fixtures:** Session-scoped `postgres_container`, function-scoped `event_store_factory`
- **Markers:** `@pytest.mark.integration`, `@pytest.mark.story("S-NNN-NNN-NNN")`
- **Test data:** Factory functions for domain objects
- **Cleanup:** Automatic event store cleanup between tests
- **Async:** `pytest-asyncio` for async test functions

## File Layout

```
tests/
├── unit/{context}/          # Fast, no external deps
├── integration/{context}/   # Testcontainers-based
└── conftest.py              # Shared fixtures
```

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/patterns/PADR-104-testing-strategy.md` | Test architecture decisions |
| `references/con-testing-strategy.md` | Testing overview |
| `references/ref-testing.md` | Test patterns and fixtures |
