"""Code intelligence and context assembly for AI agents.

Provides tree-sitter parsing, semantic search via LanceDB, structural
ranking via PageRank, and token-budgeted context assembly for AI agents.
"""

from praecepta.infra.codeintel.assembly.schemas import (
    CodeChunk,
    ContextQuery,
    ContextResponse,
    RepoSummary,
    SourceLocation,
)
from praecepta.infra.codeintel.exceptions import (
    BudgetExceededError,
    CodeIntelError,
    EmbeddingError,
    IndexError,
    ParseError,
    UnsupportedLanguageError,
)
from praecepta.infra.codeintel.lifespan import lifespan_contribution
from praecepta.infra.codeintel.protocols import (
    ContextAssembler,
    CSTParser,
    FileWatcher,
    SemanticExtractor,
    SemanticIndex,
    StructuralIndex,
)
from praecepta.infra.codeintel.settings import CodeIntelSettings, get_settings
from praecepta.infra.codeintel.types import (
    FileEvent,
    IndexStats,
    ParseResult,
    QueryIntent,
    SymbolRelationship,
    SymbolSignature,
    Tag,
)

__all__ = [
    "BudgetExceededError",
    "CSTParser",
    "CodeChunk",
    "CodeIntelError",
    "CodeIntelSettings",
    "ContextAssembler",
    "ContextQuery",
    "ContextResponse",
    "EmbeddingError",
    "FileEvent",
    "FileWatcher",
    "IndexError",
    "IndexStats",
    "ParseError",
    "ParseResult",
    "QueryIntent",
    "RepoSummary",
    "SemanticExtractor",
    "SemanticIndex",
    "SourceLocation",
    "StructuralIndex",
    "SymbolRelationship",
    "SymbolSignature",
    "Tag",
    "UnsupportedLanguageError",
    "get_settings",
    "lifespan_contribution",
]
