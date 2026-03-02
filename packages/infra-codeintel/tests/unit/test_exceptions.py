"""Unit tests for code intelligence exceptions."""

from __future__ import annotations

import pytest

from praecepta.foundation.domain.exceptions import DomainError
from praecepta.infra.codeintel.exceptions import (
    BudgetExceededError,
    CodeIntelError,
    EmbeddingError,
    IndexError,
    ParseError,
    UnsupportedLanguageError,
)


@pytest.mark.unit
class TestCodeIntelError:
    def test_inherits_domain_error(self) -> None:
        err = CodeIntelError("something failed")
        assert isinstance(err, DomainError)

    def test_error_code(self) -> None:
        err = CodeIntelError("fail")
        assert err.error_code == "CODE_INTEL_ERROR"


@pytest.mark.unit
class TestParseError:
    def test_message_format(self) -> None:
        err = ParseError(file_path="src/main.py", reason="syntax error")
        assert "src/main.py" in str(err)
        assert "syntax error" in str(err)

    def test_context_includes_fields(self) -> None:
        err = ParseError(file_path="a.py", reason="bad", line=42)
        assert err.context["file_path"] == "a.py"
        assert err.context["reason"] == "bad"
        assert err.context["line"] == 42

    def test_error_code(self) -> None:
        err = ParseError("a.py", "bad")
        assert err.error_code == "CODE_INTEL_PARSE_ERROR"

    def test_inherits_codeintel_error(self) -> None:
        err = ParseError("a.py", "bad")
        assert isinstance(err, CodeIntelError)


@pytest.mark.unit
class TestUnsupportedLanguageError:
    def test_message(self) -> None:
        err = UnsupportedLanguageError("cobol")
        assert "cobol" in str(err)

    def test_context_with_file_path(self) -> None:
        err = UnsupportedLanguageError("cobol", file_path="main.cob")
        assert err.context["language"] == "cobol"
        assert err.context["file_path"] == "main.cob"

    def test_context_without_file_path(self) -> None:
        err = UnsupportedLanguageError("cobol")
        assert "file_path" not in err.context

    def test_error_code(self) -> None:
        err = UnsupportedLanguageError("cobol")
        assert err.error_code == "CODE_INTEL_UNSUPPORTED_LANGUAGE"


@pytest.mark.unit
class TestIndexError:
    def test_error_code(self) -> None:
        err = IndexError("index failed")
        assert err.error_code == "CODE_INTEL_INDEX_ERROR"

    def test_inherits_codeintel_error(self) -> None:
        err = IndexError("fail")
        assert isinstance(err, CodeIntelError)


@pytest.mark.unit
class TestEmbeddingError:
    def test_error_code(self) -> None:
        err = EmbeddingError("model load failed")
        assert err.error_code == "CODE_INTEL_EMBEDDING_ERROR"


@pytest.mark.unit
class TestBudgetExceededError:
    def test_message_format(self) -> None:
        err = BudgetExceededError(budget=1000, min_required=2000)
        assert "1000" in str(err)
        assert "2000" in str(err)

    def test_context(self) -> None:
        err = BudgetExceededError(budget=1000, min_required=2000)
        assert err.context["budget"] == 1000
        assert err.context["min_required"] == 2000

    def test_attributes(self) -> None:
        err = BudgetExceededError(budget=500, min_required=1000)
        assert err.budget == 500
        assert err.min_required == 1000

    def test_error_code(self) -> None:
        err = BudgetExceededError(budget=1, min_required=2)
        assert err.error_code == "CODE_INTEL_BUDGET_EXCEEDED"
