"""NetworkX-backed structural index for file-level dependency graphs."""

from __future__ import annotations

import logging
import pickle
from collections import deque
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

logger = logging.getLogger(__name__)

# Increment when the saved payload schema changes to avoid loading stale data.
_PICKLE_VERSION = 1

import networkx as nx  # type: ignore[import-untyped]

from praecepta.infra.codeintel.assembly.schemas import RepoSummary

if TYPE_CHECKING:
    from pathlib import Path

    from praecepta.infra.codeintel.types import Tag


def _normalize(path: Path | str) -> str:
    """Normalize a path to a forward-slash string for cross-platform consistency."""
    return str(PurePosixPath(str(path).replace("\\", "/")))


def _guess_language(file_path: str) -> str:
    """Infer language from file extension."""
    from pathlib import PurePosixPath

    suffix = PurePosixPath(file_path).suffix.lower()
    mapping: dict[str, str] = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".cs": "csharp",
        ".rb": "ruby",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
    }
    return mapping.get(suffix, "unknown")


class NetworkXStructuralIndex:
    """Structural index using a NetworkX directed graph.

    Nodes are file paths (strings). Edges represent cross-file references
    with a ``weight`` attribute tracking reference count and a ``symbols``
    list recording which symbol names created the edge.
    """

    def __init__(self, cache_dir: Path | None = None, damping: float | None = None) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._definition_index: dict[str, str] = {}
        self._pagerank_cache: dict[str, float] | None = None
        self._cache_dir = cache_dir
        # Resolve damping factor: explicit arg > settings value
        if damping is not None:
            self._damping = damping
        else:
            from praecepta.infra.codeintel.settings import get_settings

            self._damping = get_settings().pagerank_damping

    # ------------------------------------------------------------------
    # Build / mutate
    # ------------------------------------------------------------------

    def build(self, all_tags: dict[Path, list[Tag]]) -> None:
        """Build the full graph from a complete tag set."""
        self._graph.clear()
        self._definition_index = {}

        # First pass: add nodes and register definitions
        for file_path, tags in all_tags.items():
            fp_str = _normalize(file_path)
            defs = [t for t in tags if t.kind == "definition"]
            language = _guess_language(fp_str)

            self._graph.add_node(fp_str, symbol_count=len(defs), language=language)

            for t in defs:
                self._definition_index[t.name] = fp_str

        # Second pass: create edges for cross-file references
        for file_path, tags in all_tags.items():
            fp_str = _normalize(file_path)
            refs = [t for t in tags if t.kind == "reference"]
            for ref in refs:
                target_file = self._definition_index.get(ref.name)
                if target_file and target_file != fp_str:
                    if self._graph.has_edge(fp_str, target_file):
                        self._graph[fp_str][target_file]["weight"] += 1
                        symbols: list[str] = self._graph[fp_str][target_file]["symbols"]
                        if ref.name not in symbols:
                            symbols.append(ref.name)
                    else:
                        self._graph.add_edge(fp_str, target_file, weight=1, symbols=[ref.name])

        self._invalidate_pagerank()

    def update_file(self, file_path: Path, new_tags: list[Tag]) -> None:
        """Replace all edges originating from *file_path* with edges derived from *new_tags*."""
        fp_str = _normalize(file_path)

        # Remove outgoing edges from this file
        if fp_str in self._graph:
            successors = list(self._graph.successors(fp_str))
            for succ in successors:
                self._graph.remove_edge(fp_str, succ)

        # Remove old definitions owned by this file from the definition index
        stale_keys = [k for k, v in self._definition_index.items() if v == fp_str]
        for k in stale_keys:
            del self._definition_index[k]

        # Re-register definitions
        defs = [t for t in new_tags if t.kind == "definition"]
        language = _guess_language(fp_str)

        if fp_str not in self._graph:
            self._graph.add_node(fp_str, symbol_count=len(defs), language=language)
        else:
            self._graph.nodes[fp_str]["symbol_count"] = len(defs)
            self._graph.nodes[fp_str]["language"] = language

        for t in defs:
            self._definition_index[t.name] = fp_str

        # Re-add outgoing edges
        refs = [t for t in new_tags if t.kind == "reference"]
        for ref in refs:
            target_file = self._definition_index.get(ref.name)
            if target_file and target_file != fp_str:
                if self._graph.has_edge(fp_str, target_file):
                    self._graph[fp_str][target_file]["weight"] += 1
                    symbols: list[str] = self._graph[fp_str][target_file]["symbols"]
                    if ref.name not in symbols:
                        symbols.append(ref.name)
                else:
                    self._graph.add_edge(fp_str, target_file, weight=1, symbols=[ref.name])

        self._invalidate_pagerank()

    def remove_file(self, file_path: Path) -> None:
        """Remove a file node and all associated edges."""
        fp_str = _normalize(file_path)
        if fp_str in self._graph:
            self._graph.remove_node(fp_str)

        # Clean up definition index
        stale_keys = [k for k, v in self._definition_index.items() if v == fp_str]
        for k in stale_keys:
            del self._definition_index[k]

        self._invalidate_pagerank()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_ranked_symbols(
        self,
        personalization: dict[str, float] | None = None,
        top_k: int = 50,
    ) -> list[tuple[str, float]]:
        """Return file nodes ranked by PageRank score."""
        if self._graph.number_of_nodes() == 0:
            return []

        if self._pagerank_cache is None:
            pr_kwargs: dict[str, object] = {"alpha": self._damping}

            if personalization is not None:
                # Filter to valid nodes only
                valid = {k: v for k, v in personalization.items() if k in self._graph}
                if valid:
                    pr_kwargs["personalization"] = valid

            self._pagerank_cache = nx.pagerank(self._graph, **pr_kwargs)
        elif personalization is not None:
            # Personalization changes defeat caching — recompute
            valid = {k: v for k, v in personalization.items() if k in self._graph}
            pr_kwargs = {"alpha": self._damping}
            if valid:
                pr_kwargs["personalization"] = valid
            scores: dict[str, float] = nx.pagerank(self._graph, **pr_kwargs)
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            return ranked[:top_k]

        ranked = sorted(self._pagerank_cache.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def get_dependencies(
        self,
        qualified_name: str,
        direction: Literal["callers", "callees", "both"] = "both",
        depth: int = 1,
    ) -> list[tuple[str, str]]:
        """BFS traversal of dependency edges up to *depth* hops."""
        qualified_name = _normalize(qualified_name)
        if qualified_name not in self._graph:
            return []

        edges: list[tuple[str, str]] = []
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(qualified_name, 0)])
        visited.add(qualified_name)

        while queue:
            node, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            neighbors: list[str] = []
            if direction in ("callers", "both"):
                for pred in self._graph.predecessors(node):
                    edges.append((pred, node))
                    neighbors.append(pred)
            if direction in ("callees", "both"):
                for succ in self._graph.successors(node):
                    edges.append((node, succ))
                    neighbors.append(succ)

            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_depth + 1))

        return edges

    def get_repo_summary(self) -> RepoSummary:
        """Aggregate graph metadata into a :class:`RepoSummary`."""
        total_files = self._graph.number_of_nodes()
        total_symbols = sum(
            int(data.get("symbol_count", 0)) for _, data in self._graph.nodes(data=True)
        )

        languages: dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            lang = str(data.get("language", "unknown"))
            languages[lang] = languages.get(lang, 0) + 1

        # Top symbols by PageRank (reuse cached if available)
        if total_files > 0:
            ranked = self.get_ranked_symbols(top_k=10)
            top_symbols = [name for name, _ in ranked]
        else:
            top_symbols = []

        return RepoSummary(
            total_files=total_files,
            total_symbols=total_symbols,
            languages=languages,
            entry_points=[],
            top_symbols_by_pagerank=top_symbols,
            module_clusters=[],
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Pickle the graph and definition index to *cache_dir*/graph.pkl."""
        if self._cache_dir is None:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_dir / "graph.pkl"
        with path.open("wb") as f:
            pickle.dump(
                {
                    "version": _PICKLE_VERSION,
                    "graph": self._graph,
                    "definition_index": self._definition_index,
                },
                f,
            )

    def load(self) -> None:
        """Restore the graph and definition index from *cache_dir*/graph.pkl.

        If the saved file has a mismatched version marker the file is ignored
        and the index starts empty (a fresh re-index will rebuild it).
        """
        if self._cache_dir is None:
            return
        path = self._cache_dir / "graph.pkl"
        if not path.exists():
            return
        with path.open("rb") as f:
            data: dict[str, object] = pickle.load(f)

        if data.get("version") != _PICKLE_VERSION:
            logger.warning(
                "structural index: graph.pkl version mismatch "
                "(expected %d, got %s) — discarding stale index; "
                "a full re-index will rebuild it",
                _PICKLE_VERSION,
                data.get("version"),
            )
            return

        self._graph = data["graph"]  # networkx untyped; mypy treats nx.DiGraph as Any
        self._definition_index = data["definition_index"]  # type: ignore[assignment]
        self._invalidate_pagerank()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _invalidate_pagerank(self) -> None:
        self._pagerank_cache = None
