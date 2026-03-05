# Infra Code Intelligence

Code intelligence and context assembly for AI agents.

```python
from praecepta.infra.codeintel import (
    ContextAssembler, ContextQuery, ContextResponse,
    QueryIntent, CodeIntelSettings, get_settings,
)
```

## Key Exports

### Schemas

| Export | Purpose |
|--------|---------|
| `ContextQuery` | Request schema: natural-language query, intent, token budget, file filters |
| `ContextResponse` | Response schema: ranked code chunks, repo summary, token usage |
| `CodeChunk` | Single code fragment with location, relevance score, and relationship metadata |
| `RepoSummary` | High-level repository overview (languages, file count, dependency graph stats) |
| `SourceLocation` | File path, line range, and symbol name for a code fragment |

### Protocols

| Export | Purpose |
|--------|---------|
| `ContextAssembler` | Top-level protocol: query → token-budgeted response |
| `CSTParser` | Tree-sitter CST parsing and `.scm` query execution |
| `SemanticExtractor` | Extracts embeddings from parsed symbols |
| `SemanticIndex` | LanceDB-backed vector similarity search |
| `StructuralIndex` | NetworkX graph index with PageRank-based ranking |
| `FileWatcher` | Filesystem event source for incremental re-indexing |

### Types

| Export | Purpose |
|--------|---------|
| `QueryIntent` | Enum: `UNDERSTAND`, `MODIFY`, `NAVIGATE`, `GENERATE` — controls ranking fusion weights |
| `ParseResult` | Output of CST parsing: symbols, relationships, tags |
| `SymbolSignature` | Name, kind, parameters, return type, docstring of a parsed symbol |
| `SymbolRelationship` | Directed edge (caller → callee, import, inheritance) between symbols |
| `Tag` | Tree-sitter tag capture (name, node type, position) |
| `FileEvent` | Filesystem change event (created, modified, deleted) |
| `IndexStats` | Counts and health metrics for both indexes |

### Configuration

| Export | Purpose |
|--------|---------|
| `CodeIntelSettings` | Pydantic settings with `CODE_INTEL_*` env var prefix |
| `get_settings` | Cached singleton accessor for `CodeIntelSettings` |

### Exceptions

| Export | Purpose |
|--------|---------|
| `CodeIntelError` | Base exception for all code intelligence errors |
| `ParseError` | Tree-sitter parsing failure |
| `UnsupportedLanguageError` | No grammar or `.scm` queries available for the requested language |
| `IndexError` | Indexing operation failure (structural or semantic) |
| `EmbeddingError` | Embedding generation failure |
| `BudgetExceededError` | Token budget exceeded during context assembly |

### Lifespan

| Export | Purpose |
|--------|---------|
| `lifespan_contribution` | `LifespanContribution` that initializes indexes and file watcher on app startup |

## Architecture Note

The code intelligence pipeline follows five stages:

1. **Parse** — Tree-sitter CST parsing with `.scm` query files extracts symbols, relationships, and tags from source files. Supported languages: Python, TypeScript, JavaScript.

2. **Extract** — `SemanticExtractor` generates vector embeddings (Jina) from parsed symbol signatures and docstrings.

3. **Index** — Dual indexing strategy:
    - *Structural*: NetworkX directed graph with PageRank scoring for call graphs, inheritance, and import relationships.
    - *Semantic*: LanceDB vector store for embedding-based similarity search.

4. **Assemble** — `ContextAssembler` fuses results from both indexes. Fusion weights are driven by `QueryIntent` (e.g. `MODIFY` favours structural neighbors, `UNDERSTAND` favours semantic similarity). Results are packed into a token budget with signature-only overflow for lower-ranked symbols.

5. **Surface** — Five MCP tools expose the pipeline to AI agents via a `FastMCP` server. A CLI (`code-intel serve|index|stats`) provides operational access. When started via `code-intel serve`, a `WatchdogFileWatcher` + `IncrementalUpdatePipeline` are wired through the server's `lifespan` hook so the indexes stay current as files change.

## CLI

```bash
# Start MCP server (stdio — default, for Claude Desktop / CLI clients)
code-intel serve --repo /path/to/repo

# Start MCP server (streamable-http — for remote / multi-client deployments)
code-intel serve --repo /path/to/repo --transport streamable-http --host 0.0.0.0 --port 8420

# One-shot full index
code-intel index --repo /path/to/repo

# Include test files in index
code-intel index --repo /path/to/repo --include-tests

# Print index statistics
code-intel stats --repo /path/to/repo

# Print stats as JSON
code-intel stats --repo /path/to/repo --json
```

## Configuration

`CodeIntelSettings` reads from environment variables with the `CODE_INTEL_` prefix (default values shown):

| Variable | Default | Purpose |
|----------|---------|---------|
| `CODE_INTEL_REPO_ROOT` | `.` | Root directory of the repository to index |
| `CODE_INTEL_LANGUAGES` | `python,typescript,javascript` | Languages to index |
| `CODE_INTEL_EXCLUDE_PATTERNS` | `**/node_modules/**`, `**/dist/**`, etc. | Glob patterns excluded from indexing |
| `CODE_INTEL_EMBEDDING_MODEL` | `jinaai/jina-code-embeddings-0.5b` | HuggingFace model ID for code embeddings |
| `CODE_INTEL_EMBEDDING_DEVICE` | `cpu` | Device for embedding model (`cpu`, `cuda`, `mps`) |
| `CODE_INTEL_EMBEDDING_TRUST_REMOTE_CODE` | `true` | Allow remote code execution when loading embedding model (required for Jina models) |
| `CODE_INTEL_EMBEDDING_BATCH_SIZE` | `64` | Batch size for embedding computation |
| `CODE_INTEL_DEFAULT_TOKEN_BUDGET` | `4096` | Default max tokens for context responses |
| `CODE_INTEL_CACHE_DIR` | `.code-intel` | Directory for index artifacts (relative to repo root) |
| `CODE_INTEL_WATCHER_DEBOUNCE_MS` | `300` | File watcher debounce window in milliseconds |
| `CODE_INTEL_PAGERANK_DAMPING` | `0.85` | PageRank damping factor for structural ranking |
| `CODE_INTEL_MAX_DEPENDENCY_DEPTH` | `3` | Maximum hops for dependency graph traversal |
| `CODE_INTEL_LANCEDB_COMPACT_INTERVAL_MINUTES` | `30` | LanceDB compaction interval |

## API Reference

::: praecepta.infra.codeintel
