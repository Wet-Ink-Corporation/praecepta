"""Extract tags from tree-sitter syntax trees using .scm queries."""

from __future__ import annotations

import importlib.resources
from typing import TYPE_CHECKING

import tree_sitter_language_pack as tslp

if TYPE_CHECKING:
    from pathlib import Path
from tree_sitter import Query, QueryCursor

from praecepta.infra.codeintel.exceptions import UnsupportedLanguageError
from praecepta.infra.codeintel.parser.language_registry import SUPPORTED_LANGUAGES
from praecepta.infra.codeintel.types import Tag


class TagExtractor:
    """Runs .scm tag queries against tree-sitter Trees."""

    def __init__(self) -> None:
        self._query_cache: dict[str, str] = {}

    def _load_query(self, language: str) -> str:
        """Load .scm query text for a language via importlib.resources."""
        if language not in SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(language=language)

        if language not in self._query_cache:
            queries_pkg = importlib.resources.files("praecepta.infra.codeintel.parser.queries")
            scm_file = queries_pkg.joinpath(f"{language}.scm")
            self._query_cache[language] = scm_file.read_text(encoding="utf-8")

        return self._query_cache[language]

    def extract_tags_from_tree(
        self,
        tree: object,  # tree_sitter.Tree
        language: str,
        file_path: Path,
        rel_path: str,
    ) -> list[Tag]:
        """Run .scm query against tree and return Tag objects."""
        query_text = self._load_query(language)

        # Use Query + QueryCursor pattern (same as test_scm_queries.py)
        ts_language = tslp.get_language(language)
        query = Query(ts_language, query_text)
        cursor = QueryCursor(query)
        captures_dict = cursor.captures(tree.root_node)  # type: ignore[union-attr]

        # Build tags from captures where name starts with "name."
        tags: list[Tag] = []

        for capture_name, nodes in captures_dict.items():
            if not capture_name.startswith("name."):
                continue

            # Parse kind from capture name: "name.definition.*" -> "definition",
            # "name.reference.*" -> "reference"
            parts = capture_name.split(".")
            if len(parts) < 2:
                continue

            kind = parts[1]  # "definition" or "reference"
            if kind not in ("definition", "reference"):
                continue

            for node in nodes:
                name = (
                    node.text.decode("utf-8")  # type: ignore[union-attr]
                    if isinstance(node.text, bytes)  # type: ignore[union-attr]
                    else str(node.text)  # type: ignore[union-attr]
                )
                line = node.start_point[0] + 1  # 0-indexed to 1-indexed

                tags.append(
                    Tag(
                        rel_fname=rel_path,
                        fname=str(file_path),
                        line=line,
                        name=name,
                        kind=kind,
                    )
                )

        return tags
