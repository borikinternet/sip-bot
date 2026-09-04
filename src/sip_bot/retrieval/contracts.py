"""Typed seam between application retrieval and the LLM Facade.

The embedding provider is a protocol.  The production Ollama adapter belongs
to plan 002-G; F only consumes this typed operation and supplies a fake
backend for deterministic evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CorpusSource:
    source_id: str
    title: str
    url: str
    license: str
    attribution: str


@dataclass(frozen=True, slots=True)
class CorpusChunk:
    chunk_id: str
    source_id: str
    ordinal: int
    text: str


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    request_id: str
    text: str
    model: str
    operation: str = "embed"

    def __post_init__(self) -> None:
        if self.operation != "embed":
            raise ValueError("only the typed embed operation is owned by retrieval")
        if not self.request_id or not self.text.strip() or not self.model:
            raise ValueError("embedding request requires id, text and model")


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    request_id: str
    vector: tuple[float, ...]
    model: str

    def __post_init__(self) -> None:
        if not self.request_id or not self.vector or not self.model:
            raise ValueError("embedding response requires id, vector and model")


class EmbeddingProvider(Protocol):
    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Return a typed embedding response; may raise on backend failure."""


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    chunk_id: str
    source_id: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class KnowledgeContext:
    context_id: str
    query_text: str
    hits: tuple[KnowledgeHit, ...]
    sufficient: bool
    threshold: float
    top_k: int
    index_version: str
    embedding_model: str
    failure: str | None = None

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(hit.source_id for hit in self.hits))

