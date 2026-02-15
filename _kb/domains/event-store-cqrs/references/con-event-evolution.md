# Event Schema Evolution

## Overview

Three strategies for evolving event schemas while maintaining backward compatibility with stored events.

## Evolution Strategies

| Strategy | When to Use | Example |
|----------|-------------|---------|
| **Versioned Events** | Major schema changes | `DogRegisteredV2` alongside `DogRegistered` |
| **Upcasting** | Many versions (3+) | Chain: V1 -> V2 -> V3 on read |
| **Weak Schema** | Unknown future changes | Accept missing/extra fields gracefully |

## Versioned Events (Simple Approach)

When event schema changes:

1. Add new fields with defaults (backward compatible)
2. Never remove fields (mark deprecated)
3. For breaking changes, create new event type

```python
@dataclass(frozen=True)
class DogRegisteredV2(DogSchoolEvent):
    """V2 adds breed field."""
    name: str
    owner_id: UUID
    breed: str = "unknown"  # Default for old events
```

## Upcasting Pipeline

For multiple versions, chain upcasters to transform old events on read:

```python
class EventUpcaster(ABC):
    """Convert events from old schema to new schema."""

    @property
    @abstractmethod
    def from_version(self) -> int:
        pass

    @property
    @abstractmethod
    def to_version(self) -> int:
        pass

    @abstractmethod
    def upcast(self, event: Dict[str, Any]) -> Dict[str, Any]:
        pass

class DogRegisteredV1toV2(EventUpcaster):
    """Add breed field to V1 events."""

    @property
    def from_version(self) -> int:
        return 1

    @property
    def to_version(self) -> int:
        return 2

    def upcast(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **event,
            'version': 2,
            'breed': 'unknown',  # Default for legacy events
        }
```

**Registry for chaining:**

```python
class EventUpcasterRegistry:
    def upcast_to_latest(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Upcast event through all versions to latest."""
        current = event.copy()

        while event_type in self._upcasters:
            version = current.get('version', 1)
            if version not in self._upcasters[event_type]:
                break
            upcaster = self._upcasters[event_type][version]
            current = upcaster.upcast(current)

        return current
```

## Weak Schema

Accept unknown fields gracefully for forward compatibility:

```python
@dataclass
class FlexibleEvent:
    known_field: str
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "FlexibleEvent":
        known = data.pop("known_field")
        return cls(known_field=known, extra=data)
```

## Key Points

- Add new fields with defaults for backward compatibility
- Never remove fields from events (mark deprecated instead)
- Use upcasting for complex multi-version evolution
- Events are immutable; schema changes require new versions

## Prerequisites

- [Domain Modeling](con-domain-modeling.md) - Event fundamentals

## Related

- [ACL](con-acl.md) - Translating external events
