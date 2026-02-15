"""Port interface for LLM completion services.

This module defines the LLMServicePort protocol for abstracting LLM interactions,
enabling domain logic to use LLM capabilities without coupling to specific providers
or frameworks.

Example:
    >>> from praecepta.foundation.domain.ports import LLMServicePort
    >>> def extract_entities(llm: LLMServicePort, text: str) -> list[str]:
    ...     return llm.complete(f"Extract entities from: {text}")
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMServicePort(Protocol):
    """Port for LLM completion services.

    This protocol defines the contract for LLM interactions. Implementations
    may use any LLM client library.

    The protocol is runtime_checkable to enable isinstance() verification
    in tests and dependency injection validation.

    Example:
        >>> # Domain code depends only on the port
        >>> def process_with_llm(llm: LLMServicePort, prompt: str) -> str:
        ...     return llm.complete(prompt)
    """

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate unstructured text completion.

        Args:
            prompt: The prompt text to send to the LLM.
            model: Optional model identifier. If None, adapter uses default.
            temperature: Sampling temperature (0.0-2.0). Defaults to 0.7.

        Returns:
            The generated text response from the LLM.

        Example:
            >>> response = llm.complete("Summarize this document: ...")
            >>> print(response)
            'The document discusses...'
        """
        ...

    def complete_structured(
        self,
        prompt: str,
        response_type: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> T:
        """Generate structured completion validated against Pydantic model.

        Uses the LLM to generate a response that conforms to the specified
        Pydantic model schema. The adapter is responsible for ensuring the
        response is properly validated.

        Args:
            prompt: The prompt text to send to the LLM.
            response_type: Pydantic model class defining expected response structure.
            model: Optional model identifier. If None, adapter uses default.
            temperature: Sampling temperature (0.0-2.0). Defaults to 0.7.

        Returns:
            Instance of response_type populated with LLM-generated values.

        Raises:
            Adapter-specific exceptions for validation failures or LLM errors.

        Example:
            >>> class EntityList(BaseModel):
            ...     entities: list[str]
            >>> result = llm.complete_structured(
            ...     "Extract names from: John met Mary",
            ...     EntityList,
            ... )
            >>> result.entities
            ['John', 'Mary']
        """
        ...
