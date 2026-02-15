# Design Patterns Reference

## Overview

Reference for dependency injection, specification pattern, and structured concurrency with AnyIO.

## Dependency Injection Container

Simple service container for dependency management:

```python
class Container:
    """Service container for dependency management."""

    def __init__(self):
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, tuple[Callable, bool]] = {}

    def register(self, name: str, service: Any) -> None:
        """Register a singleton service instance."""
        self._singletons[name] = service

    def register_factory(
        self,
        name: str,
        factory: Callable[["Container"], Any],
        singleton: bool = False
    ) -> None:
        """Register a factory function."""
        self._factories[name] = (factory, singleton)

    def get(self, name: str) -> Any:
        """Get service by name."""
        if name in self._singletons:
            return self._singletons[name]

        if name in self._factories:
            factory, singleton = self._factories[name]
            instance = factory(self)
            if singleton:
                self._singletons[name] = instance
            return instance

        raise ServiceNotFound(f"Service '{name}' not registered")
```

**Configuration:**

```python
def configure_container() -> Container:
    container = Container()

    # Event bus (singleton)
    container.register_factory('event_bus', create_event_bus, singleton=True)

    # Repository (per-request)
    container.register_factory('dog_repository', create_dog_repository)

    return container
```

## Specification Pattern

Composable business rules:

```python
class Specification(ABC, Generic[T]):

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        pass

    def __and__(self, other: "Specification[T]") -> "AndSpecification[T]":
        return AndSpecification(self, other)

    def __or__(self, other: "Specification[T]") -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification[T]":
        return NotSpecification(self)

class AndSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return (self.left.is_satisfied_by(candidate) and
                self.right.is_satisfied_by(candidate))
```

**Usage:**

```python
class KnowsTrickSpec(Specification):
    def __init__(self, trick: str):
        self.trick = trick

    def is_satisfied_by(self, dog) -> bool:
        return self.trick in dog.tricks

# Compose specifications
talented_rollers = KnowsTrickSpec("roll over") & HasMinTricksSpec(3)
```

## Structured Concurrency (AnyIO)

```python
import anyio
from anyio import create_task_group, move_on_after
from result import Ok, Err, Result

async def process_events_concurrently(events: list, handler) -> list[Result]:
    results = []

    async with create_task_group() as tg:
        for event in events:
            tg.start_soon(_process_with_timeout, event, handler, results)

    return results

async def _process_with_timeout(event, handler, results, timeout: float = 10.0):
    with move_on_after(timeout) as scope:
        result = await handler(event)
        results.append(Ok(result))

    if scope.cancelled_caught:
        results.append(Err(TimeoutError(f"Event {event.id} timed out")))

async def run_with_shutdown(task, shutdown_event: anyio.Event):
    async with create_task_group() as tg:
        tg.start_soon(task)
        await shutdown_event.wait()
        tg.cancel_scope.cancel()
```

## Pattern Summary

| Pattern | Purpose | Key Benefit |
|---------|---------|-------------|
| **DI Container** | Manage service dependencies | Decoupled configuration |
| **Specification** | Composable business rules | Reusable, testable predicates |
| **Structured Concurrency** | Async task management | Automatic cleanup, cancellation |

## See Also

- [Architecture Layers](con-layers.md) - Where patterns apply
- [Domain Modeling](con-domain-modeling.md) - Domain patterns
