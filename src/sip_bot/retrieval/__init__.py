"""Local, application-owned retrieval contracts and implementation."""

from .contracts import (
    CorpusChunk,
    CorpusSource,
    EmbeddingRequest,
    EmbeddingResponse,
    KnowledgeContext,
    KnowledgeHit,
)
from .index import DeterministicEmbeddingBackend, LocalKnowledgeIndex, load_corpus
from .query_builder import KnowledgeQuery, KnowledgeQueryBuilder

__all__ = [
    "CorpusChunk",
    "CorpusSource",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "KnowledgeContext",
    "KnowledgeHit",
    "DeterministicEmbeddingBackend",
    "LocalKnowledgeIndex",
    "KnowledgeQuery",
    "KnowledgeQueryBuilder",
    "load_corpus",
]
