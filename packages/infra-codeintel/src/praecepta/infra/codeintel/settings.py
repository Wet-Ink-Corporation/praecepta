"""Code intelligence configuration using Pydantic settings.

Environment variables use the CODE_INTEL_ prefix.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CodeIntelSettings(BaseSettings):
    """Configuration for the code intelligence subsystem."""

    model_config = SettingsConfigDict(
        env_prefix="CODE_INTEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    repo_root: str = Field(default=".", description="Repository root path")
    languages: list[str] = Field(
        default=["python", "typescript", "javascript"],
        description="Languages to index",
    )
    exclude_patterns: list[str] = Field(
        default=[
            "**/node_modules/**",
            "**/dist/**",
            "**/.venv/**",
            "**/bin/**",
            "**/obj/**",
            "**/__pycache__/**",
        ],
        description="Glob patterns to exclude from indexing",
    )
    embedding_model: str = Field(
        default="jinaai/jina-code-embeddings-0.5b",
        description="HuggingFace model ID for code embeddings",
    )
    embedding_device: str = Field(
        default="cpu",
        description="Device for embedding model (cpu, cuda, mps)",
    )
    embedding_trust_remote_code: bool = Field(
        default=True,
        description=(
            "Allow execution of remote code when loading the embedding model. "
            "Required for Jina models (default True). Set to False only when using "
            "models that do not require it. "
            "WARNING: only disable if you fully trust the model source."
        ),
    )
    embedding_batch_size: int = Field(
        default=64,
        ge=1,
        le=512,
        description="Batch size for embedding computation",
    )
    default_token_budget: int = Field(
        default=4096,
        ge=256,
        le=65536,
        description="Default token budget for context queries",
    )
    watcher_debounce_ms: int = Field(
        default=300,
        ge=50,
        le=5000,
        description="File watcher debounce window in milliseconds",
    )
    pagerank_damping: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="PageRank damping factor",
    )
    max_dependency_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum hops for dependency graph traversal",
    )
    cache_dir: str = Field(
        default=".code-intel",
        description="Directory name for index artifacts (relative to repo root)",
    )
    lancedb_compact_interval_minutes: int = Field(
        default=30,
        ge=5,
        description="Interval for LanceDB compaction and cleanup",
    )

    @field_validator("pagerank_damping")
    @classmethod
    def validate_damping(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            msg = "pagerank_damping must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v


@lru_cache(maxsize=1)
def get_settings() -> CodeIntelSettings:
    """Return cached settings singleton."""
    return CodeIntelSettings()
