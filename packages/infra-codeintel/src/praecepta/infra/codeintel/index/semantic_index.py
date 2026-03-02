"""LanceDB-backed semantic index for symbol embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import lancedb  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]

from praecepta.infra.codeintel.settings import get_settings

if TYPE_CHECKING:
    from praecepta.infra.codeintel.types import SymbolSignature

TABLE_NAME = "symbols"

SCHEMA = pa.schema(
    [
        pa.field("qualified_name", pa.string()),
        pa.field("name", pa.string()),
        pa.field("kind", pa.string()),
        pa.field("language", pa.string()),
        pa.field("file_path", pa.string()),
        pa.field("start_line", pa.int32()),
        pa.field("end_line", pa.int32()),
        pa.field("signature", pa.string()),
        pa.field("docstring", pa.string()),
        pa.field("parent_symbol", pa.string()),
        pa.field("embedding_text", pa.string()),
        pa.field("embedding", pa.list_(pa.float32(), 1024)),
        pa.field("token_count_estimate", pa.int32()),
        pa.field("last_modified", pa.timestamp("us", tz="UTC")),
    ]
)


class LanceDBSemanticIndex:
    """SemanticIndex implementation using LanceDB embedded vector store."""

    def __init__(
        self,
        db_path: Path | None = None,
        encoder: Any = None,  # JinaEmbeddingEncoder or mock
    ) -> None:
        settings = get_settings()
        path = db_path or Path(settings.repo_root) / settings.cache_dir / "lance.db"
        self._db = lancedb.connect(str(path))
        self._encoder = encoder
        self._ensure_table()

    def _ensure_table(self) -> None:
        if TABLE_NAME not in self._db.list_tables():
            self._db.create_table(TABLE_NAME, schema=SCHEMA)
        self._table = self._db.open_table(TABLE_NAME)

    async def upsert_symbols(self, symbols: list[SymbolSignature]) -> int:
        if not symbols:
            return 0

        texts = [s.embedding_text for s in symbols]
        vectors = self._encoder.encode(texts, query_type="code2code")

        records = []
        for sym, vec in zip(symbols, vectors, strict=True):
            records.append(
                {
                    "qualified_name": sym.qualified_name,
                    "name": sym.name,
                    "kind": sym.kind,
                    "language": sym.language,
                    "file_path": sym.file_path,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                    "signature": sym.signature,
                    "docstring": sym.docstring or "",
                    "parent_symbol": sym.parent_symbol or "",
                    "embedding_text": sym.embedding_text,
                    "embedding": vec,
                    "token_count_estimate": sym.token_count_estimate,
                    "last_modified": sym.last_modified,
                }
            )

        # Delete existing records with same qualified_names, then add
        names = [r["qualified_name"] for r in records]
        try:
            # Build SQL-safe IN clause
            escaped = ", ".join(f"'{n}'" for n in names)
            self._table.delete(f"qualified_name IN ({escaped})")
        except Exception:
            pass  # table may be empty or no matching rows
        self._table.add(records)
        return len(records)

    async def remove_symbols(self, qualified_names: list[str]) -> int:
        if not qualified_names:
            return 0
        escaped = ", ".join(f"'{n}'" for n in qualified_names)
        self._table.delete(f"qualified_name IN ({escaped})")
        return len(qualified_names)

    async def search(
        self,
        query_text: str,
        query_type: Literal["nl2code", "code2code", "techqa"] = "nl2code",
        top_k: int = 20,
        filters: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        vectors = self._encoder.encode([query_text], query_type=query_type)
        query_vec = vectors[0]

        search = self._table.search(query_vec).limit(top_k)

        if filters:
            where_clauses = [f"{k} = '{v}'" for k, v in filters.items()]
            search = search.where(" AND ".join(where_clauses))

        results = search.to_list()
        return [(r["qualified_name"], float(r.get("_distance", 0.0))) for r in results]

    async def search_by_name(self, symbol_name: str, top_k: int = 10) -> list[str]:
        results = self._table.search().where(f"name = '{symbol_name}'").limit(top_k).to_list()
        return [r["qualified_name"] for r in results]

    def compact(self) -> None:
        self._table.compact_files()
        self._table.cleanup_old_versions()

    def close(self) -> None:
        pass
