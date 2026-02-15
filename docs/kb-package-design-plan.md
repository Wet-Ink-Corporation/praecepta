# KB Package Design Document Plan

Write a detailed design specification for `packages/kb` — a workspace package shipping a pre-built Docling-indexed SQLite knowledge base with an embedded MCP server, FTS5 keyword search, and sqlite-vec vector similarity search.

## Resolved Decisions

| Question | Resolution |
|----------|------------|
| DB location | Pre-built `kb.db` ships as a **package data artifact** inside `packages/kb/`; CI builds it from `_kb/` sources; git hook keeps dev copy current |
| Pre-baked DB | Yes — consumers install the package and get the DB with all embeddings. No indexing at install time |
| Runtime embedding | `sentence-transformers` is a **runtime dep** (always included). Query strings embedded at MCP serve time for `search_semantic` |
| Model loading | **Eager load on `serve` startup** — model downloads on first `praecepta-kb serve` (~30-60s), cached in `~/.cache/huggingface/`, ~2-3s on subsequent starts. Loaded before accepting MCP connections so queries never block on download |
| MCP transport | **Both** stdio (IDE integration) and streamable-http (remote). Console script entry point for activation |
| Namespace | `praecepta.kb` (consistent with `praecepta.*` pattern) |
| CI integration | Yes — quality workflow builds the DB and runs search tests |
| Chunk size | 256 max tokens for `HybridChunker` |

## Design Document Outline

The design doc will live at `_kb/design/references/con-kb-package-design.md` (consistent with existing `con-*` convention). It will cover:

### 1. Overview & Goals
- Replace file-read navigation protocol with structured retrieval via MCP
- Markdown in `_kb/` remains source of truth; SQLite is a derived, pre-built artifact
- Ship a **zero-config experience**: `pip install praecepta-kb` → `praecepta-kb serve` → MCP tools available
- Support incremental dev updates via git hooks; CI does full rebuild for releases

### 2. Package Structure
```
packages/kb/
  pyproject.toml                  # hatchling, console script, package-data for kb.db
  src/praecepta/kb/
    __init__.py
    py.typed
    data/
      kb.db                       # pre-built artifact (gitignored; CI-built, included in wheel)
    indexer/
      __init__.py
      pipeline.py                 # Docling parse → chunk → embed → SQLite write
      chunker.py                  # HybridChunker config (256 tokens, MarkdownTableSerializer)
      embedder.py                 # sentence-transformers wrapper, model singleton
    db/
      __init__.py
      schema.py                   # Raw DDL for documents, chunks, chunks_fts, vec_chunks
      connection.py               # Context manager, sqlite-vec extension loading, DB location resolution
      queries.py                  # Typed query functions (FTS5 + vec KNN + metadata)
    server/
      __init__.py
      app.py                      # MCPServer with @mcp.tool() / @mcp.resource() / @mcp.prompt()
    hooks/
      __init__.py
      post_commit.py              # post-commit hook entry point (filters _kb/ changes)
      diff.py                     # git diff parser → added/modified/deleted file sets
    cli.py                        # Entry point: build | serve | hook-install
  tests/
    test_schema.py
    test_indexer.py
    test_queries.py
    test_mcp_tools.py
```

### 3. Distribution Model (Build-Time vs Runtime)

```
                    ┌──────────────────────────────┐
 BUILD TIME         │  _kb/*.md (source of truth)  │
 (CI or dev)        └──────────┬───────────────────┘
                               │
                    Docling parse → HybridChunker (256 tok)
                               │
                    sentence-transformers embed (all-MiniLM-L6-v2)
                               │
                    ┌──────────▼───────────────────┐
                    │  kb.db  (documents, chunks,   │
                    │          chunks_fts, vec_chunks)│
                    └──────────┬───────────────────┘
                               │
                    hatchling wheel build (kb.db as package data)
                               │
                    ┌──────────▼───────────────────┐
 RUNTIME            │  pip install praecepta-kb     │
 (consumer)         │  praecepta-kb serve           │
                    └──────────┬───────────────────┘
                               │
                    MCPServer (stdio or streamable-http)
                               │
                    ┌──────────▼───────────────────┐
                    │  search_keyword  (FTS5)       │
                    │  search_semantic (vec KNN)    │◄── query embedding at runtime
                    │  get_document / get_chunk     │
                    │  list_domains                 │
                    └──────────────────────────────┘
```

- **Build time**: Docling + sentence-transformers process `_kb/` markdown → `kb.db`
- **Runtime**: MCP server reads `kb.db`; only `search_semantic` needs the embedding model (to embed the query string)
- **Package data**: `kb.db` included in the wheel via hatchling `[tool.hatch.build]` config; gitignored in source

### 4. Client Activation

```toml
# pyproject.toml
[project.scripts]
praecepta-kb = "praecepta.kb.cli:main"
```

Consumer MCP configuration (e.g. Windsurf `mcp_config.json`):
```json
{
  "mcpServers": {
    "praecepta-kb": {
      "command": "praecepta-kb",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

Or for remote/shared access:
```bash
praecepta-kb serve --transport http --port 8765
```

### 5. SQLite Schema Design

```sql
CREATE TABLE documents (
    id           INTEGER PRIMARY KEY,
    path         TEXT NOT NULL UNIQUE,   -- relative to _kb/
    domain       TEXT,                   -- "ddd-patterns", "decisions", etc.
    doc_type     TEXT,                   -- "brief", "reference", "decision", "index"
    title        TEXT,                   -- first H1
    content_hash TEXT NOT NULL,          -- SHA-256 (change detection)
    indexed_at   TEXT NOT NULL           -- ISO-8601
);

CREATE TABLE chunks (
    id           INTEGER PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,       -- ordinal within document
    heading      TEXT,                   -- nearest parent heading
    text         TEXT NOT NULL,
    meta         TEXT,                   -- JSON: labels, cross-refs, PADR IDs
    UNIQUE(document_id, chunk_index)
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text, heading, content=chunks, content_rowid=id
);

CREATE VIRTUAL TABLE vec_chunks USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding float[384]                -- all-MiniLM-L6-v2 dimension
);
```

Key decisions:
- **`path` as unique key** — 1:1 filesystem mapping, natural dedup
- **`content_hash`** — git hook + CI skip unchanged files
- **`ON DELETE CASCADE`** — re-index = delete doc → cascade chunks → reinsert
- **FTS5 external content** (`content=chunks`) — no text duplication
- **384-dim vectors** — matches `all-MiniLM-L6-v2`; rebuild required on model change

### 6. Indexing Pipeline
- **Parse**: Docling `MarkdownDocumentBackend` for `.md`; extensible to PDF later
- **Chunk**: `HybridChunker(max_tokens=256)` + `MarkdownTableSerializer`
- **Embed**: `SentenceTransformer("all-MiniLM-L6-v2")` — batch encode all chunks per document
- **Write**: Single transaction per document: delete old → insert new → update hash
- **Full rebuild**: `praecepta-kb build` — drops and recreates all tables
- **Incremental**: Git hook or `praecepta-kb build --incremental` — hash comparison

### 7. Git Hook Integration
- **Hook**: `post-commit` (non-blocking, dev-only)
- **Trigger**: Only when `_kb/**` files appear in `git diff --name-only HEAD~1 HEAD`
- **Added/Modified**: Re-index (delete old chunks for path → parse → chunk → embed → insert)
- **Deleted**: `DELETE FROM documents WHERE path = ?` (cascade)
- **Install**: `praecepta-kb hook-install` → writes `.git/hooks/post-commit`
- **Idempotency**: `content_hash` comparison skips unchanged files
- **Edge cases**: Renames = delete + add; binary files skipped

### 8. MCP Server Tools

| Tool | Parameters | Returns |
|------|------------|---------|
| `search_keyword` | `query`, `domain?`, `limit?` | Ranked chunks with FTS5 snippets, doc path, heading |
| `search_semantic` | `query`, `domain?`, `k?` | Chunks ranked by vector distance (query embedded at runtime) |
| `get_document` | `path` | Document metadata + all chunk texts |
| `get_chunk` | `chunk_id` | Chunk text, heading, parent doc path, metadata |
| `list_domains` | — | Domain names + document counts |

Resources & Prompts:
- `kb://manifest` → MANIFEST.md content
- `kb://domain/{name}` → domain BRIEF content
- `navigate_kb` prompt → navigation prompt from manifest + search index

### 9. Complexity Assessment

| Component | Effort | Risk |
|-----------|--------|------|
| SQLite schema + connection | Low | Low |
| Docling markdown parsing | Low | Low |
| HybridChunker integration | Medium | Low |
| sentence-transformers (build + runtime) | Low | Medium (model download) |
| sqlite-vec integration | Medium | Medium (Windows extension loading) |
| FTS5 keyword search | Low | Low |
| MCP server (5 tools + resources) | Medium | Low |
| Git hook (post-commit) | Medium | Medium (cross-platform) |
| CLI + console script | Low | Low |
| CI build step + wheel packaging | Medium | Low |
| **Total** | **~3-4 days** | **Medium** |

### 10. Dependencies
```toml
[project]
dependencies = [
    "docling>=2.0",
    "docling-core>=2.0",
    "sentence-transformers>=3.0",
    "sqlite-vec>=0.1",
    "mcp>=1.0",
]
```

## Implementation Steps

1. **Write the design doc** at `_kb/design/references/con-kb-package-design.md` covering all sections above
2. **Add PADR-123** (next available number) to `_kb/decisions/patterns/` for the architectural decision
3. **Update `_kb/design/BRIEF.md`** reference index to link the new doc
4. **Update `_kb/SEARCH_INDEX.md`** with KB package keywords (docling, sqlite, mcp, vector, embedding, chunking)
5. **Update `_kb/MANIFEST.md`** — no new domain needed; links go under Design collection
