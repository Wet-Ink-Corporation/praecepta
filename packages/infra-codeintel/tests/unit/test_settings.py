"""Unit tests for code intelligence settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from praecepta.infra.codeintel.settings import CodeIntelSettings, get_settings


@pytest.mark.unit
class TestCodeIntelSettings:
    def test_defaults(self) -> None:
        settings = CodeIntelSettings()
        assert settings.repo_root == "."
        assert "python" in settings.languages
        assert settings.embedding_device == "cpu"
        assert settings.embedding_batch_size == 64
        assert settings.default_token_budget == 4096
        assert settings.watcher_debounce_ms == 300
        assert settings.pagerank_damping == 0.85
        assert settings.max_dependency_depth == 3
        assert settings.cache_dir == ".code-intel"
        assert settings.lancedb_compact_interval_minutes == 30

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODE_INTEL_REPO_ROOT", "/my/repo")
        monkeypatch.setenv("CODE_INTEL_EMBEDDING_DEVICE", "cuda")
        monkeypatch.setenv("CODE_INTEL_DEFAULT_TOKEN_BUDGET", "8192")
        settings = CodeIntelSettings()
        assert settings.repo_root == "/my/repo"
        assert settings.embedding_device == "cuda"
        assert settings.default_token_budget == 8192

    def test_pagerank_damping_validation(self) -> None:
        with pytest.raises(ValidationError):
            CodeIntelSettings(pagerank_damping=1.5)

    def test_embedding_batch_size_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CodeIntelSettings(embedding_batch_size=0)
        with pytest.raises(ValidationError):
            CodeIntelSettings(embedding_batch_size=1000)

    def test_token_budget_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CodeIntelSettings(default_token_budget=100)

    def test_exclude_patterns_default(self) -> None:
        settings = CodeIntelSettings()
        assert "**/node_modules/**" in settings.exclude_patterns
        assert "**/__pycache__/**" in settings.exclude_patterns

    def test_embedding_trust_remote_code_default(self) -> None:
        """New setting should default to True for Jina model compatibility (M-7)."""
        settings = CodeIntelSettings()
        assert settings.embedding_trust_remote_code is True

    def test_embedding_trust_remote_code_configurable(self) -> None:
        settings = CodeIntelSettings(embedding_trust_remote_code=False)
        assert settings.embedding_trust_remote_code is False


@pytest.mark.unit
class TestGetSettings:
    def test_returns_instance(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, CodeIntelSettings)

    def test_caches_result(self) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
