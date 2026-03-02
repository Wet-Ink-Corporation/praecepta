# Code Intelligence & Context Assembly System — Design Specification

## 1. System Purpose

Build a code intelligence subsystem for an agent orchestration platform that provides AI agents with accurate, ranked, token-budgeted code context assembled from structural analysis and semantic search over arbitrary codebases.

The system must support multi-language codebases, incremental indexing on file changes, and expose its capabilities through both a Python API and MCP tool surface.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Source Files (disk)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              File Watcher (watchdog)                      │
│              Detects changes → triggers incremental parse │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Tree-sitter CST Parser                      │
│              Incremental parse with old_tree reference    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Semantic Extractor                           │
│              .scm tag queries per language                │
│              Extracts: definitions, references, sigs      │
│              Outputs: Tag(file, line, name, kind)         │
└───────┬─────────────────────────┬───────────────────────┘
        │                         │
        ▼                         ▼
┌───────────────────┐  ┌──────────────────────────────────┐
│  Structural Index  │  │  Semantic Index                   │
│  NetworkX DiGraph  │  │  LanceDB (embedded)               │
│  PageRank ranking  │  │  jina-code-embeddings-0.5b        │
│                    │  │  Enriched signature embeddings     │
└───────┬───────────┘  └──────────┬───────────────────────┘
        │                         │
        └──────────┬──────────────┘
                   │
        ┌──────────▼──────────────────────────────────────┐
        │  Context Assembler                               │
        │  Fuses structural + semantic rankings            │
        │  Intent-aware weight adjustment                  │
        │  Token-budget packing via binary search          │
        │  Hydrates full source from disk on demand        │
        │  Exposes: Python API + MCP tools                 │
        └──────────┬──────────────────────────────────────┘
                   │
        ┌──────────▼──────────────────────────────────────┐
        │  Analytics Projection (async, batched)           │
        │  PostgreSQL + pgvector                           │
        │  Time-series metrics, agent query logs           │
        │  Future: Neo4j extension for knowledge-code graph│
        └─────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 File Watcher

**Purpose:** Detect source file changes and trigger incremental re-indexing.

**Package:** `watchdog`

**Behavior:**
- Watch the repository root recursively
- Debounce rapid changes (300ms window) to avoid re-parsing during active typing
- On file change: trigger incremental tree-sitter parse, update structural index subgraph, re-embed changed symbols in LanceDB
- On file create/delete: full subgraph rebuild for affected module
- Respect `.gitignore` patterns and a configurable exclusion list
- Enqueue async PostgreSQL sync job (batched, not on every change)

**Interface:**
```python
class FileWatcher(Protocol):
    def start(self, repo_root: Path, on_change: Callable[[list[FileEvent]], Awaitable[None]]) -> None: ...
    def stop(self) -> None: ...

@dataclass
class FileEvent:
    path: Path
    event_type: Literal["created", "modified", "deleted"]
    timestamp: datetime
```

---

### 3.2 Tree-sitter CST Parser

**Purpose:** Parse source files into concrete syntax trees. Support incremental parsing for efficiency.

**Packages:**
- `tree-sitter` (v0.25.x) — core bindings
- `tree-sitter-language-pack` — pre-built grammars for 165+ languages

**Key behaviors:**
- Maintain a cache of parsed trees keyed by `(file_path, mtime)` for incremental parsing
- On file change, use `parser.parse(new_bytes, old_tree=cached_tree)` for incremental update
- Cache invalidation on file delete or language grammar change
- Use `diskcache.Cache` for persistent tree/tag caching across process restarts

**CST-to-semantic-units conversion:** Use tree-sitter `.scm` query files per language to extract definitions and references. These are S-expression patterns that identify semantic nodes.

**Example query (Python):**
```scheme
;; tags.scm for Python
(function_definition
  name: (identifier) @name.definition.function) @definition.function

(class_definition
  name: (identifier) @name.definition.class) @definition.class

(call
  function: (identifier) @name.reference.call) @reference.call

(call
  function: (attribute
    attribute: (identifier) @name.reference.call)) @reference.call
```

**Output type:**
```python
Tag = namedtuple("Tag", ["rel_fname", "fname", "line", "name", "kind"])
# kind: "definition" | "reference"
# Examples:
#   Tag("src/auth.py", "/repo/src/auth.py", 42, "authenticate_user", "definition")
#   Tag("src/api.py", "/repo/src/api.py", 15, "authenticate_user", "reference")
```

**Tag queries must be maintained per language.** Start with: Python, TypeScript/JavaScript, C#, Go, Rust, Java. Use Aider's existing `.scm` files as reference: https://github.com/Aider-AI/aider/tree/main/aider/queries

**Interface:**
```python
class CSTParser(Protocol):
    def parse_file(self, file_path: Path) -> ParseResult: ...
    def parse_file_incremental(self, file_path: Path, old_tree: Tree) -> ParseResult: ...
    def extract_tags(self, file_path: Path) -> list[Tag]: ...
    def get_supported_languages(self) -> list[str]: ...

@dataclass
class ParseResult:
    tree: Tree
    tags: list[Tag]
    language: str
    parse_duration_ms: float
```

---

### 3.3 Semantic Extractor

**Purpose:** Transform raw tags from the CST parser into enriched `SymbolSignature` objects suitable for embedding and indexing.

**Behavior:**
- Walk the CST tree for each definition tag
- Extract: full signature line, docstring (first paragraph), decorators, type hints, parameter names/types, return type, parent class/module
- Construct the `SymbolSignature.embedding_text` property (the text that gets embedded)
- Compute relationships: which symbols does this definition reference? Which symbols reference it?

**Embedding text construction (what gets sent to the embedding model):**
```
# Member of AuthService
@require_permissions("admin")
async def revoke_session(self, session_id: str, reason: str = "manual") -> bool:
    Revoke an active session and notify the user.
```

This combines: parent context, decorators, full signature, and docstring summary. It does NOT include the function body — that stays on disk.

**Interface:**
```python
class SemanticExtractor(Protocol):
    def extract_symbols(self, file_path: Path, tags: list[Tag], tree: Tree) -> list[SymbolSignature]: ...
    def extract_relationships(self, file_path: Path, tags: list[Tag]) -> list[SymbolRelationship]: ...

@dataclass
class SymbolRelationship:
    source: str          # qualified name of the source symbol
    target: str          # qualified name of the target symbol
    kind: str            # "calls" | "imports" | "inherits" | "implements" | "decorates"
```

---

### 3.4 Structural Index (Dependency Graph)

**Purpose:** Model the codebase as a directed graph of files and symbols. Rank by structural importance using PageRank. Support graph traversal for dependency exploration.

**Package:** `networkx`

**Graph structure:**
- Nodes: files (with attributes: path, language, symbol_count, mtime)
- Edges: symbol references from file A to file B (with attributes: symbol_name, kind, weight)
- Edge weight: number of distinct references from source to target
- Multi-edges allowed (one per distinct symbol reference)

**PageRank configuration:**
- Personalization vector: boost files the agent is currently working with (passed at query time)
- Damping factor: 0.85 (standard)
- After PageRank, distribute each node's rank to its outgoing edges proportionally to edge weight, associating rank with specific `(file, symbol)` pairs

**Incremental update:** On file change, remove all edges originating from the changed file, re-extract tags, re-add edges. PageRank must be recomputed (it's global), but on typical repo sizes (<50K nodes) this takes <100ms.

**Interface:**
```python
class StructuralIndex(Protocol):
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
    ) -> list[tuple[str, str]]: ...  # list of (symbol, relationship_kind)
    def get_repo_summary(self) -> RepoSummary: ...
```

**Caching:** Store the serialized graph to disk (`networkx.write_gpickle` or similar) for fast startup. Invalidate when any file's mtime changes.

---

### 3.5 Semantic Index (Vector Store)

**Purpose:** Store enriched signature embeddings for semantic similarity search. Enable natural-language-to-code and code-to-code retrieval.

**Packages:**
- `lancedb` — embedded vector database
- `jina-code-embeddings-0.5b` via `transformers` — embedding model (self-hosted, no API cost)

**Embedding model details:**
- Model: `jinaai/jina-code-embeddings-0.5b` (494M params, Qwen2.5-Coder backbone)
- Pooling: last-token pooling (NOT mean pooling — this model uses autoregressive architecture)
- Dimensions: 1024 (default), supports Matryoshka truncation
- Context window: 512 tokens (sufficient for signatures + docstrings)
- Task-specific instruction prefixes are required for optimal performance:
  - NL→Code queries: `Retrieve the code that is relevant to the query\n`
  - Code→Code queries: `Retrieve the code that is semantically similar to the query code\n`
  - TechQA queries: `Retrieve the document that answers the technical question\n`

**LanceDB table schema:**
```python
import pyarrow as pa

schema = pa.schema([
    pa.field("qualified_name", pa.string()),       # primary key
    pa.field("name", pa.string()),
    pa.field("kind", pa.string()),                  # function, class, method, etc.
    pa.field("language", pa.string()),
    pa.field("file_path", pa.string()),
    pa.field("start_line", pa.int32()),
    pa.field("end_line", pa.int32()),
    pa.field("signature", pa.string()),             # the raw signature text
    pa.field("docstring", pa.string()),             # first paragraph
    pa.field("parent_symbol", pa.string()),
    pa.field("embedding_text", pa.string()),        # what was embedded
    pa.field("embedding", pa.list_(pa.float32(), 1024)),  # the vector
    pa.field("token_count_estimate", pa.int32()),   # estimated tokens for full body
    pa.field("last_modified", pa.timestamp("ms")),
])
```

**LanceDB operational notes:**
- Create the database at `{repo_root}/.code-intel/lance.db`
- For datasets under 100K vectors (most single repos), brute-force search is fast enough — skip IVF-PQ index creation
- For larger repos, create index: `table.create_index(metric="cosine", num_partitions=256, num_sub_vectors=96)`
- Schedule periodic maintenance: `table.compact_files()` and `table.cleanup_old_versions()` (every 30 minutes or on git commit)
- Create a full-text search index on `signature` and `docstring` for exact symbol name matching: `table.create_fts_index(["signature", "docstring"])`

**Interface:**
```python
class SemanticIndex(Protocol):
    async def upsert_symbols(self, symbols: list[SymbolSignature]) -> int: ...
    async def remove_symbols(self, qualified_names: list[str]) -> int: ...
    async def search(
        self,
        query_text: str,
        query_type: Literal["nl2code", "code2code", "techqa"] = "nl2code",
        top_k: int = 20,
        filters: dict | None = None,  # {"language": "python", "kind": "function"}
    ) -> list[tuple[str, float]]: ...  # (qualified_name, cosine_similarity)
    async def search_by_name(self, symbol_name: str, top_k: int = 10) -> list[str]: ...
```

---

### 3.6 Context Assembler

**Purpose:** The agent-facing service that merges structural and semantic retrieval into a single ranked, token-budgeted response. This is the only component agents interact with directly.

#### 3.6.1 Query Schema

```python
class QueryIntent(str, Enum):
    UNDERSTAND = "understand"   # Favor breadth — signatures, call chains, architecture
    MODIFY     = "modify"       # Favor depth — full implementations + tests
    NAVIGATE   = "navigate"     # Favor structure — file tree, dep graph, entry points
    GENERATE   = "generate"     # Favor examples — similar patterns, conventions

@dataclass
class ContextQuery:
    # At least one required
    natural_language: str | None = None
    symbol_names: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)

    # Controls
    intent: QueryIntent = QueryIntent.UNDERSTAND
    token_budget: int = 4096
    max_chunks: int = 20

    # Filters
    languages: list[str] = field(default_factory=list)
    symbol_kinds: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)

    # Depth
    include_dependencies: bool = True
    dependency_depth: int = 1
    include_tests: bool = False
    include_source_code: bool = True   # False = signatures only (compact)

    # Ranking fusion weights (overridable by agent)
    structural_weight: float = 0.5
    semantic_weight: float = 0.5
```

#### 3.6.2 Response Schema

```python
@dataclass
class SourceLocation:
    file_path: str           # Relative to repo root
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0

@dataclass
class CodeChunk:
    # Identity
    qualified_name: str
    name: str
    kind: str                # function, class, method, etc.
    language: str
    location: SourceLocation
    signature: str
    docstring: str | None

    # Content — hydrated from disk at query time, NOT stored in index
    source_code: str | None          # Full body (None if signatures-only mode)
    context_snippet: str | None      # Surrounding imports/context

    # Ranking
    relevance_score: float           # 0.0-1.0, fused score
    structural_rank: float           # PageRank-derived
    semantic_similarity: float       # Cosine similarity to query
    retrieval_source: str            # "structural" | "semantic" | "both" | "direct" | "dependency"

    # Relationships
    calls: list[str]                 # Symbols this chunk calls
    called_by: list[str]             # Symbols that call this
    imports: list[str]
    imported_by: list[str]

    # Token accounting
    token_count: int

@dataclass
class RepoSummary:
    total_files: int
    total_symbols: int
    languages: dict[str, int]
    entry_points: list[str]
    top_symbols_by_pagerank: list[str]
    module_clusters: list[dict]

@dataclass
class ContextResponse:
    chunks: list[CodeChunk]
    total_tokens_used: int
    token_budget: int
    chunks_available: int            # How many more exist beyond budget

    repo_summary: RepoSummary | None = None   # Included for NAVIGATE intent

    # Query metadata
    query_echo: str | None = None
    intent_detected: QueryIntent | None = None
    search_terms_used: list[str] = field(default_factory=list)
    files_scanned: int = 0
    index_timestamp: str | None = None
    stale_files: list[str] = field(default_factory=list)
```

#### 3.6.3 Ranking Fusion Algorithm

```
Input: structural_results[(name, pagerank)], semantic_results[(name, cosine_sim)]
Output: fused_results[(name, score)] sorted descending

1. Apply intent-based weight adjustment:
   - UNDERSTAND: semantic=0.5, structural=0.5
   - MODIFY:     semantic=0.3, structural=0.7
   - NAVIGATE:   semantic=0.2, structural=0.8
   - GENERATE:   semantic=0.7, structural=0.3

2. Normalize each result set independently to [0.0, 1.0]

3. For each unique symbol across both sets:
   fused_score = (normalized_structural * struct_weight) + (normalized_semantic * sem_weight)

4. If symbol appears in BOTH result sets: fused_score *= 1.2 (cap at 1.0)

5. Sort by fused_score descending
```

#### 3.6.4 Token Budget Packing

```
Input: ranked_chunks (sorted by fused score), token_budget, token_counter function
Output: selected_chunks, tokens_used, chunks_remaining

1. Check if all chunks fit. If yes, return all.

2. Binary search for maximum chunk count N where sum(tokens[0:N]) <= budget

3. After packing N full chunks, check remaining budget:
   - If next chunk's SIGNATURE fits in remaining budget, include it as signature-only
   - This gives agents awareness of the symbol's existence without consuming full-body tokens

4. Return (selected_chunks, tokens_used, len(ranked_chunks) - N)
```

#### 3.6.5 Context String Rendering

The `as_context_string` property renders the response for direct injection into an LLM prompt. Format uses XML-tagged structure with attributes for metadata (token-efficient):

```xml
<code_context tokens_used="7845" budget="8192" chunks="18" more_available="7">

<chunk rank="1" relevance="0.95" source="both"
       symbol="authenticate_user" kind="function"
       location="src/auth/service.py:42-89">
  # Calls: validate_credentials, create_session, emit_auth_event
  # Called by: login_handler, api_auth_middleware
  async def authenticate_user(
      credentials: UserCredentials,
      provider: AuthProvider = AuthProvider.LOCAL
  ) -> AuthResult:
      '''Authenticate a user against the configured provider.'''
      ...full implementation...
</chunk>

<chunk rank="2" relevance="0.88" source="structural"
       symbol="AuthProvider" kind="enum"
       location="src/auth/types.py:12-18">
  class AuthProvider(str, Enum):
      LOCAL = "local"
      LDAP = "ldap"
</chunk>

</code_context>
```

#### 3.6.6 Query Execution Pipeline

```
1. Parse ContextQuery
   - Validate at least one query dimension is provided
   - Detect intent if not explicitly set

2. Parallel retrieval
   a. Semantic path:
      - Embed NL query with Jina 0.5b (with appropriate task prefix)
      - Search LanceDB for top-K similar signatures
      - Apply metadata filters (language, kind, exclude_paths)
   b. Structural path:
      - Extract symbol names from NL query (simple tokenization + fuzzy match against index)
      - Run PageRank personalized toward files containing matched symbols
      - Return top-K by rank

3. If symbol_names or file_paths provided: add as DIRECT results (highest priority)

4. Fuse rankings (see 3.6.3)

5. Dependency expansion:
   - For top results, walk the graph `dependency_depth` hops
   - Add discovered symbols as DEPENDENCY results (lower priority)
   - Deduplicate against existing results

6. Hydrate from disk:
   - For each result within token budget: read source file[start_line:end_line]
   - If include_source_code=False: skip hydration, return signatures only

7. Pack to budget (see 3.6.4)

8. Construct and return ContextResponse
```

#### 3.6.7 Service Interface

```python
class ContextAssembler(Protocol):
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

---

### 3.7 MCP Tool Surface

Five tools exposed to agent frameworks. These are thin wrappers around `ContextAssembler`.

| Tool | Maps To | Primary Input | Output |
|------|---------|---------------|--------|
| `code_context_search` | `.query()` | NL query + optional filters | `ContextResponse` as JSON |
| `code_symbol_lookup` | `.get_symbol()` | Qualified symbol name | Single `CodeChunk` as JSON |
| `code_dependency_graph` | `.get_dependencies()` | Symbol name + depth + direction | List of `CodeChunk` as JSON |
| `code_repo_overview` | `.get_repo_summary()` | (none) | `RepoSummary` as JSON |
| `code_index_refresh` | `.refresh_index()` | Optional file paths | `IndexStats` as JSON |

**MCP registration example (FastMCP):**
```python
@mcp.tool()
async def code_context_search(
    query: str,
    intent: str = "understand",
    token_budget: int = 4096,
    include_dependencies: bool = True,
    dependency_depth: int = 1,
    languages: list[str] | None = None,
    symbol_kinds: list[str] | None = None,
    include_tests: bool = False,
) -> dict:
    """Search the codebase for relevant context using natural language.

    Returns ranked code chunks with signatures, source code, and dependency
    relationships, packed to fit within the specified token budget.

    Args:
        query: Natural language description of what you're looking for
        intent: How you plan to use the context —
                "understand" (breadth), "modify" (depth + deps),
                "navigate" (structure), "generate" (similar patterns)
        token_budget: Maximum tokens in the response (default 4096)
        include_dependencies: Whether to expand results with dependency chain
        dependency_depth: How many hops to walk in the dependency graph
        languages: Filter results to specific languages (e.g., ["python", "typescript"])
        symbol_kinds: Filter to specific symbol types (e.g., ["function", "class"])
        include_tests: Whether to include test files in results
    """
    ctx_query = ContextQuery(
        natural_language=query,
        intent=QueryIntent(intent),
        token_budget=token_budget,
        include_dependencies=include_dependencies,
        dependency_depth=dependency_depth,
        languages=languages or [],
        symbol_kinds=symbol_kinds or [],
        include_tests=include_tests,
    )
    response = await assembler.query(ctx_query)
    return response.to_dict()
```

---

### 3.8 Analytics Projection (PostgreSQL)

**Purpose:** Persistent, multi-user queryable store for UI dashboards and codebase analytics. Updated asynchronously — NOT on the agent hot path.

**Sync pattern:** Batch write every 5 minutes or on git commit hook. Async queue from the indexer.

**Schema:**

```sql
-- Core symbol table (mirrors LanceDB, but with SQL query capabilities)
CREATE TABLE symbols (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qualified_name      TEXT UNIQUE NOT NULL,
    name                TEXT NOT NULL,
    kind                TEXT NOT NULL,
    language            TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    start_line          INT,
    end_line            INT,
    signature           TEXT,
    docstring           TEXT,
    parent_symbol       TEXT,
    embedding           vector(1024),      -- pgvector
    complexity          INT,               -- cyclomatic complexity if computable
    token_count         INT,
    last_modified       TIMESTAMPTZ,
    indexed_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_symbols_language ON symbols(language);
CREATE INDEX idx_symbols_kind ON symbols(kind);
CREATE INDEX idx_symbols_file ON symbols(file_path);
CREATE INDEX idx_symbols_embedding ON symbols USING ivfflat (embedding vector_cosine_ops);

-- Dependency edges
CREATE TABLE edges (
    source_symbol   TEXT NOT NULL REFERENCES symbols(qualified_name),
    target_symbol   TEXT NOT NULL REFERENCES symbols(qualified_name),
    kind            TEXT NOT NULL,   -- calls, imports, inherits, implements
    weight          FLOAT DEFAULT 1.0,
    PRIMARY KEY (source_symbol, target_symbol, kind)
);

CREATE INDEX idx_edges_source ON edges(source_symbol);
CREATE INDEX idx_edges_target ON edges(target_symbol);

-- Time-series snapshots
CREATE TABLE codebase_snapshots (
    id                  SERIAL PRIMARY KEY,
    commit_hash         TEXT,
    snapshot_at         TIMESTAMPTZ DEFAULT NOW(),
    total_files         INT,
    total_symbols       INT,
    languages           JSONB,
    avg_complexity      FLOAT,
    stale_file_count    INT,
    orphan_symbols      INT
);

-- Agent query log
CREATE TABLE agent_queries (
    id                  SERIAL PRIMARY KEY,
    query_text          TEXT,
    intent              TEXT,
    token_budget        INT,
    chunks_returned     INT,
    tokens_used         INT,
    retrieval_sources   JSONB,
    duration_ms         INT,
    queried_at          TIMESTAMPTZ DEFAULT NOW()
);
```

**Future extension:** When a concrete use case emerges, extend the existing Neo4j instance (currently used for NER-based markdown knowledge base) with `CodeSymbol` nodes and `:CALLS`/`:IMPORTS`/`:IMPLEMENTS` relationships. This enables cross-graph traversal from business requirements → architecture decisions → code implementations.

---

## 4. Data Flow

### 4.1 Initial Indexing (cold start)

```
1. Walk repository, discover all source files
2. For each file:
   a. Detect language from extension
   b. Parse with tree-sitter → get CST
   c. Run .scm tag queries → get definitions and references
   d. Extract SymbolSignatures via SemanticExtractor
   e. Compute embedding via Jina 0.5b
   f. Insert into LanceDB
   g. Add nodes/edges to NetworkX graph
3. Compute PageRank on completed graph
4. Serialize graph to disk cache
5. Async: batch-write to PostgreSQL
6. Log: total files, symbols, languages, duration
```

### 4.2 Incremental Update (file change)

```
1. File watcher detects change to src/auth/service.py
2. Debounce (300ms)
3. Incremental parse: parser.parse(new_bytes, old_tree=cached_tree)
4. Re-extract tags for changed file only
5. Diff tags against cached tags:
   - Removed symbols: delete from LanceDB, remove graph edges
   - New symbols: embed and insert into LanceDB, add graph edges
   - Modified symbols: re-embed, upsert in LanceDB, update graph edges
6. Recompute PageRank (global, but fast on typical repo sizes)
7. Update disk cache
8. Enqueue async PostgreSQL sync
```

### 4.3 Agent Query

```
1. Agent calls code_context_search("authentication flow for OAuth2", intent="modify")
2. Context Assembler:
   a. Embeds query with Jina 0.5b (prefix: "Retrieve the code that is relevant to the query\n")
   b. LanceDB search: top-20 by cosine similarity
   c. PageRank: personalized toward files containing "auth", "oauth" symbols
   d. Fuse rankings with MODIFY weights (0.7 structural, 0.3 semantic)
   e. Expand top-10 by 1 hop in dependency graph
   f. Hydrate: read source code from disk for each result
   g. Pack into 4096 token budget
3. Return ContextResponse
4. Log query to agent_queries table
```

---

## 5. Storage Layout

```
{repo_root}/
├── .code-intel/                    # All index artifacts
│   ├── lance.db/                   # LanceDB embedded database
│   ├── graph.pkl                   # Serialized NetworkX graph
│   ├── tags.cache.v1/              # diskcache for parsed tags
│   ├── trees/                      # Cached tree-sitter parse trees
│   └── config.json                 # Index configuration
├── src/                            # Source code (read-only from indexer's perspective)
└── ...
```

The `.code-intel/` directory should be added to `.gitignore`.

---

## 6. Configuration

```json
{
  "repo_root": ".",
  "languages": ["python", "typescript", "csharp"],
  "exclude_patterns": ["**/node_modules/**", "**/dist/**", "**/.venv/**", "**/bin/**", "**/obj/**"],
  "include_patterns": ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.cs"],
  "embedding_model": "jinaai/jina-code-embeddings-0.5b",
  "embedding_device": "cuda",
  "embedding_batch_size": 64,
  "token_counter_model": "gpt-4",
  "default_token_budget": 4096,
  "file_watcher_debounce_ms": 300,
  "postgres_sync_interval_seconds": 300,
  "lancedb_compact_interval_minutes": 30,
  "pagerank_damping": 0.85,
  "max_dependency_depth": 3,
  "cache_dir": ".code-intel"
}
```

---

## 7. Package Dependencies

```
# Core parsing
tree-sitter>=0.25.0
tree-sitter-language-pack>=0.13.0

# Graph
networkx>=3.2

# Embeddings
transformers>=4.40.0
torch>=2.2.0

# Vector store
lancedb>=0.8.0
pyarrow>=15.0.0

# Caching
diskcache>=5.6.0

# Token counting
tiktoken>=0.7.0

# File watching
watchdog>=4.0.0

# Analytics projection
psycopg[binary]>=3.1.0
pgvector>=0.2.0

# MCP surface
mcp>=1.0.0       # or fastmcp

# Utilities
pydantic>=2.6.0  # for config validation
```

---

## 8. Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| LanceDB for agent hot path, PostgreSQL for analytics | LanceDB is embedded (sub-10ms, no network), Postgres is multi-user queryable. Different access patterns, different stores. |
| NetworkX in-memory, not a graph DB | Repo-scale graphs (10K-50K nodes) fit easily in memory. Sub-millisecond traversal. No network overhead. Neo4j extension deferred to when cross-knowledge-graph use case emerges. |
| Jina 0.5b self-hosted, not Voyage API | <1 percentage point benchmark difference. Zero marginal cost. No network latency. Code never leaves the machine (government client requirement). 512-token context window is sufficient for signatures. |
| Embed signatures, not full bodies | Compact representations = faster search, lower storage, better signal-to-noise ratio. Full bodies are hydrated from disk only for results that make the token budget. |
| Intent-aware ranking fusion | Different agent tasks need different balances of structural vs. semantic context. MODIFY needs the call chain; GENERATE needs similar patterns. Static fusion can't serve both. |
| Binary search for token packing | Matches Aider's proven approach. Fills 85-100% of budget efficiently. Graceful degradation: overflow symbols included as signature-only. |
| .scm query files per language | Tree-sitter's native query mechanism. Declarative, fast, maintainable. Same approach used by Aider (40+ languages), Cline, and most tree-sitter-based tools. |
| Async PostgreSQL sync | Analytics don't need real-time freshness. 5-minute lag is acceptable. Keeps the agent hot path free of Postgres write latency. |

---

## 9. Testing Strategy

### Unit tests
- Tree-sitter parsing: parse known code snippets, verify extracted tags match expected
- Signature extraction: verify SymbolSignature fields for each supported language
- Ranking fusion: test with known structural/semantic scores, verify output order
- Token packing: verify budget compliance, verify signature-only fallback

### Integration tests
- End-to-end: index a small repo → query → verify response contains expected symbols
- Incremental update: modify a file → verify index reflects changes → verify query results update
- Multi-language: index a polyglot repo, verify cross-language dependency detection

### Performance benchmarks
- Index time for repos at: 1K, 10K, 50K, 100K files
- Query latency at each scale (target: <100ms for agent queries)
- Incremental update latency (target: <500ms per file change)
- Memory footprint of NetworkX graph at each scale

---

## 10. Implementation Order

1. **Tree-sitter parser + tag extraction** — foundation, everything depends on this
2. **Semantic extractor** — SymbolSignature construction from tags
3. **Structural index** — NetworkX graph + PageRank
4. **Semantic index** — Jina embeddings + LanceDB
5. **Context assembler** — ranking fusion + token packing + disk hydration
6. **MCP tool surface** — thin wrappers around assembler
7. **File watcher** — incremental update pipeline
8. **PostgreSQL projection** — analytics layer
9. **UI dashboards** — visualization layer (separate concern)

---

## 11. Distribution & Packaging

### 11.1 Package Structure

The system is distributed as a single Python package with an MCP server entry point:

```
code-intel/
├── pyproject.toml
├── README.md
├── src/
│   └── code_intel/
│       ├── __init__.py
│       ├── __main__.py           # CLI entry point
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── cst_parser.py     # Tree-sitter CST parsing
│       │   ├── tag_extractor.py  # .scm query runner
│       │   └── queries/          # Per-language .scm files
│       │       ├── python.scm
│       │       ├── typescript.scm
│       │       ├── csharp.scm
│       │       └── ...
│       ├── graph/
│       │   ├── __init__.py
│       │   └── structural_index.py   # NetworkX graph + PageRank
│       ├── embeddings/
│       │   ├── __init__.py
│       │   ├── encoder.py            # Jina model wrapper
│       │   └── semantic_index.py     # LanceDB operations
│       ├── assembler/
│       │   ├── __init__.py
│       │   ├── context_assembler.py  # Ranking fusion + token packing
│       │   ├── schemas.py            # ContextQuery, ContextResponse, CodeChunk
│       │   └── renderer.py           # XML context string output
│       ├── watcher/
│       │   ├── __init__.py
│       │   └── file_watcher.py       # watchdog integration
│       ├── analytics/
│       │   ├── __init__.py
│       │   ├── postgres_sync.py      # Async batch writer
│       │   └── migrations/           # SQL migration scripts
│       └── server/
│           ├── __init__.py
│           └── mcp_server.py         # MCP tool definitions
├── tests/
│   ├── test_parser/
│   ├── test_graph/
│   ├── test_embeddings/
│   ├── test_assembler/
│   └── fixtures/                     # Small repos for integration tests
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

### 11.2 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "code-intel"
version = "0.1.0"
description = "Code intelligence and context assembly for AI agents"
requires-python = ">=3.11"
dependencies = [
    "tree-sitter>=0.25.0",
    "tree-sitter-language-pack>=0.13.0",
    "networkx>=3.2",
    "transformers>=4.40.0",
    "torch>=2.2.0",
    "lancedb>=0.8.0",
    "pyarrow>=15.0.0",
    "diskcache>=5.6.0",
    "tiktoken>=0.7.0",
    "watchdog>=4.0.0",
    "mcp>=1.0.0",
    "pydantic>=2.6.0",
    "click>=8.1.0",
]

[project.optional-dependencies]
analytics = [
    "psycopg[binary]>=3.1.0",
    "pgvector>=0.2.0",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4.0",
]

[project.scripts]
code-intel = "code_intel.__main__:cli"
```

### 11.3 CLI Entry Point

```python
# src/code_intel/__main__.py
import click

@click.group()
@click.version_option()
def cli():
    """Code intelligence and context assembly for AI agents."""
    pass

@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio")
@click.option("--port", default=8420, help="Port for SSE transport")
@click.option("--device", default="cuda", help="Embedding model device (cuda/cpu)")
@click.option("--config", default=None, help="Path to code-intel.json config file")
def serve(repo, transport, port, device, config):
    """Start the MCP server."""
    ...

@cli.command()
@click.option("--repo", default=".", help="Repository root path")
@click.option("--device", default="cuda")
def index(repo, device):
    """Run a one-time full index of the repository."""
    ...

@cli.command()
@click.option("--repo", default=".", help="Repository root path")
def stats(repo):
    """Print index statistics for the repository."""
    ...

if __name__ == "__main__":
    cli()
```

### 11.4 Distribution via GitHub Releases

Build and publish wheels as GitHub Release assets on the internal repo. No private PyPI mirror required.

**Build:**
```bash
pip install build
python -m build          # produces dist/code_intel-0.1.0-py3-none-any.whl
```

**Publish:** Attach the `.whl` to a GitHub Release (manual or via CI).

**Install from GitHub Release:**
```bash
# Direct from release URL
pip install https://github.com/IQBG/code-intel/releases/download/v0.1.0/code_intel-0.1.0-py3-none-any.whl

# Or from the repo itself (builds from source)
pip install git+https://github.com/IQBG/code-intel.git@v0.1.0
```

**CI automation (GitHub Actions):**
```yaml
# .github/workflows/release.yml
name: Build and Release
on:
  push:
    tags: ["v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build
      - run: python -m build
      - run: pip install dist/*.whl && pytest
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/*.whl
```

**Versioning:** Tag releases with semver. Breaking changes to the MCP tool interface or ContextQuery/ContextResponse schemas bump the major version. New tools, new optional fields, or new languages bump minor. Bug fixes bump patch.

### 11.5 Distribution Layers

The system has three distribution layers with different scopes:

| Layer | What Ships | How | Scope |
|-------|-----------|-----|-------|
| Core package | `code-intel` wheel | GitHub Release → `pip install` | Shared across all projects and consultants |
| User-level MCP registration | Claude Code server config | `~/.claude/settings.json` | Per developer machine |
| Project-level config | Language filters, exclusions, slash commands | Checked into each repo | Per repository |

### 11.6 Claude Code Integration

**User-level registration** — available across all projects without per-repo setup:

```jsonc
// ~/.claude/settings.json
{
  "mcpServers": {
    "code-intel": {
      "command": "code-intel",
      "args": ["serve", "--repo", "${workspaceFolder}"],
      "env": {
        "CODE_INTEL_DEVICE": "cuda"
      }
    }
  }
}
```

**Project-level override** — when a project needs specific configuration:

```jsonc
// {repo_root}/.claude/settings.json
{
  "mcpServers": {
    "code-intel": {
      "command": "code-intel",
      "args": [
        "serve",
        "--repo", "${workspaceFolder}",
        "--config", "${workspaceFolder}/code-intel.json"
      ],
      "env": {
        "CODE_INTEL_DEVICE": "cpu"
      }
    }
  }
}
```

**Per-project configuration file:**

```jsonc
// {repo_root}/code-intel.json
{
  "languages": ["python", "typescript"],
  "exclude_patterns": ["**/migrations/**", "**/generated/**"],
  "default_token_budget": 8192,
  "include_tests": false,
  "dependency_depth": 2
}
```

### 11.7 Optional Convenience Slash Commands

Distribute these as markdown files checked into project repos. They cost nothing and provide ergonomic shortcuts for common queries:

```markdown
<!-- {repo_root}/.claude/commands/understand.md -->
Use the code_context_search tool with intent="understand" to find context
relevant to: $ARGUMENTS

Summarize the architecture, key relationships, and data flow you find.
```

```markdown
<!-- {repo_root}/.claude/commands/impact.md -->
Use the code_dependency_graph tool to analyze the impact of changing: $ARGUMENTS

Walk 2 hops in both directions. List every file and function that would be
affected, grouped by direct vs. transitive impact.
```

```markdown
<!-- {repo_root}/.claude/commands/map.md -->
Use the code_repo_overview tool to get the repository structure.

Present a concise architectural overview: major modules, entry points,
key abstractions, and how data flows between them.
```

### 11.8 Docker Distribution (Government / Air-Gapped Clients)

For environments where installing Python packages and downloading model weights is impractical, distribute as a Docker image with everything bundled:

```dockerfile
# docker/Dockerfile
FROM nvidia/cuda:12.4.1-runtime-ubuntu24.04

RUN apt-get update && apt-get install -y python3.11 python3-pip && rm -rf /var/lib/apt/lists/*

COPY dist/code_intel-*.whl /tmp/
RUN pip install /tmp/code_intel-*.whl --break-system-packages

# Pre-download model weights into image
RUN python3 -c "from transformers import AutoModel; AutoModel.from_pretrained('jinaai/jina-code-embeddings-0.5b')"

EXPOSE 8420
ENTRYPOINT ["code-intel", "serve", "--transport", "sse", "--port", "8420"]
```

```yaml
# docker/docker-compose.yml
services:
  code-intel:
    build: .
    ports:
      - "8420:8420"
    volumes:
      - "${REPO_PATH:-.}:/workspace:ro"
      - code-intel-cache:/root/.cache/code-intel
    environment:
      - CODE_INTEL_DEVICE=cuda
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

volumes:
  code-intel-cache:
```

Claude Code connects to the Docker-hosted server via SSE transport:

```jsonc
// ~/.claude/settings.json (Docker mode)
{
  "mcpServers": {
    "code-intel": {
      "type": "sse",
      "url": "http://localhost:8420/sse"
    }
  }
}
```

**Air-gapped delivery:** Build the image on a connected machine, `docker save` to a tarball, transport via approved media, `docker load` on the client network.

```bash
# Connected machine
docker build -t code-intel:0.1.0 docker/
docker save code-intel:0.1.0 | gzip > code-intel-0.1.0.tar.gz

# Air-gapped client
docker load < code-intel-0.1.0.tar.gz
```

---

## 12. Reference Implementations

| Project | What to Study | URL |
|---------|--------------|-----|
| Aider `repomap.py` | Tree-sitter → graph → PageRank → token-budgeted map | https://github.com/Aider-AI/aider/blob/main/aider/repomap.py |
| Aider `.scm` queries | Per-language tag query files | https://github.com/Aider-AI/aider/tree/main/aider/queries |
| Aider `grep_ast` | Code snippet rendering around lines of interest | https://github.com/paul-gauthier/grep-ast |
| RepoMapper | Standalone extraction of Aider's approach + MCP server | https://github.com/pdavis68/RepoMapper |
| Context+ | Tree-sitter + spectral clustering + Ollama embeddings MCP | https://contextplus.vercel.app/ |
| cAST paper | AST-based recursive chunking for code RAG | https://arxiv.org/html/2506.15655v1 |
| CodeRAG + Neo4j | Tree-sitter + graph DB + vector embeddings on nodes | https://medium.com/@shsax/how-i-built-coderag-with-dependency-graph-using-tree-sitter-0a71867059ae |
| LanceDB CodeQA | Tree-sitter chunking + LanceDB + retrieval pipeline | https://lancedb.com/blog/building-rag-on-codebases-part-1/ |
| Continue + LanceDB | Production IDE integration with embedded vector search | https://lancedb.com/blog/the-future-of-ai-native-development-is-local-inside-continues-lancedb-powered-evolution/ |
| Jina code embeddings paper | Training recipe + benchmark results for the embedding model | https://arxiv.org/abs/2508.21290 |
