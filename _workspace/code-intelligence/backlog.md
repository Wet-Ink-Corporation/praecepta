# Code Intelligence Package — Implementation Backlog

> Ordered epics and stories for `praecepta-infra-codeintel`. Each story includes acceptance criteria, files, dependencies, test requirements, and complexity (S/M/L).

---

## Phase 1: Foundation

Scaffolding, protocols, configuration, exceptions, and monorepo registration. No runtime functionality yet — this phase establishes the package skeleton and contracts.

---

### Story 1.1 — Scaffold Package Structure

**As a** developer, **I want** the `praecepta-infra-codeintel` package scaffolded with PEP 420 layout, **so that** it integrates with the monorepo toolchain.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/pyproject.toml`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/py.typed`
- `packages/infra-codeintel/tests/__init__.py`
- `packages/infra-codeintel/tests/conftest.py`

**Files to modify:**
- `pyproject.toml` (root) — 4 sections: dependencies, uv sources, mypy_path, commitizen version_files
- `CLAUDE.md` — add package to Packages table

**Acceptance criteria:**
- [ ] `uv sync --dev` succeeds with new package
- [ ] `uv run mypy` finds the package (no import errors for `praecepta.infra.codeintel`)
- [ ] `uv run lint-imports` passes (no boundary violations)
- [ ] No `__init__.py` exists in `praecepta/` or `praecepta/infra/` directories
- [ ] `py.typed` marker exists in leaf package

**Dependencies:** None

**Tests:** None (infrastructure scaffold only — verified by `make verify`)

---

### Story 1.2 — Define Value Objects and Types

**As a** developer, **I want** all shared value objects defined, **so that** protocols and implementations use consistent types.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/types.py`

**Acceptance criteria:**
- [ ] `Tag` (NamedTuple), `FileEvent`, `ParseResult`, `SymbolSignature`, `SymbolRelationship`, `QueryIntent`, `IndexStats` defined
- [ ] All types use `from __future__ import annotations`
- [ ] `mypy --strict` passes
- [ ] Exported from package `__init__.py`

**Dependencies:** 1.1

**Tests:**
- [ ] Unit: instantiation of each type, field access, equality checks

---

### Story 1.3 — Define Protocol Interfaces

**As a** developer, **I want** all 6 protocol interfaces defined with type signatures, **so that** implementations can be developed independently.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/protocols.py`

**Acceptance criteria:**
- [ ] `CSTParser`, `SemanticExtractor`, `StructuralIndex`, `SemanticIndex`, `ContextAssembler`, `FileWatcher` protocols defined
- [ ] All protocols use `@runtime_checkable`
- [ ] Type signatures match design spec sections 3.1–3.7
- [ ] `mypy --strict` passes
- [ ] Exported from package `__init__.py`

**Dependencies:** 1.2

**Tests:**
- [ ] Unit: verify `isinstance()` check works for each protocol with a minimal conforming class

---

### Story 1.4 — Implement Configuration Schema

**As a** developer, **I want** `CodeIntelSettings` with environment variable support, **so that** all configuration is centralized and validated.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/settings.py`

**Acceptance criteria:**
- [ ] `CodeIntelSettings` extends `BaseSettings` with `env_prefix="CODE_INTEL_"`
- [ ] All fields from architecture spec section 6 present with defaults and validation
- [ ] `@lru_cache` singleton via `get_settings()`
- [ ] `extra="ignore"` in `SettingsConfigDict`
- [ ] `mypy --strict` passes

**Dependencies:** 1.1

**Tests:**
- [ ] Unit: default values, env override via `monkeypatch`, validation errors for out-of-range values
- [ ] Unit: `get_settings()` returns same instance on repeated calls

---

### Story 1.5 — Implement Exception Hierarchy

**As a** developer, **I want** a structured exception hierarchy, **so that** error handling is consistent with the monorepo pattern.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/exceptions.py`

**Acceptance criteria:**
- [ ] `CodeIntelError` extends `DomainError` with `error_code` class attribute
- [ ] Subclasses: `ParseError`, `UnsupportedLanguageError`, `IndexError`, `EmbeddingError`, `BudgetExceededError`
- [ ] Each exception includes structured `context` dict
- [ ] `mypy --strict` passes

**Dependencies:** 1.1

**Tests:**
- [ ] Unit: each exception has correct `error_code`, `message`, `context` fields
- [ ] Unit: `str()` and `repr()` output includes context

---

### Story 1.6 — Define Assembly Schemas

**As a** developer, **I want** the query/response schemas defined, **so that** the assembler and MCP tools share a stable contract.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/schemas.py`

**Acceptance criteria:**
- [ ] `ContextQuery`, `ContextResponse`, `CodeChunk`, `SourceLocation`, `RepoSummary` defined as dataclasses
- [ ] `ContextQuery` validation: at least one of `natural_language`, `symbol_names`, `file_paths` is set
- [ ] `ContextResponse.as_context_string` property renders XML format per design spec §3.6.5
- [ ] All fields match design spec §3.6.1–3.6.2
- [ ] `mypy --strict` passes

**Dependencies:** 1.2

**Tests:**
- [ ] Unit: query validation rejects empty queries
- [ ] Unit: `as_context_string` renders expected XML for known inputs
- [ ] Unit: `to_dict()` serialization round-trip

---

## Phase 2: Parsing Pipeline

Tree-sitter parser, .scm tag queries, and diskcache integration.

---

### Story 2.1 — Implement Language Registry

**As a** developer, **I want** file extension to language detection, **so that** the parser knows which grammar and .scm queries to use.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/language_registry.py`

**Acceptance criteria:**
- [ ] `LANGUAGE_EXTENSIONS` maps extensions to language names (Python + TypeScript/JS)
- [ ] `SUPPORTED_LANGUAGES` frozenset derived from extensions
- [ ] `detect_language(file_path) -> str | None` function
- [ ] Module-level constants (PADR-112 pattern)

**Dependencies:** 1.1

**Tests:**
- [ ] Unit: `.py` → `"python"`, `.ts`/`.tsx` → `"typescript"`, `.js`/`.jsx`/`.mjs`/`.cjs` → `"javascript"`
- [ ] Unit: unknown extension returns `None`

---

### Story 2.2 — Create .scm Tag Query Files

**As a** developer, **I want** tree-sitter `.scm` query files for Python and TypeScript, **so that** the parser can extract definitions and references.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/queries/python.scm`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/queries/typescript.scm`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/queries/javascript.scm`

**Acceptance criteria:**
- [ ] Python: captures `function_definition`, `class_definition`, `call`, `import_from_statement`
- [ ] TypeScript: captures `function_declaration`, `class_declaration`, `method_definition`, `call_expression`, `import_statement`
- [ ] JavaScript: shares TypeScript queries where applicable
- [ ] Queries use Aider's `.scm` files as reference (see design spec §12)
- [ ] Queries produce `@name.definition.*` and `@name.reference.*` capture groups

**Dependencies:** 2.1

**Tests:**
- [ ] Integration: parse known Python snippet, verify expected tags match (count, names, kinds)
- [ ] Integration: parse known TypeScript snippet, verify expected tags match

---

### Story 2.3 — Implement Tag Extractor

**As a** developer, **I want** a tag extractor that runs .scm queries against parsed trees, **so that** I get structured `Tag` objects.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/tag_extractor.py`

**Acceptance criteria:**
- [ ] Loads `.scm` query file by language name
- [ ] Runs query against tree-sitter `Tree`, produces `list[Tag]`
- [ ] Handles `@name.definition.*` and `@name.reference.*` capture groups
- [ ] Raises `UnsupportedLanguageError` for unknown languages
- [ ] `.scm` files loaded via `importlib.resources` (not relative file paths)

**Dependencies:** 1.2, 1.5, 2.1, 2.2

**Tests:**
- [ ] Unit: mock tree and captures, verify Tag construction
- [ ] Integration: parse real Python file, extract tags, verify count and fields

---

### Story 2.4 — Implement CST Parser

**As a** developer, **I want** tree-sitter parsing with incremental support, **so that** source files are efficiently parsed into syntax trees.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/parser/cst_parser.py`

**Acceptance criteria:**
- [ ] Implements `CSTParser` protocol
- [ ] `parse_file()` detects language, parses with tree-sitter, returns `ParseResult`
- [ ] `parse_file_incremental()` uses `old_tree` for incremental parsing
- [ ] `extract_tags()` delegates to `TagExtractor`
- [ ] `get_supported_languages()` returns from language registry
- [ ] Raises `ParseError` on parse failure, `UnsupportedLanguageError` for unknown extensions

**Dependencies:** 1.3, 2.3

**Tests:**
- [ ] Unit: parse result has expected fields
- [ ] Integration: parse Python file, verify tree is valid and tags extracted
- [ ] Integration: incremental parse produces same tags as full parse for unchanged file

---

### Story 2.5 — Implement Parse Cache (diskcache)

**As a** developer, **I want** parsed tags cached to disk, **so that** re-indexing after process restart is fast.

**Complexity:** S

**Files to create:** (modify `cst_parser.py`)

**Acceptance criteria:**
- [ ] `diskcache.Cache` keyed by `(file_path, mtime)` stores parsed `Tag` lists
- [ ] Cache directory is `{cache_dir}/tags.cache.v1/`
- [ ] Cache hit skips tree-sitter parsing entirely
- [ ] Cache invalidated on mtime change or file deletion
- [ ] Cache versioned (`.v1`) to allow format changes without migration

**Dependencies:** 2.4, 1.4

**Tests:**
- [ ] Unit: cache hit returns stored tags
- [ ] Unit: mtime change causes cache miss
- [ ] Integration: parse, restart (new Cache instance), verify cache hit

---

## Phase 3: Indexing

Semantic extraction, structural graph, embedding encoding, and vector store.

---

### Story 3.1 — Implement Semantic Extractor

**As a** developer, **I want** raw tags enriched into `SymbolSignature` objects, **so that** symbols are ready for embedding and indexing.

**Complexity:** L

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/extraction/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/extraction/semantic_extractor.py`

**Acceptance criteria:**
- [ ] Implements `SemanticExtractor` protocol
- [ ] Walks CST tree for each definition tag to extract: full signature line, first-paragraph docstring, decorators, type hints, parameter names/types, return type, parent class/module
- [ ] Constructs `embedding_text` property (parent context + decorators + signature + docstring)
- [ ] `extract_relationships()` computes calls/imports/inherits edges
- [ ] Estimates token count for full symbol body using tiktoken
- [ ] Works for Python and TypeScript

**Dependencies:** 1.3, 2.4

**Tests:**
- [ ] Unit: Python function → expected `SymbolSignature` fields
- [ ] Unit: Python class with methods → parent_symbol set correctly
- [ ] Unit: `embedding_text` format matches design spec §3.3
- [ ] Unit: relationship extraction finds calls and imports

---

### Story 3.2 — Implement Structural Index

**As a** developer, **I want** a NetworkX directed graph with PageRank ranking, **so that** symbols are ranked by structural importance.

**Complexity:** L

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/index/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/index/structural_index.py`

**Acceptance criteria:**
- [ ] Implements `StructuralIndex` protocol
- [ ] `build()` creates DiGraph with file nodes and symbol-reference edges
- [ ] `update_file()` removes stale edges, re-adds from new tags
- [ ] `remove_file()` removes node and all incident edges
- [ ] `get_ranked_symbols()` runs PageRank (damping from settings) with optional personalization vector
- [ ] `get_dependencies()` traverses graph with direction and depth params
- [ ] `get_repo_summary()` returns file/symbol counts, language distribution, top PageRank symbols
- [ ] Graph serialized to `{cache_dir}/graph.pkl` via `pickle`
- [ ] Load from disk on instantiation if file exists

**Dependencies:** 1.3, 1.4, 3.1

**Tests:**
- [ ] Unit: build graph from known tags, verify node/edge counts
- [ ] Unit: PageRank returns expected top symbols for known graph topology
- [ ] Unit: `update_file()` replaces edges correctly
- [ ] Unit: `get_dependencies()` traverses correct depth and direction
- [ ] Unit: serialization round-trip preserves graph

---

### Story 3.3 — Implement Embedding Encoder

**As a** developer, **I want** a Jina embedding encoder, **so that** symbol signatures are vectorized for semantic search.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/index/embedding_encoder.py`

**Acceptance criteria:**
- [ ] Loads `jinaai/jina-code-embeddings-0.5b` via `transformers.AutoModel`
- [ ] Uses last-token pooling (not mean pooling — autoregressive architecture)
- [ ] Supports task-specific instruction prefixes (nl2code, code2code, techqa)
- [ ] Batch encoding with configurable batch size from settings
- [ ] Device selection from settings (cpu/cuda/mps)
- [ ] Returns `list[list[float]]` of 1024-dimensional vectors
- [ ] Raises `EmbeddingError` on model load or inference failure

**Dependencies:** 1.4, 1.5

**Tests:**
- [ ] Unit: mock model, verify correct prefix prepended for each query type
- [ ] Unit: batch splitting works for inputs larger than batch_size
- [ ] Integration: encode a known string, verify output dimensions are 1024

---

### Story 3.4 — Implement Semantic Index (LanceDB)

**As a** developer, **I want** a LanceDB-backed semantic index, **so that** symbol embeddings are stored and searchable.

**Complexity:** L

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/index/semantic_index.py`

**Acceptance criteria:**
- [ ] Implements `SemanticIndex` protocol
- [ ] Creates LanceDB database at `{cache_dir}/lance.db/`
- [ ] Table schema matches design spec §3.5 (PyArrow schema)
- [ ] `upsert_symbols()` embeds via encoder, upserts into LanceDB
- [ ] `remove_symbols()` deletes by qualified_name
- [ ] `search()` queries with task-appropriate instruction prefix, applies metadata filters
- [ ] `search_by_name()` uses full-text search index on `signature` and `docstring`
- [ ] Periodic compaction via `table.compact_files()` + `table.cleanup_old_versions()`
- [ ] Skips IVF-PQ index for datasets under 100K vectors (brute-force is fast enough)

**Dependencies:** 1.3, 1.4, 3.3

**Tests:**
- [ ] Unit: mock encoder, verify upsert constructs correct records
- [ ] Integration: upsert symbols → search → verify top result matches
- [ ] Integration: remove symbol → search → verify it's gone
- [ ] Integration: metadata filter restricts results correctly

---

## Phase 4: Assembly

Ranking fusion, token budget packing, disk hydration, XML rendering.

---

### Story 4.1 — Implement Ranking Fusion

**As a** developer, **I want** structural and semantic results fused with intent-aware weights, **so that** agents get optimally ranked context.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/ranking.py`

**Acceptance criteria:**
- [ ] Intent-based weight adjustment per design spec §3.6.3:
  - UNDERSTAND: semantic=0.5, structural=0.5
  - MODIFY: semantic=0.3, structural=0.7
  - NAVIGATE: semantic=0.2, structural=0.8
  - GENERATE: semantic=0.7, structural=0.3
- [ ] Each result set independently normalized to [0.0, 1.0]
- [ ] Symbols appearing in both sets get 1.2x boost (capped at 1.0)
- [ ] Query-level weight overrides (`structural_weight`, `semantic_weight`) respected
- [ ] Output sorted descending by fused score

**Dependencies:** 1.2, 1.6

**Tests:**
- [ ] Unit: known structural + semantic scores → expected fused order
- [ ] Unit: each intent produces different rankings for same inputs
- [ ] Unit: both-set bonus applied and capped correctly
- [ ] Unit: weight overrides take precedence over intent defaults

---

### Story 4.2 — Implement Token Budget Packing

**As a** developer, **I want** binary search token packing with signature-only overflow, **so that** the response fills the budget optimally.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/packing.py`

**Acceptance criteria:**
- [ ] If all chunks fit within budget, return all
- [ ] Binary search for maximum N chunks where `sum(tokens[0:N]) <= budget`
- [ ] After packing N full chunks, include next chunk as signature-only if it fits remaining budget
- [ ] Returns `(selected_chunks, tokens_used, chunks_remaining)`
- [ ] Token counting via tiktoken (model from settings)
- [ ] Raises `BudgetExceededError` if even the smallest chunk exceeds budget

**Dependencies:** 1.4, 1.5, 1.6

**Tests:**
- [ ] Unit: all fit → all returned
- [ ] Unit: exact budget match → all returned with 0 remaining
- [ ] Unit: overflow → correct number packed + signature-only stub
- [ ] Unit: zero-budget → `BudgetExceededError`

---

### Story 4.3 — Implement Disk Hydration

**As a** developer, **I want** source code read from disk at query time, **so that** full implementations are included in responses without storing bodies in the index.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/hydration.py`

**Acceptance criteria:**
- [ ] Read source file and extract lines `[start_line:end_line]` for each chunk
- [ ] Optionally include surrounding context (imports at file top)
- [ ] Handle file-not-found gracefully (symbol still indexed but source unavailable)
- [ ] Skip hydration when `include_source_code=False` (signatures-only mode)
- [ ] Detect and flag stale files (mtime changed since indexing)

**Dependencies:** 1.6

**Tests:**
- [ ] Unit: known file content → correct line range extracted
- [ ] Unit: missing file → `source_code=None`, no exception
- [ ] Unit: `include_source_code=False` → `source_code=None`

---

### Story 4.4 — Implement XML Renderer

**As a** developer, **I want** `ContextResponse` rendered as XML for LLM prompt injection, **so that** agents can consume context efficiently.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/renderer.py`

**Acceptance criteria:**
- [ ] Renders `<code_context>` root element with `tokens_used`, `budget`, `chunks`, `more_available` attributes
- [ ] Each chunk rendered as `<chunk>` element with `rank`, `relevance`, `source`, `symbol`, `kind`, `location` attributes
- [ ] Relationship comments (`# Calls:`, `# Called by:`) included before source code
- [ ] Signature-only chunks clearly marked
- [ ] Output matches design spec §3.6.5 format

**Dependencies:** 1.6

**Tests:**
- [ ] Unit: known chunks → expected XML string (snapshot test)
- [ ] Unit: empty response → valid XML with `chunks="0"`
- [ ] Unit: signature-only chunk rendered without body

---

### Story 4.5 — Implement Context Assembler

**As a** developer, **I want** the full query execution pipeline, **so that** agents get fused, budgeted, hydrated context from a single API call.

**Complexity:** L

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/assembly/context_assembler.py`

**Acceptance criteria:**
- [ ] Implements `ContextAssembler` protocol
- [ ] `query()` follows pipeline from design spec §3.6.6:
  1. Validate ContextQuery (at least one dimension)
  2. Parallel retrieval: semantic (LanceDB) + structural (PageRank)
  3. Direct results for explicit symbol_names/file_paths (highest priority)
  4. Ranking fusion
  5. Dependency expansion (walk graph N hops)
  6. Disk hydration
  7. Token budget packing
  8. Construct ContextResponse
- [ ] `get_symbol()` returns single CodeChunk by qualified name
- [ ] `get_dependencies()` returns dependency subgraph as CodeChunk list
- [ ] `get_repo_summary()` delegates to structural index
- [ ] `refresh_index()` re-indexes specified files or all files

**Dependencies:** 3.2, 3.4, 4.1, 4.2, 4.3, 4.4

**Tests:**
- [ ] Integration: index sample repo → query → verify response has expected chunks
- [ ] Unit: query validation rejects empty query
- [ ] Unit: direct symbol lookup bypasses search
- [ ] Unit: dependency expansion adds correct symbols

---

## Phase 5: Surface

MCP tools, CLI commands, and entry-point wiring.

---

### Story 5.1 — Implement MCP Tools

**As a** developer, **I want** 5 MCP tools exposed, **so that** AI agents can query code intelligence via the MCP protocol.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/surface/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/surface/mcp_tools.py`

**Acceptance criteria:**
- [ ] `code_context_search` → `assembler.query()` with NL query + filters
- [ ] `code_symbol_lookup` → `assembler.get_symbol()` with qualified name
- [ ] `code_dependency_graph` → `assembler.get_dependencies()` with symbol + depth + direction
- [ ] `code_repo_overview` → `assembler.get_repo_summary()`
- [ ] `code_index_refresh` → `assembler.refresh_index()` with optional file paths
- [ ] Each tool has comprehensive docstring for agent discovery
- [ ] Tool registration uses `@mcp.tool()` decorator (FastMCP)
- [ ] Response is JSON-serializable dict

**Dependencies:** 4.5

**Tests:**
- [ ] Unit: each tool constructs correct query and returns dict
- [ ] Integration: tool invocation against indexed sample repo returns valid response

---

### Story 5.2 — Implement CLI Commands

**As a** developer, **I want** `serve`, `index`, and `stats` CLI commands, **so that** the MCP server can be started and indexes managed from the terminal.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/surface/cli.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/__main__.py`

**Files to modify:**
- `packages/infra-codeintel/pyproject.toml` — add `[project.scripts]` entry

**Acceptance criteria:**
- [ ] `code-intel serve --repo . --transport stdio|sse --port 8420 --device cpu` starts MCP server
- [ ] `code-intel index --repo . --device cpu` runs one-time full index
- [ ] `code-intel stats --repo .` prints index statistics (files, symbols, languages, index age)
- [ ] All commands accept `--config` for per-project config file
- [ ] Click-based CLI (consistent with design spec §11.3)
- [ ] `python -m praecepta.infra.codeintel` works as alternative entry point

**Dependencies:** 5.1

**Tests:**
- [ ] Unit: CLI invocation with `click.testing.CliRunner`
- [ ] Unit: `--help` outputs expected options for each command

---

### Story 5.3 — Wire Lifespan Contribution

**As a** developer, **I want** code intelligence indexes loaded on app startup, **so that** queries are fast from the first request.

**Complexity:** S

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/lifespan.py`

**Files to modify:**
- `packages/infra-codeintel/pyproject.toml` — add entry point
- `packages/infra-codeintel/src/praecepta/infra/codeintel/__init__.py` — export contribution

**Acceptance criteria:**
- [ ] `LifespanContribution` with `priority=250` (after projections at 200)
- [ ] Startup: load serialized graph from disk, open LanceDB, optionally start file watcher
- [ ] Shutdown: stop file watcher, serialize graph, close LanceDB
- [ ] Entry point registered: `[project.entry-points."praecepta.lifespan"] codeintel = "praecepta.infra.codeintel:lifespan_contribution"`
- [ ] Follows `_persistence_lifespan` pattern (async context manager, try/yield/finally)

**Dependencies:** 3.2, 3.4, 1.4

**Tests:**
- [ ] Unit: lifespan context manager calls startup/shutdown in correct order
- [ ] Unit: `lifespan_contribution.priority == 250`

---

### Story 5.4 — Update Package Exports

**As a** developer, **I want** the package `__init__.py` to export all public APIs, **so that** consumers have a clean import surface.

**Complexity:** S

**Files to modify:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/__init__.py`

**Acceptance criteria:**
- [ ] Exports: `CodeIntelSettings`, `get_settings`, `CodeIntelError` (and subclasses), all protocols, key types (`Tag`, `SymbolSignature`, `QueryIntent`), assembly schemas, `lifespan_contribution`
- [ ] `__all__` list defined and alphabetically sorted
- [ ] Module docstring present

**Dependencies:** All Phase 1–5 stories

**Tests:** None (verified by import in other tests)

---

## Phase 6: Reactivity

File watcher for incremental updates.

---

### Story 6.1 — Implement File Watcher

**As a** developer, **I want** file system changes detected and debounced, **so that** the index stays fresh during active development.

**Complexity:** M

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/watcher/__init__.py`
- `packages/infra-codeintel/src/praecepta/infra/codeintel/watcher/file_watcher.py`

**Acceptance criteria:**
- [ ] Implements `FileWatcher` protocol
- [ ] Uses `watchdog` for recursive file system monitoring
- [ ] Debounces rapid changes (configurable, default 300ms from settings)
- [ ] Respects `.gitignore` patterns and `exclude_patterns` from settings
- [ ] Produces `FileEvent` objects with `created`, `modified`, `deleted` types
- [ ] `start()` begins watching, `stop()` cleanly shuts down observer thread
- [ ] Only triggers for files with supported language extensions

**Dependencies:** 1.2, 1.4, 2.1

**Tests:**
- [ ] Unit: debounce groups rapid events
- [ ] Unit: gitignore patterns filter correctly
- [ ] Integration: create/modify/delete file → events emitted with correct types

---

### Story 6.2 — Implement Incremental Update Pipeline

**As a** developer, **I want** file changes to trigger targeted re-indexing, **so that** the full index doesn't need rebuilding on every edit.

**Complexity:** L

**Files to create:**
- `packages/infra-codeintel/src/praecepta/infra/codeintel/watcher/incremental_pipeline.py`

**Acceptance criteria:**
- [ ] On `modified`: incremental parse → diff tags → update structural index edges → re-embed changed symbols in LanceDB → recompute PageRank
- [ ] On `created`: full parse → add to both indexes
- [ ] On `deleted`: remove from both indexes
- [ ] Tag diffing: compare old tags vs new tags to identify added/removed/modified symbols
- [ ] Recompute PageRank after structural index update (global, but fast for typical repos)
- [ ] Update disk cache (serialized graph + diskcache)
- [ ] Callback integrates with `FileWatcher.on_change`

**Dependencies:** 6.1, 2.4, 3.1, 3.2, 3.4

**Tests:**
- [ ] Integration: modify file → verify structural index updated
- [ ] Integration: delete file → verify symbols removed from both indexes
- [ ] Integration: add file → verify symbols appear in search results
- [ ] Unit: tag diff correctly identifies added/removed/modified symbols

---

## Dependency Graph

```
Phase 1: Foundation
  1.1 ──► 1.2 ──► 1.3
  1.1 ──► 1.4
  1.1 ──► 1.5
  1.2 ──► 1.6

Phase 2: Parsing
  1.1 ──► 2.1
  2.1 ──► 2.2 ──► 2.3 ──► 2.4 ──► 2.5
                  (also depends on 1.2, 1.5)

Phase 3: Indexing
  2.4 ──► 3.1
  3.1 ──► 3.2
  1.4 ──► 3.3 ──► 3.4
           (also depends on 1.5)

Phase 4: Assembly
  1.6 ──► 4.1
  1.6 ──► 4.2
  1.6 ──► 4.3
  1.6 ──► 4.4
  3.2 + 3.4 + 4.1-4.4 ──► 4.5

Phase 5: Surface
  4.5 ──► 5.1 ──► 5.2
  3.2 + 3.4 ──► 5.3
  All ──► 5.4

Phase 6: Reactivity
  1.2 + 1.4 + 2.1 ──► 6.1
  6.1 + 2.4 + 3.1 + 3.2 + 3.4 ──► 6.2
```

---

## Future Epics (Deferred)

### Analytics Projection
- PostgreSQL + pgvector sync (design spec §3.8)
- Time-series snapshots, agent query logging
- Neo4j extension for cross-knowledge-graph traversal
- **Trigger:** When a concrete dashboard/analytics use case emerges

### Additional Language Support
- C#, Go, Rust, Java `.scm` query files
- Extend `LANGUAGE_EXTENSIONS` registry
- **Trigger:** When a project using those languages is onboarded

### Docker Distribution
- Dockerfile with bundled model weights (design spec §11.8)
- `docker-compose.yml` for air-gapped deployment
- **Trigger:** When government/air-gapped client deployment is needed

### Performance Optimization
- IVF-PQ index for repos >100K vectors
- Parallel file parsing with thread pool
- Memory-mapped graph for very large repos
- **Trigger:** When repos exceed 50K files
