"""Domain port interfaces for hexagonal architecture.

Ports define abstract interfaces that the domain layer uses to interact
with external services. Implementations (adapters) live in infrastructure.
"""

from praecepta.foundation.domain.ports.api_key_generator import APIKeyGeneratorPort
from praecepta.foundation.domain.ports.llm_service import LLMServicePort

__all__ = ["APIKeyGeneratorPort", "LLMServicePort"]
