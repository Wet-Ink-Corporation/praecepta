"""Code intelligence exception hierarchy.

All exceptions extend DomainError and include structured error codes
and context dicts for consistent error handling.
"""

from __future__ import annotations

from typing import Any

from praecepta.foundation.domain.exceptions import DomainError


class CodeIntelError(DomainError):
    """Base error for all code intelligence operations."""

    error_code: str = "CODE_INTEL_ERROR"


class ParseError(CodeIntelError):
    """Tree-sitter parsing or tag extraction failed."""

    error_code: str = "CODE_INTEL_PARSE_ERROR"

    def __init__(self, file_path: str, reason: str, **context: Any) -> None:
        self.file_path = file_path
        self.reason = reason
        message = f"Failed to parse '{file_path}': {reason}"
        super().__init__(message, {"file_path": file_path, "reason": reason, **context})


class UnsupportedLanguageError(CodeIntelError):
    """File language is not supported by any loaded .scm query."""

    error_code: str = "CODE_INTEL_UNSUPPORTED_LANGUAGE"

    def __init__(self, language: str, file_path: str | None = None, **context: Any) -> None:
        self.language = language
        message = f"Unsupported language: '{language}'"
        ctx: dict[str, Any] = {"language": language, **context}
        if file_path:
            ctx["file_path"] = file_path
        super().__init__(message, ctx)


class IndexError(CodeIntelError):
    """Structural or semantic index operation failed."""

    error_code: str = "CODE_INTEL_INDEX_ERROR"


class EmbeddingError(CodeIntelError):
    """Embedding model loading or inference failed."""

    error_code: str = "CODE_INTEL_EMBEDDING_ERROR"


class BudgetExceededError(CodeIntelError):
    """Query cannot fit any results within the token budget."""

    error_code: str = "CODE_INTEL_BUDGET_EXCEEDED"

    def __init__(self, budget: int, min_required: int, **context: Any) -> None:
        self.budget = budget
        self.min_required = min_required
        message = f"Token budget {budget} too small (minimum {min_required} required)"
        super().__init__(message, {"budget": budget, "min_required": min_required, **context})
