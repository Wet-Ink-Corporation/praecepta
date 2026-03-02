"""XML context string renderer for LLM prompt injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from praecepta.infra.codeintel.assembly.schemas import ContextResponse


def render_context_xml(response: ContextResponse) -> str:
    """Render ContextResponse as XML string."""
    parts: list[str] = []

    parts.append(
        f'<code_context tokens_used="{response.total_tokens_used}" '
        f'budget="{response.token_budget}" '
        f'chunks="{len(response.chunks)}" '
        f'more_available="{response.chunks_available}">'
    )

    for i, chunk in enumerate(response.chunks, start=1):
        location = (
            f"{chunk.location.file_path}:{chunk.location.start_line}-{chunk.location.end_line}"
        )
        parts.append("")
        parts.append(
            f'<chunk rank="{i}" relevance="{chunk.relevance_score:.2f}" '
            f'source="{chunk.retrieval_source}"\n'
            f'       symbol="{chunk.name}" kind="{chunk.kind}"\n'
            f'       location="{location}">'
        )

        if chunk.calls:
            parts.append(f"  # Calls: {', '.join(chunk.calls)}")
        if chunk.called_by:
            parts.append(f"  # Called by: {', '.join(chunk.called_by)}")

        if chunk.source_code:
            for line in chunk.source_code.splitlines():
                parts.append(f"  {line}")
        else:
            parts.append(f"  {chunk.signature}")

        parts.append("</chunk>")

    parts.append("")
    parts.append("</code_context>")

    return "\n".join(parts)
