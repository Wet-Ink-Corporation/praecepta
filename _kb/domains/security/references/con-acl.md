# Anti-Corruption Layer (ACL)

## Overview

When consuming events from other bounded contexts, use an Anti-Corruption Layer to translate external events into internal domain concepts. This isolates your domain from external changes.

## Why ACL?

External domains evolve independently. Without an ACL:

- Your domain couples to external event schemas
- Changes in other domains break your code
- You process fields you don't need
- External concepts leak into your ubiquitous language

## ACL Structure

```
Product Domain (external)
    | publishes
    ProductCreated { product_id, name, price, sku, category, supplier_id, ... }
    |
Order Domain ACL (translator)
    | isolates & translates
    ProductAvailableForOrdering { product_id, name, price }  (only what Order needs)
    |
Order Domain (internal)
    | processes in own terms
```

## Implementation

**Internal Domain Events:**

```python
@dataclass(frozen=True)
class ProductAvailableForOrdering:
    """Order domain's view of a product."""
    product_id: str
    product_name: str
    current_price: Decimal

@dataclass(frozen=True)
class ProductNoLongerAvailable:
    """Order domain event - product unavailable."""
    product_id: str
    reason: str
```

**Translator:**

```python
class ProductEventTranslator:
    """Translates Product domain events to Order domain events."""

    @staticmethod
    def translate(external_event: dict) -> Optional[object]:
        """Translate external event to internal domain event.

        Returns None for unknown events (forward compatibility).
        """
        event_type = external_event.get('event_type', '')

        if event_type == 'product.created':
            return ProductAvailableForOrdering(
                product_id=external_event['product_id'],
                product_name=external_event['name'],
                current_price=Decimal(str(external_event['price'])),
            )

        elif event_type == 'product.archived':
            return ProductNoLongerAvailable(
                product_id=external_event['product_id'],
                reason=external_event.get('reason', 'Product archived'),
            )

        # Ignore unknown events (forward compatibility)
        return None
```

**Usage:**

```python
class OrderService:
    def __init__(self, translator: ProductEventTranslator):
        self.translator = translator

    async def on_product_event(self, raw_event: dict) -> None:
        # Translate through ACL (isolates us from Product changes)
        order_event = self.translator.translate(raw_event)

        if order_event is None:
            return  # Ignore events we don't care about

        # Process in Order domain terms
        if isinstance(order_event, ProductAvailableForOrdering):
            await self._on_product_available(order_event)
```

## Key Points

- ACL translates external events to internal domain concepts
- Returns `None` for unknown events (forward compatibility)
- Only extracts fields your domain needs
- Isolates your domain from external schema changes

## Prerequisites

- [Domain Modeling](con-domain-modeling.md) - Event patterns

## Related

- [Event Distribution](con-event-distribution.md) - Cross-application events
- [Event Evolution](con-event-evolution.md) - Schema versioning
