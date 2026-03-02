# Code Intelligence Package — Architecture Specification

> Maps the [design spec](./code-intelligence-design-spec.md) to a Praecepta workspace package at `packages/infra-codeintel/` under `praecepta.infra.codeintel`.

---

## 1. Package Identity

| Attribute | Value |
|-----------|-------|
| Package name | `praecepta-infra-codeintel` |
| Namespace | `praecepta.infra.codeintel` |
| Layer | 1 — Infrastructure |
| Python | `>=3.12` |
| Build backend | hatchling |
| Version | `2.0.1` (monorepo-shared, managed by commitizen) |

---

## 2. Package Layout

```
packages/infra-codeintel/
├── pyproject.toml
├── src/
│   └── praecepta/                          # NO __init__.py (PEP 420)
│       └── infra/                          # NO __init__.py (PEP 420)
│           └── codeintel/
│               ├── __init__.py             # Leaf package — public API exports
│               ├── py.typed                # PEP 561 marker
│               │
│               ├── settings.py             # CodeIntelSettings (Pydantic)
│               ├── exceptions.py           # CodeIntelError hierarchy
│               ├── types.py                # Value objects: Tag, SymbolSignature, etc.
│               ├── protocols.py            # All protocol definitions
│               │
│               ├── parser/
│               │   ├── __init__.py
│               │   ├── cst_parser.py       # Tree-sitter CST parsing
│               │   ├── tag_extractor.py    # .scm query runner
│               │   ├── language_registry.py# Extension → language mapping
│               │   └── queries/            # Per-language .scm files
│               │       ├── python.scm
│               │       ├── typescript.scm
│               │       └── javascript.scm
│               │
│               ├── extraction/
│               │   ├── __init__.py
│               │   └── semantic_extractor.py  # Tag → SymbolSignature enrichment
│               │
│               ├── index/
│               │   ├── __init__.py
│               │   ├── structural_index.py    # NetworkX DiGraph + PageRank
│               │   └── semantic_index.py      # LanceDB + Jina embeddings
│               │
│               ├── assembly/
│               │   ├── __init__.py
│               │   ├── context_assembler.py   # Ranking fusion + budget packing
│               │   ├── schemas.py             # ContextQuery, ContextResponse, CodeChunk
│               │   └── renderer.py            # XML context string rendering
│               │
│               ├── watcher/
│               │   ├── __init__.py
│               │   └── file_watcher.py        # watchdog integration
│               │
│               ├── surface/
│               │   ├── __init__.py
│               │   ├── mcp_tools.py           # 5 MCP tool definitions
│               │   └── cli.py                 # serve / index / stats commands
│               │
│               └── lifespan.py                # LifespanContribution for app startup
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_settings.py
    │   ├── test_language_registry.py
    │   ├── test_tag_extractor.py
    │   ├── test_semantic_extractor.py
    │   ├── test_structural_index.py
    │   ├── test_ranking_fusion.py
    │   ├── test_token_packing.py
    │   └── test_renderer.py
    ├── integration/
    │   ├── __init__.py
    │   ├── test_cst_parser.py
    │   ├── test_semantic_index.py
    │   ├── test_end_to_end.py
    │   └── test_file_watcher.py
    └── fixtures/
        └── sample_repo/
            ├── main.py
            ├── auth/
            │   ├── service.py
            │   └── types.py
            └── utils.py
```

---

## 3. Internal Module Dependency Graph

Dependencies flow top-to-bottom. No cycles.

```
surface/
  ├── mcp_tools.py ──────────► assembly/context_assembler.py
  └── cli.py ────────────────► assembly/context_assembler.py
                                    │
                        ┌───────────┼───────────┐
                        ▼           ▼           ▼
              assembly/         index/        index/
              schemas.py    structural_index  semantic_index
              renderer.py        │                │
                                 │                │
                        ┌────────┘                │
                        ▼                         ▼
              extraction/                   extraction/
              semantic_extractor.py          semantic_extractor.py
                        │                         │
                        ▼                         ▼
                   parser/                   parser/
               cst_parser.py             tag_extractor.py
               tag_extractor.py
                        │
                        ▼
              parser/language_registry.py
              parser/queries/*.scm

  watcher/file_watcher.py ──► parser/cst_parser.py
                              extraction/semantic_extractor.py
                              index/structural_index.py
                              index/semantic_index.py

  lifespan.py ──► index/structural_index.py
                  index/semantic_index.py
                  watcher/file_watcher.py

  settings.py ◄── (consumed by all modules via get_settings())
  types.py    ◄── (consumed by all modules)
  protocols.py ◄── (consumed by all modules for type annotations)
  exceptions.py ◄── (consumed by all modules)
```

---

## 4. Protocol Definitions

Six protocols, all `@runtime_checkable`, following the pattern in `praecepta.foundation.domain.ports.llm_service`.

### 4.1 CSTParser

```python
@runtime_checkable
class CSTParser(Protocol):
    """Parse source files into concrete syntax trees with tag extraction."""

    def parse_file(self, file_path: Path) -> ParseResult: ...
    def parse_file_incremental(self, file_path: Path, old_tree: Tree) -> ParseResult: ...
    def extract_tags(self, file_path: Path) -> list[Tag]: ...
    def get_supported_languages(self) -> list[str]: ...
```

### 4.2 SemanticExtractor

```python
@runtime_checkable
class SemanticExtractor(Protocol):
    """Transform raw tags into enriched SymbolSignature objects."""

    def extract_symbols(
        self, file_path: Path, tags: list[Tag], tree: Tree
    ) -> list[SymbolSignature]: ...

    def extract_relationships(
        self, file_path: Path, tags: list[Tag]
    ) -> list[SymbolRelationship]: ...
```

### 4.3 StructuralIndex

```python
@runtime_checkable
class StructuralIndex(Protocol):
    """Directed graph of files/symbols ranked by PageRank."""

    def build(self, all_tags: dict[Path, list[Tag]]) -> None: ...
    def update_file(self, file_path: Path, new_tags: list[Tag]) -> None: ...
    def remove_file(self, file_path: Path) -> None: ...
    def get_ranked_symbols(
        self,
        personalization: dict[str, float] | None = None,
        top_k: int = 50,
    ) -> list[tuple[str, float]]: ...
    def get_dependencies(
        self,
        qualified_name: str,
        direction: Literal["callers", "callees", "both"] = "both",
        depth: int = 1,
    ) -> list[tuple[str, str]]: ...
    def get_repo_summary(self) -> RepoSummary: ...
```

### 4.4 SemanticIndex

```python
@runtime_checkable
class SemanticIndex(Protocol):
    """Vector store for symbol embeddings with semantic search."""

    async def upsert_symbols(self, symbols: list[SymbolSignature]) -> int: ...
    async def remove_symbols(self, qualified_names: list[str]) -> int: ...
    async def search(
        self,
        query_text: str,
        query_type: Literal["nl2code", "code2code", "techqa"] = "nl2code",
        top_k: int = 20,
        filters: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]: ...
    async def search_by_name(self, symbol_name: str, top_k: int = 10) -> list[str]: ...
```

### 4.5 ContextAssembler

```python
@runtime_checkable
class ContextAssembler(Protocol):
    """Agent-facing service: fuses structural + semantic retrieval into
    ranked, token-budgeted responses."""

    async def query(self, query: ContextQuery) -> ContextResponse: ...
    async def get_symbol(self, qualified_name: str) -> CodeChunk | None: ...
    async def get_dependencies(
        self,
        qualified_name: str,
        depth: int = 1,
        direction: Literal["callers", "callees", "both"] = "both",
    ) -> list[CodeChunk]: ...
    async def get_repo_summary(self) -> RepoSummary: ...
    async def refresh_index(self, file_paths: list[Path] | None = None) -> IndexStats: ...
```

### 4.6 FileWatcher

```python
@runtime_checkable
class FileWatcher(Protocol):
    """Detect source file changes and trigger incremental re-indexing."""

    def start(
        self, repo_root: Path, on_change: Callable[[list[FileEvent]], Awaitable[None]]
    ) -> None: ...
    def stop(self) -> None: ...
```

---

## 5. Value Objects & Data Types

Defined in `types.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, NamedTuple


class Tag(NamedTuple):
    """A structural tag extracted from source code via tree-sitter .scm queries."""
    rel_fname: str
    fname: str
    line: int
    name: str
    kind: Literal["definition", "reference"]


@dataclass(frozen=True)
class FileEvent:
    path: Path
    event_type: Literal["created", "modified", "deleted"]
    timestamp: datetime


@dataclass(frozen=True)
class ParseResult:
    tree: object  # tree_sitter.Tree
    tags: list[Tag]
    language: str
    parse_duration_ms: float


@dataclass
class SymbolSignature:
    qualified_name: str
    name: str
    kind: str  # function, class, method, etc.
    language: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: str | None
    parent_symbol: str | None
    embedding_text: str
    token_count_estimate: int
    last_modified: datetime


@dataclass(frozen=True)
class SymbolRelationship:
    source: str
    target: str
    kind: str  # calls, imports, inherits, implements, decorates


class QueryIntent(str, Enum):
    UNDERSTAND = "understand"
    MODIFY = "modify"
    NAVIGATE = "navigate"
    GENERATE = "generate"


@dataclass
class IndexStats:
    files_indexed: int
    symbols_indexed: int
    duration_ms: float
    languages: dict[str, int]
```

Response schemas (`ContextQuery`, `ContextResponse`, `CodeChunk`, `SourceLocation`, `RepoSummary`) are defined in `assembly/schemas.py` per the design spec section 3.6.1–3.6.2. These are dataclasses, not Pydantic models, to avoid unnecessary validation overhead on the hot path.

---

## 6. Configuration Schema

Follows the `EventSourcingSettings` pattern (PADR-106). Defined in `settings.py`.

```python
from __future__ import annotations
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CodeIntelSettings(BaseSettings):
    """Configuration for the code intelligence subsystem.

    Environment Variables:
        CODE_INTEL_REPO_ROOT: Repository root path (default: .)
        CODE_INTEL_LANGUAGES: Comma-separated language list (default: python,typescript,javascript)
        CODE_INTEL_EXCLUDE_PATTERNS: Comma-separated glob patterns to exclude
        CODE_INTEL_EMBEDDING_MODEL: HuggingFace model ID (default: jinaai/jina-code-embeddings-0.5b)
        CODE_INTEL_EMBEDDING_DEVICE: torch device (default: cpu)
        CODE_INTEL_EMBEDDING_BATCH_SIZE: Batch size for embedding (default: 64)
        CODE_INTEL_DEFAULT_TOKEN_BUDGET: Default query token budget (default: 4096)
        CODE_INTEL_WATCHER_DEBOUNCE_MS: File watcher debounce (default: 300)
        CODE_INTEL_PAGERANK_DAMPING: PageRank damping factor (default: 0.85)
        CODE_INTEL_MAX_DEPENDENCY_DEPTH: Max dependency graph traversal (default: 3)
        CODE_INTEL_CACHE_DIR: Storage directory name (default: .code-intel)
        CODE_INTEL_LANCEDB_COMPACT_INTERVAL_MINUTES: LanceDB compaction interval (default: 30)
    """

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
            "**/node_modules/**", "**/dist/**", "**/.venv/**",
            "**/bin/**", "**/obj/**", "**/__pycache__/**",
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
    embedding_batch_size: int = Field(
        default=64, ge=1, le=512,
        description="Batch size for embedding computation",
    )
    default_token_budget: int = Field(
        default=4096, ge=256, le=65536,
        description="Default token budget for context queries",
    )
    watcher_debounce_ms: int = Field(
        default=300, ge=50, le=5000,
        description="File watcher debounce window in milliseconds",
    )
    pagerank_damping: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="PageRank damping factor",
    )
    max_dependency_depth: int = Field(
        default=3, ge=1, le=10,
        description="Maximum hops for dependency graph traversal",
    )
    cache_dir: str = Field(
        default=".code-intel",
        description="Directory name for index artifacts (relative to repo root)",
    )
    lancedb_compact_interval_minutes: int = Field(
        default=30, ge=5,
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
```

---

## 7. Exception Hierarchy

Follows the `DomainError` pattern (PADR-103) from `praecepta.foundation.domain.exceptions`.

```python
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
        ctx = {"language": language, **context}
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
```

---

## 8. Entry-Point Registrations

### 8.1 pyproject.toml Entry Points

```toml
[project.entry-points."praecepta.lifespan"]
codeintel = "praecepta.infra.codeintel:lifespan_contribution"
```

This is the only entry point needed. The code intelligence subsystem doesn't expose FastAPI routers, middleware, or error handlers — it is consumed via MCP tools and Python API.

### 8.2 Lifespan Contribution

```python
# lifespan.py
from praecepta.foundation.application import LifespanContribution

@asynccontextmanager
async def _codeintel_lifespan(app: Any) -> AsyncIterator[None]:
    """Load indexes on startup, stop watcher on shutdown.

    Startup:
        1. Load serialized structural index from disk (graph.pkl)
        2. Open LanceDB database connection
        3. Start file watcher (if configured)

    Shutdown:
        1. Stop file watcher
        2. Serialize structural index to disk
        3. Close LanceDB connection

    Priority 250: after projections (200), since code intelligence
    is an auxiliary service that doesn't block core event processing.
    """
    ...

lifespan_contribution = LifespanContribution(
    hook=_codeintel_lifespan,
    priority=250,
)
```

---

## 9. Storage Layout

All index artifacts live under `{repo_root}/.code-intel/`:

```
{repo_root}/
└── .code-intel/                    # Managed by this package
    ├── lance.db/                   # LanceDB embedded database (vector store)
    ├── graph.pkl                   # Serialized NetworkX DiGraph
    ├── tags.cache.v1/              # diskcache for parsed tags (keyed by file_path + mtime)
    ├── trees/                      # Cached tree-sitter parse trees (for incremental parsing)
    └── config.json                 # Index configuration snapshot (languages, exclude patterns)
```

This directory should be added to `.gitignore`. The package should check for and warn if it's not excluded.

---

## 10. Language Extension Registry

Module-level constant + pure function (PADR-112 pattern).

```python
# parser/language_registry.py

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
    from pathlib import Path
    suffix = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(suffix)
```

Initial language support: **Python** and **TypeScript/JavaScript**. Additional languages (C#, Go, Rust, Java) are added as follow-up stories by creating new `.scm` query files and extending `LANGUAGE_EXTENSIONS`.

---

## 11. Package Dependencies

```toml
[project]
dependencies = [
    # Workspace
    "praecepta-foundation-domain",
    "praecepta-foundation-application",

    # Parsing
    "tree-sitter>=0.25.0",
    "tree-sitter-language-pack>=0.13.0",

    # Graph
    "networkx>=3.2",

    # Embeddings
    "transformers>=4.40.0",
    "torch>=2.2.0",

    # Vector store
    "lancedb>=0.8.0",
    "pyarrow>=15.0.0",

    # Caching
    "diskcache>=5.6.0",

    # Token counting
    "tiktoken>=0.7.0",

    # File watching
    "watchdog>=4.0.0",

    # MCP surface
    "mcp>=1.0.0",

    # Config
    "pydantic>=2.6.0",
    "pydantic-settings>=2.0",

    # CLI
    "click>=8.1.0",
]
```

Notably excluded: `psycopg`, `pgvector` — analytics projection is deferred.

---

## 12. Root `pyproject.toml` Changes

Four sections must be updated when adding this package (per CLAUDE.md "Adding a New Package"):

### 12.1 `[project] dependencies`

```toml
dependencies = [
    # ... existing 11 packages ...
    "praecepta-infra-codeintel",
]
```

### 12.2 `[tool.uv.sources]`

```toml
praecepta-infra-codeintel = { workspace = true }
```

### 12.3 `[tool.mypy] mypy_path`

Append `:packages/infra-codeintel/src` to the existing colon-separated path.

### 12.4 `[tool.commitizen] version_files`

```toml
"packages/infra-codeintel/pyproject.toml:^version",
```

### 12.5 `CLAUDE.md` Packages Table

Add row:

```
| praecepta-infra-codeintel | praecepta.infra.codeintel | 1 |
```

---

## 13. Deviations from Design Spec

| Design Spec | This Architecture | Rationale |
|-------------|-------------------|-----------|
| Standalone `code-intel` package | Workspace member `praecepta-infra-codeintel` | Shared versioning, tooling, architectural boundary enforcement |
| Namespace `code_intel` | `praecepta.infra.codeintel` (PEP 420) | Consistent with Layer 1 infrastructure convention |
| Python `>=3.11` | `>=3.12` | Monorepo constraint |
| Analytics projection (§3.8) | Deferred | No concrete use case yet; added as separate epic when needed |
| 6 initial languages (§3.2) | 2 (Python + TypeScript/JS) | Covers primary languages; others added as follow-up stories |
| `namedtuple` for Tag (§3.2) | `NamedTuple` (typed) | Consistent with strict mypy |
| `docker/` directory (§11.8) | Deferred to surface phase | Focus on core functionality first |
| Distribution via GitHub Releases (§11.4) | Via workspace `uv sync` | Monorepo distribution model |
| `click` CLI (§11.3) | Kept as specified | CLI is the MCP server entry point |
| `[project.scripts]` (§11.2) | `[project.entry-points."praecepta.lifespan"]` for app integration; `[project.scripts]` for standalone CLI | Both models supported |

---

## 14. Testing Strategy

Follows PADR-104 test patterns from existing packages:

- **Unit tests** (`@pytest.mark.unit`): Pure logic — tag extraction, ranking fusion, token packing, rendering, language detection, settings validation
- **Integration tests** (`@pytest.mark.integration`): Tree-sitter parsing of real files, LanceDB operations, end-to-end query pipeline
- **Fixtures**: Small sample repository under `tests/fixtures/sample_repo/` with Python and TypeScript files
- **Helpers**: `_make_tag()`, `_make_symbol()`, `_make_query()` factory functions in `conftest.py`
- **Coverage target**: 80% (consistent with monorepo standard)
- **Async**: `asyncio_mode = "strict"` (monorepo-wide setting)
