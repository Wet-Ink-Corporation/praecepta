"""Semantic extractor — enriches parsed tags into SymbolSignature objects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import tiktoken

from praecepta.infra.codeintel.types import SymbolRelationship, SymbolSignature, Tag

if TYPE_CHECKING:
    from pathlib import Path

# Node type constants for Python CST
_FUNC_DEF = "function_definition"
_CLASS_DEF = "class_definition"
_DECORATED_DEF = "decorated_definition"

# Map of tree-sitter node types to symbol kinds
_NODE_KIND_MAP: dict[str, str] = {
    _FUNC_DEF: "function",
    _CLASS_DEF: "class",
}


def _node_text(node: object) -> str:
    """Extract UTF-8 text from a tree-sitter node."""
    text = getattr(node, "text", b"")
    if isinstance(text, bytes):
        return text.decode("utf-8")
    return str(text)


def _find_definition_node(root: object, target_line: int, name: str) -> object | None:
    """Find a definition node for the given name at the given 0-indexed line.

    Recursively searches the tree for function_definition or class_definition
    (or decorated_definition wrapping them) whose identifier child matches
    *name* and whose start line matches *target_line*.
    """
    _DEF_TYPES = {_FUNC_DEF, _CLASS_DEF, _DECORATED_DEF}

    def _search(node: object) -> object | None:
        node_type = getattr(node, "type", "")
        if node_type in _DEF_TYPES:
            # For decorated_definition, check the inner def/class
            inner = _get_definition_node(node) if node_type == _DECORATED_DEF else node
            # Check if identifier child matches name on the target line
            for child in getattr(inner, "children", []):
                if getattr(child, "type", "") == "identifier":
                    child_line: int = getattr(child, "start_point", (0, 0))[0]
                    if _node_text(child) == name and child_line == target_line:
                        return node
                    break  # only check first identifier

        # Recurse into children
        for child in getattr(node, "children", []):
            result = _search(child)
            if result is not None:
                return result
        return None

    return _search(root)


def _get_definition_node(node: object) -> object:
    """Unwrap a decorated_definition to get the inner definition node."""
    if getattr(node, "type", "") == _DECORATED_DEF:
        for child in getattr(node, "children", []):
            child_type = getattr(child, "type", "")
            if child_type in (_FUNC_DEF, _CLASS_DEF):
                return child
    return node


def _get_decorators(node: object) -> list[str]:
    """Extract decorator strings from a decorated_definition node."""
    decorators: list[str] = []
    if getattr(node, "type", "") == _DECORATED_DEF:
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "decorator":
                decorators.append(_node_text(child))
    return decorators


def _get_parent_class(node: object) -> str | None:
    """Walk up parent chain to find enclosing class_definition, return its name."""
    current: object | None = getattr(node, "parent", None)
    while current is not None:
        if getattr(current, "type", "") == _CLASS_DEF:
            for child in getattr(current, "children", []):
                if getattr(child, "type", "") == "identifier":
                    return _node_text(child)
        # Also check if parent is a decorated class
        if getattr(current, "type", "") == _DECORATED_DEF:
            for child in getattr(current, "children", []):
                if getattr(child, "type", "") == _CLASS_DEF:
                    for grandchild in getattr(child, "children", []):
                        if getattr(grandchild, "type", "") == "identifier":
                            return _node_text(grandchild)
        current = getattr(current, "parent", None)
    return None


def _extract_signature(def_node: object) -> str:
    """Extract the full signature line (def name(...) -> type:) from a definition node."""
    node_type = getattr(def_node, "type", "")
    if node_type == _FUNC_DEF:
        # Build signature from children up to the body block
        parts: list[str] = []
        for child in getattr(def_node, "children", []):
            if getattr(child, "type", "") == "block":
                break
            parts.append(_node_text(child))
        return " ".join(parts).replace(" (", "(").replace(" )", ")").replace(" :", ":")
    elif node_type == _CLASS_DEF:
        parts = []
        for child in getattr(def_node, "children", []):
            if getattr(child, "type", "") in ("block", "body"):
                break
            parts.append(_node_text(child))
        return " ".join(parts).replace(" (", "(").replace(" )", ")").replace(" :", ":")
    return ""


def _strip_string_quotes(raw: str) -> str:
    """Strip surrounding quotes from a string literal."""
    for quote in ('"""', "'''"):
        if raw.startswith(quote) and raw.endswith(quote):
            return raw[3:-3].strip()
    for quote in ('"', "'"):
        if raw.startswith(quote) and raw.endswith(quote):
            return raw[1:-1].strip()
    return raw.strip()


def _extract_docstring(def_node: object) -> str | None:
    """Extract the docstring from a function or class definition.

    Handles two tree-sitter patterns:
    - block > expression_statement > string  (functions)
    - block > string  (classes, depending on tree-sitter version)
    """
    for child in getattr(def_node, "children", []):
        if getattr(child, "type", "") == "block":
            block_children = getattr(child, "children", [])
            for block_child in block_children:
                bt = getattr(block_child, "type", "")
                # Pattern 1: direct string child of block
                if bt == "string":
                    return _strip_string_quotes(_node_text(block_child))
                # Pattern 2: expression_statement wrapping a string
                if bt == "expression_statement":
                    for expr_child in getattr(block_child, "children", []):
                        if getattr(expr_child, "type", "") == "string":
                            return _strip_string_quotes(_node_text(expr_child))
                    break
                # Only check first non-comment statement
                if bt not in ("comment", "newline"):
                    break
    return None


def _first_paragraph(text: str) -> str:
    """Return the first paragraph of a docstring."""
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped and lines:
            break
        if stripped:
            lines.append(stripped)
    return " ".join(lines)


class TreeSitterSemanticExtractor:
    """SemanticExtractor implementation using tree-sitter CST navigation."""

    def __init__(self) -> None:
        self._encoding: tiktoken.Encoding | None = None

    def _get_encoding(self) -> tiktoken.Encoding:
        if self._encoding is None:
            self._encoding = tiktoken.encoding_for_model("gpt-4")
        return self._encoding

    def _estimate_tokens(self, text: str) -> int:
        return len(self._get_encoding().encode(text))

    def extract_symbols(
        self, file_path: Path, tags: list[Tag], tree: object
    ) -> list[SymbolSignature]:
        """Walk CST for each definition tag to produce SymbolSignature objects."""
        root = getattr(tree, "root_node", None)
        if root is None:
            return []

        module_name = file_path.stem
        now = datetime.now(tz=UTC)

        definition_tags = [t for t in tags if t.kind == "definition"]
        symbols: list[SymbolSignature] = []

        for tag in definition_tags:
            target_line = tag.line - 1  # Convert to 0-indexed

            node = _find_definition_node(root, target_line, tag.name)
            if node is None:
                continue

            # Keep the outer node for decorator extraction
            outer_node = node
            # Get the actual definition node (unwrap decorated_definition)
            def_node = _get_definition_node(node)
            def_node_type = getattr(def_node, "type", "")

            kind = _NODE_KIND_MAP.get(def_node_type, "unknown")
            if kind == "unknown":
                continue

            # Get parent class for methods
            parent_class = _get_parent_class(def_node)
            if parent_class and kind == "function":
                kind = "method"

            # Build qualified name
            if parent_class:
                qualified_name = f"{module_name}.{parent_class}.{tag.name}"
            else:
                qualified_name = f"{module_name}.{tag.name}"

            signature = _extract_signature(def_node)
            docstring = _extract_docstring(def_node)
            decorators = _get_decorators(outer_node)

            # Build embedding_text
            embed_parts: list[str] = []
            if parent_class:
                embed_parts.append(f"# Member of {parent_class}")
            for dec in decorators:
                embed_parts.append(dec)
            if signature:
                embed_parts.append(signature)
            if docstring:
                embed_parts.append(_first_paragraph(docstring))
            embedding_text = "\n".join(embed_parts)

            # Determine start/end lines from the outer node (includes decorators)
            start_point = getattr(outer_node, "start_point", (target_line, 0))
            end_point = getattr(outer_node, "end_point", (target_line, 0))
            start_line = start_point[0] + 1
            end_line = end_point[0] + 1

            token_count = self._estimate_tokens(embedding_text) if embedding_text else 1

            symbols.append(
                SymbolSignature(
                    qualified_name=qualified_name,
                    name=tag.name,
                    kind=kind,
                    language="python",
                    file_path=str(file_path),
                    start_line=start_line,
                    end_line=end_line,
                    signature=signature,
                    docstring=docstring,
                    parent_symbol=parent_class,
                    embedding_text=embedding_text,
                    token_count_estimate=token_count,
                    last_modified=now,
                )
            )

        return symbols

    def extract_relationships(self, file_path: Path, tags: list[Tag]) -> list[SymbolRelationship]:
        """Compute call/import edges from tags."""
        module_name = file_path.stem

        # Build definitions dict
        definitions: dict[str, Tag] = {}
        for tag in tags:
            if tag.kind == "definition":
                definitions[tag.name] = tag

        relationships: list[SymbolRelationship] = []
        seen: set[tuple[str, str, str]] = set()

        for tag in tags:
            if tag.kind != "reference":
                continue

            target_name = tag.name

            # Determine source: find the closest preceding definition
            source_name: str | None = None
            best_line = 0
            for def_tag in definitions.values():
                if def_tag.line <= tag.line and def_tag.line > best_line:
                    best_line = def_tag.line
                    source_name = def_tag.name

            if source_name is None:
                source_qualified = f"{module_name}.<module>"
            else:
                source_qualified = f"{module_name}.{source_name}"

            # Determine relationship kind
            rel_kind = "imports" if "import" in tag.rel_fname.lower() else "calls"

            key = (source_qualified, target_name, rel_kind)
            if key not in seen:
                seen.add(key)
                relationships.append(
                    SymbolRelationship(
                        source=source_qualified,
                        target=target_name,
                        kind=rel_kind,
                    )
                )

        return relationships
