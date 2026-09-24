"""Typed seam between application retrieval and the LLM Facade.

The embedding provider is a protocol.  The production Ollama adapter belongs
to plan 002-G; F only consumes this typed operation and supplies a fake
backend for deterministic evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Protocol


CORPUS_SCHEMA_VERSION = "rag-corpus-v1"
CHUNKING_POLICY_VERSION = "markdown-semantic-v1"
INDEX_SCHEMA_VERSION = "rag-index-v1"


@dataclass(frozen=True, slots=True)
class CorpusSource:
    source_id: str
    title: str
    url: str
    license: str
    attribution: str
    file: str = ""
    origin: str = ""
    owner: str = ""
    version: str = ""
    effective_date: date | None = None
    priority: int = 0
    topics: tuple[str, ...] = ()
    audiences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    schema_version: str
    corpus_id: str
    corpus_version: str
    title: str
    language: str
    license: str
    sources: tuple[CorpusSource, ...]


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    source: CorpusSource
    relative_path: PurePosixPath
    text: str
    sha256: str

    @property
    def source_id(self) -> str:
        return self.source.source_id


@dataclass(frozen=True, slots=True)
class CorpusValidationIssue:
    code: str
    message: str
    location: str
    source_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "location": self.location,
            "message": self.message,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class CorpusValidationReport:
    root: str
    manifest: CorpusManifest | None
    documents: tuple[CorpusDocument, ...]
    errors: tuple[CorpusValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.errors and self.manifest is not None

    def to_dict(self) -> dict[str, object]:
        manifest = self.manifest
        return {
            "valid": self.valid,
            "root": self.root,
            "schema_version": manifest.schema_version if manifest else None,
            "corpus_id": manifest.corpus_id if manifest else None,
            "corpus_version": manifest.corpus_version if manifest else None,
            "source_ids": [source.source_id for source in manifest.sources] if manifest else [],
            "documents": [
                {
                    "source_id": document.source_id,
                    "file": document.relative_path.as_posix(),
                    "sha256": document.sha256,
                }
                for document in self.documents
            ],
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass(frozen=True, slots=True)
class CorpusChunk:
    chunk_id: str
    source_id: str
    ordinal: int
    text: str
    source_version: str = ""
    effective_date: date | None = None
    priority: int = 0
    topics: tuple[str, ...] = ()
    audiences: tuple[str, ...] = ()
    content_sha256: str = ""


@dataclass(frozen=True, slots=True)
class CorpusIngestionResult:
    manifest: CorpusManifest | None
    sources: tuple[CorpusSource, ...]
    chunks: tuple[CorpusChunk, ...]
    accepted_source_ids: tuple[str, ...]
    skipped_source_ids: tuple[str, ...]
    errors: tuple[CorpusValidationIssue, ...]
    chunking_policy: str
    content_sha256: str

    @property
    def valid(self) -> bool:
        return self.manifest is not None and not self.errors and bool(self.chunks)

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "corpus_id": self.manifest.corpus_id if self.manifest else None,
            "corpus_version": self.manifest.corpus_version if self.manifest else None,
            "chunking_policy": self.chunking_policy,
            "content_sha256": self.content_sha256,
            "accepted_source_ids": list(self.accepted_source_ids),
            "skipped_source_ids": list(self.skipped_source_ids),
            "chunk_ids": [chunk.chunk_id for chunk in self.chunks],
            "chunk_count": len(self.chunks),
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass(frozen=True, slots=True)
class IndexMetadata:
    schema_version: str
    index_version: str
    corpus_id: str
    corpus_version: str
    chunking_policy: str
    corpus_sha256: str
    embedding_model: str
    dimension: int
    item_count: int
    sources: tuple[CorpusSource, ...]


@dataclass(frozen=True, slots=True)
class IndexBuildReport:
    status: str
    output_path: str
    index_version: str
    corpus_id: str
    corpus_version: str
    corpus_sha256: str
    chunking_policy: str
    embedding_model: str
    dimension: int
    item_count: int
    artifact_sha256: str
    elapsed_ms: float

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "index_version": self.index_version,
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "corpus_sha256": self.corpus_sha256,
            "chunking_policy": self.chunking_policy,
            "embedding_model": self.embedding_model,
            "dimension": self.dimension,
            "item_count": self.item_count,
            "artifact_sha256": self.artifact_sha256,
            "elapsed_ms": self.elapsed_ms,
        }


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
class SufficiencyDiagnostics:
    """Observable factors used for the final source-sufficiency decision."""

    reason: str
    configured_threshold: float
    effective_threshold: float
    semantic_only_threshold: float
    lexical_semantic_floor: float
    top_semantic_score: float
    top_lexical_support: int
    required_top_lexical_support: int
    eligible_query_terms: int
    minimum_query_terms: int


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
    sufficiency_diagnostics: SufficiencyDiagnostics | None = None

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(hit.source_id for hit in self.hits))
