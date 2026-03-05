"""Language detection from file extensions.

Module-level constants map file extensions to language names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(LANGUAGE_EXTENSIONS.values())


def detect_language(file_path: str) -> str | None:
    """Detect language from file extension. Returns None if unsupported."""
    suffix = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(suffix)


def as_language_name(lang: str) -> Any:
    """Return *lang* typed as ``Any`` so tslp APIs accept it without a Literal.

    Callers must have already validated that *lang* is in SUPPORTED_LANGUAGES.
    This is a type-only widening cast — no runtime conversion occurs.
    """
    return lang
