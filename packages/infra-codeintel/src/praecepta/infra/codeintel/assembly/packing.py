"""Token budget packing via binary search with signature-only overflow."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import tiktoken

from praecepta.infra.codeintel.exceptions import BudgetExceededError

if TYPE_CHECKING:
    from praecepta.infra.codeintel.assembly.schemas import CodeChunk

_enc = tiktoken.encoding_for_model("gpt-4")


def _estimate_signature_tokens(chunk: CodeChunk) -> int:
    """Estimate tokens for signature-only representation."""
    return len(_enc.encode(chunk.signature))


def pack_to_budget(
    chunks: list[CodeChunk],
    budget: int,
) -> tuple[list[CodeChunk], int, int]:
    """Pack ranked chunks into token budget.

    Returns:
        (selected_chunks, tokens_used, chunks_remaining)
    """
    if not chunks:
        return [], 0, 0

    if budget <= 0:
        raise BudgetExceededError(budget=budget, min_required=chunks[0].token_count)

    total = sum(c.token_count for c in chunks)
    if total <= budget:
        return list(chunks), total, 0

    if chunks[0].token_count > budget:
        raise BudgetExceededError(budget=budget, min_required=chunks[0].token_count)

    # Binary search for max N where sum(tokens[0:N]) <= budget
    prefix_sums: list[int] = []
    running = 0
    for c in chunks:
        running += c.token_count
        prefix_sums.append(running)

    lo, hi = 1, len(chunks)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if prefix_sums[mid - 1] <= budget:
            lo = mid
        else:
            hi = mid - 1

    n = lo
    tokens_used = prefix_sums[n - 1]
    selected = list(chunks[:n])

    # Try to include next chunk as signature-only
    if n < len(chunks):
        remaining_budget = budget - tokens_used
        next_chunk = chunks[n]
        sig_tokens = _estimate_signature_tokens(next_chunk)
        if sig_tokens <= remaining_budget:
            stub = copy.copy(next_chunk)
            stub.source_code = None
            stub.token_count = sig_tokens
            selected.append(stub)
            tokens_used += sig_tokens
            n += 1

    return selected, tokens_used, len(chunks) - n
