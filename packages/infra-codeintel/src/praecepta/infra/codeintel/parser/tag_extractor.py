"""Extract tags from tree-sitter syntax trees using .scm queries."""

from __future__ import annotations

import importlib.resources
from typing import TYPE_CHECKING, Literal, cast

import tree_sitter_language_pack as tslp
from tree_sitter import Node, Query, QueryCursor

if TYPE_CHECKING:
    from pathlib import Path

from praecepta.infra.codeintel.exceptions import UnsupportedLanguageError
from praecepta.infra.codeintel.parser.language_registry import (
    SUPPORTED_LANGUAGES,
    as_language_name,
)
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

        ts_language = tslp.get_language(as_language_name(language))
        query = Query(ts_language, query_text)
        cursor = QueryCursor(query)

        # tree is typed as object in the protocol; access root_node via getattr
        root_node = getattr(tree, "root_node", None)
        if root_node is None:
            return []

        captures_dict: dict[str, list[Node]] = cursor.captures(root_node)

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

            kind_str = parts[1]  # "definition" or "reference"
            if kind_str not in ("definition", "reference"):
                continue

            # Narrowed literal kind for the Tag type
            tag_kind = cast("Literal['definition', 'reference']", kind_str)
            # sub_kind is the third segment if present (e.g. "function", "call", "import")
            sub_kind = parts[2] if len(parts) > 2 else ""

            for node in nodes:
                node_text = getattr(node, "text", b"")
                name = node_text.decode("utf-8") if isinstance(node_text, bytes) else str(node_text)

                start_point = getattr(node, "start_point", (0, 0))
                line: int = start_point[0] + 1  # 0-indexed to 1-indexed

                tags.append(
                    Tag(
                        rel_fname=rel_path,
                        fname=str(file_path),
                        line=line,
                        name=name,
                        kind=tag_kind,
                        sub_kind=sub_kind,
                    )
                )

        return tags
