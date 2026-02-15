# Testing Strategy Reference

## Overview

Testing strategy with coverage targets, test pyramid, and patterns for testing event-sourced vertical slices.

## Coverage Targets

| Layer | Target |
|-------|--------|
| Domain | 90% |
| Application | 85% |
| Infrastructure | 80% |
| API | 70% |
| **Overall** | **85%** |

## Test Pyramid

```
         /\
        /  \         E2E Tests (5%)
       /----\
      /      \
     /--------\      Integration Tests (25%)
    /          \
   /------------\
  /              \   Unit Tests (70%)
 /----------------\
```

## Testing Vertical Slices

Command handlers are pure functions, making them trivially testable:

```python
# src/dog_school/slices/register_dog/test_cmd.py
from unittest import TestCase
from uuid import uuid4

from dog_school._shared.events import DogRegistered
from dog_school._shared.exceptions import DogAlreadyRegisteredError
from .cmd import RegisterDog

class TestRegisterDogHandler(TestCase):

    def test_register_new_dog(self):
        dog_id = uuid4()
        cmd = RegisterDog(name="Fido", owner_id=uuid4(), dog_id=dog_id)

        new_events = cmd.handle(())

        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], DogRegistered)
        self.assertEqual(new_events[0].name, "Fido")

    def test_cannot_register_twice(self):
        dog_id = uuid4()
        existing = (DogRegistered(
            originator_id=dog_id,
            originator_version=1,
            name="Fido",
            owner_id=uuid4(),
        ),)

        cmd = RegisterDog(name="Fido", owner_id=uuid4(), dog_id=dog_id)

        with self.assertRaises(DogAlreadyRegisteredError):
            cmd.handle(existing)
```

## Fixtures

```python
# tests/conftest.py
import os
import pytest

@pytest.fixture
def in_memory_app():
    os.environ["PERSISTENCE_MODULE"] = "eventsourcing.popo"
    from dog_school._shared.common import reset_app, get_app
    reset_app()
    return get_app()

@pytest.fixture
def postgres_app():
    os.environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"
    os.environ["POSTGRES_DBNAME"] = "test_events"
    from dog_school._shared.common import reset_app, get_app
    reset_app()
    yield get_app()
```

## Test Patterns

| Pattern | When to Use |
|---------|-------------|
| **Pure handler tests** | Testing `cmd.handle(events)` without infrastructure |
| **In-memory store** | Fast integration tests with `eventsourcing.popo` |
| **PostgreSQL tests** | Full integration with real database |
| **API tests** | FastAPI TestClient for endpoint testing |

## Pure Handler Test Benefits

- No mocking required
- Runs in milliseconds
- Deterministic results
- Easy to reason about

The pure function signature `handle(events) -> new_events` means you:

1. Create past events directly
2. Call the handler
3. Assert on returned events

## Key Points

- 85% overall coverage target
- 70% unit tests, 25% integration, 5% E2E
- Pure handlers enable fast, mockless unit tests
- In-memory store for integration tests
- Fixtures swap persistence modules

## See Also

- [Domain Modeling](con-domain-modeling.md) - How handlers work
- [Package Structure](ref-package-structure.md) - Where tests live
