"""Compact pure-Python local index with a typed embedding seam."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from .contracts import (
    CorpusChunk,
    CorpusSource,
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResponse,
    INDEX_SCHEMA_VERSION,
    IndexMetadata,
    KnowledgeContext,
    KnowledgeHit,
    SufficiencyDiagnostics,
)
from .corpus import CorpusPackage, CorpusValidationError, ingest_corpus
from .query_builder import KnowledgeQuery


class DeterministicEmbeddingBackend:
    """Small fake provider for reproducible tests, never production inference."""

    backend_kind = "fake-deterministic-character-ngrams-v1"

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        vector = [0.0] * self.dimension
        normalized = " ".join(request.text.casefold().split())
        grams = {normalized[index : index + 3] for index in range(max(0, len(normalized) - 2))}
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self.dimension
            vector[bucket] += 1.0
        return EmbeddingResponse(request.request_id, tuple(vector), request.model)


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    denominator = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


_LEXICAL_TOKEN = re.compile(r"(?u)[A-Za-zА-Яа-яЁё0-9]+(?:[-./^+−][A-Za-zА-Яа-яЁё0-9]+)*")
_LEXICAL_RANK_BOOST = 0.08
_LEXICAL_RANK_MAX_TERMS = 3
_SEMANTIC_ONLY_THRESHOLD = 0.53
_LEXICAL_SEMANTIC_FLOOR = 0.20
_MINIMUM_QUERY_TERMS = 2


def _eligible_lexical_terms(query: KnowledgeQuery) -> tuple[str, ...]:
    return tuple(term.casefold() for term in query.lexical_terms if len(term) >= 4)


def _lexical_match_count(query: KnowledgeQuery, text: str) -> int:
    terms = _eligible_lexical_terms(query)
    if not terms:
        return 0
    hit_tokens = {token.casefold() for token in _LEXICAL_TOKEN.findall(text)}
    return sum(
        1
        for term in terms
        if any(
            token == term
            or (
                not re.search(r"\d|[-./^+−]", term)
                and len(term) >= 5
                and token.startswith(term[:5])
            )
            for token in hit_tokens
        )
    )


class LocalKnowledgeIndex:
    """In-memory query index that can be serialized as compact JSON."""

    def __init__(
        self,
        *,
        index_version: str,
        embedding_model: str,
        metadata: IndexMetadata | None = None,
    ) -> None:
        self.index_version = index_version
        self.embedding_model = embedding_model
        self._metadata = metadata or IndexMetadata(
            schema_version=INDEX_SCHEMA_VERSION,
            index_version=index_version,
            corpus_id="legacy-unspecified",
            corpus_version="legacy-unspecified",
            chunking_policy="legacy-unspecified",
            corpus_sha256="",
            embedding_model=embedding_model,
            dimension=0,
            item_count=0,
            sources=(),
        )
        self._items: list[tuple[CorpusChunk, tuple[float, ...]]] = []

    @property
    def metadata(self) -> IndexMetadata:
        return self._metadata

    @property
    def dimension(self) -> int:
        return self._metadata.dimension

    @property
    def item_count(self) -> int:
        return len(self._items)

    @classmethod
    def build(
        cls,
        chunks: Iterable[CorpusChunk],
        provider: EmbeddingProvider,
        *,
        index_version: str,
        embedding_model: str,
        corpus_id: str = "legacy-unspecified",
        corpus_version: str = "legacy-unspecified",
        chunking_policy: str = "legacy-unspecified",
        corpus_sha256: str = "",
        sources: Iterable[CorpusSource] = (),
    ) -> "LocalKnowledgeIndex":
        materialized = tuple(chunks)
        if not materialized:
            raise ValueError("cannot build an empty knowledge index")
        index = cls(index_version=index_version, embedding_model=embedding_model)
        dimension: int | None = None
        for number, chunk in enumerate(materialized, start=1):
            request = EmbeddingRequest(f"index-{number}-{chunk.chunk_id}", chunk.text, embedding_model)
            response = provider.embed(request)
            if not isinstance(response, EmbeddingResponse):
                raise TypeError("embedding provider returned an untyped response")
            if response.request_id != request.request_id or response.model != embedding_model:
                raise ValueError("embedding response identity/model mismatch")
            if any(not math.isfinite(value) for value in response.vector):
                raise ValueError("embedding vector contains a non-finite value")
            if dimension is None:
                dimension = len(response.vector)
            elif len(response.vector) != dimension:
                raise ValueError("embedding provider returned mixed vector dimensions")
            index._items.append((chunk, response.vector))
        index._metadata = IndexMetadata(
            schema_version=INDEX_SCHEMA_VERSION,
            index_version=index_version,
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            chunking_policy=chunking_policy,
            corpus_sha256=corpus_sha256,
            embedding_model=embedding_model,
            dimension=dimension or 0,
            item_count=len(index._items),
            sources=tuple(sources),
        )
        return index

    def replace_from(self, source: "LocalKnowledgeIndex") -> None:
        """Publish a completed index into an already shared index handle.

        Runtime composition may need a stable retrieval object before the
        asynchronous readiness operation has built its contents.  The
        replacement is intentionally explicit and keeps the object identity
        used by the pipeline; callers must publish only a completed index.
        """

        if not isinstance(source, LocalKnowledgeIndex):
            raise TypeError("source must be LocalKnowledgeIndex")
        # ``index_version`` identifies the published corpus and is expected
        # to change when a conference visitor uploads a new document.  The
        # stable object handle only needs the same embedding model; its
        # callers keep using the object identity while the contents change.
        if source.embedding_model != self.embedding_model:
            raise ValueError("source embedding model does not match the target index")
        self.index_version = source.index_version
        self._metadata = source.metadata
        self._items = list(source._items)

    def query(
        self,
        query: KnowledgeQuery,
        provider: EmbeddingProvider,
        *,
        top_k: int,
        threshold: float,
        context_id: str = "knowledge-context",
    ) -> KnowledgeContext:
        if top_k < 1 or not 0.0 <= threshold <= 1.0:
            raise ValueError("top_k and threshold are invalid")
        if not self._items or self.dimension < 1:
            raise ValueError("knowledge index is empty")
        request = EmbeddingRequest(f"query-{context_id}", query.embedding_text, self.embedding_model)
        response = provider.embed(request)
        if response.request_id != request.request_id or response.model != self.embedding_model:
            raise ValueError("query embedding response identity/model mismatch")
        if len(response.vector) != self.dimension:
            raise ValueError("query embedding dimension does not match index")
        # Semantic similarity remains mandatory.  Explainable lexical anchors
        # add a bounded ranking boost; this rescues ordinary paraphrases without
        # introducing the forbidden lexical-only fallback.  Metadata resolves
        # equal hybrid ranks deterministically.
        ranked = sorted(
            (
                (
                    chunk,
                    _cosine(response.vector, vector),
                    _lexical_match_count(query, chunk.text),
                )
                for chunk, vector in self._items
            ),
            key=lambda item: (
                -round(item[1] + _LEXICAL_RANK_BOOST * min(item[2], _LEXICAL_RANK_MAX_TERMS), 6),
                -item[0].priority,
                -(item[0].effective_date.toordinal() if item[0].effective_date else 0),
                -item[1],
                item[0].chunk_id,
            ),
        )[:top_k]
        scored = [
            KnowledgeHit(chunk.chunk_id, chunk.source_id, chunk.text, score)
            for chunk, score, _ in ranked
        ]
        eligible_query_terms = len(_eligible_lexical_terms(query))
        required_top_lexical_support = (
            max(1, math.ceil(eligible_query_terms * 0.4)) if eligible_query_terms else 0
        )
        top_semantic_score = scored[0].score if scored else 0.0
        top_lexical_support = ranked[0][2] if ranked else 0
        lexical_ready = bool(
            eligible_query_terms >= _MINIMUM_QUERY_TERMS
            and top_lexical_support >= required_top_lexical_support
        )
        semantic_only_threshold = max(threshold, _SEMANTIC_ONLY_THRESHOLD)
        lexical_semantic_floor = max(
            _LEXICAL_SEMANTIC_FLOOR,
            threshold - _LEXICAL_RANK_BOOST * 2,
        )
        if not scored:
            sufficient = False
            reason = "no_hits"
            effective_threshold = threshold
        elif self.embedding_model == "embeddinggemma" and top_semantic_score >= semantic_only_threshold:
            sufficient = True
            reason = "strong_semantic"
            effective_threshold = semantic_only_threshold
        elif lexical_ready and top_semantic_score >= threshold:
            sufficient = True
            reason = "configured_semantic_with_lexical_support"
            effective_threshold = threshold
        elif lexical_ready and top_semantic_score >= lexical_semantic_floor:
            sufficient = True
            reason = "lexical_rescue_with_semantic_floor"
            effective_threshold = lexical_semantic_floor
        elif eligible_query_terms < _MINIMUM_QUERY_TERMS:
            sufficient = False
            reason = "underspecified_query"
            effective_threshold = semantic_only_threshold
        elif top_lexical_support < required_top_lexical_support:
            sufficient = False
            reason = "insufficient_lexical_support"
            effective_threshold = threshold
        else:
            sufficient = False
            reason = "semantic_score_below_floor"
            effective_threshold = lexical_semantic_floor
        return KnowledgeContext(
            context_id=context_id,
            query_text=query.authoritative_text,
            hits=tuple(scored),
            sufficient=sufficient,
            threshold=threshold,
            top_k=top_k,
            index_version=self.index_version,
            embedding_model=self.embedding_model,
            sufficiency_diagnostics=SufficiencyDiagnostics(
                reason=reason,
                configured_threshold=threshold,
                effective_threshold=effective_threshold,
                semantic_only_threshold=semantic_only_threshold,
                lexical_semantic_floor=lexical_semantic_floor,
                top_semantic_score=top_semantic_score,
                top_lexical_support=top_lexical_support,
                required_top_lexical_support=required_top_lexical_support,
                eligible_query_terms=eligible_query_terms,
                minimum_query_terms=_MINIMUM_QUERY_TERMS,
            ),
        )

    def _body(self) -> dict[str, object]:
        if not self._items or self.metadata.item_count != len(self._items):
            raise ValueError("cannot serialize an incomplete knowledge index")
        metadata = asdict(self.metadata)
        metadata["sources"] = [_source_payload(source) for source in self.metadata.sources]
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "metadata": metadata,
            "items": [
                {"chunk": _chunk_payload(chunk), "vector": list(vector)}
                for chunk, vector in self._items
            ],
        }

    def serialized_bytes(self) -> bytes:
        body = self._body()
        payload = dict(body)
        payload["payload_sha256"] = hashlib.sha256(_canonical_json(body)).hexdigest()
        return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

    def save(self, path: Path) -> None:
        self.save_atomic(path)

    def save_atomic(
        self,
        path: Path,
        *,
        before_replace: Callable[[Path], None] | None = None,
    ) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = self.serialized_bytes()
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            loaded = type(self).load(temporary)
            if loaded.serialized_bytes() != data:
                raise ValueError("candidate index self-check is not byte-identical")
            if before_replace is not None:
                before_replace(temporary)
            os.replace(temporary, target)
            if os.name != "nt":
                directory_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        expected_index_version: str | None = None,
        expected_corpus_version: str | None = None,
        expected_embedding_model: str | None = None,
        expected_dimension: int | None = None,
        expected_chunking_policy: str | None = None,
        expected_corpus_sha256: str | None = None,
    ) -> "LocalKnowledgeIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version", "metadata", "items", "payload_sha256"
        }:
            raise ValueError("index artifact has an invalid top-level schema")
        if payload["schema_version"] != INDEX_SCHEMA_VERSION:
            raise ValueError("unsupported index schema version")
        body = {key: payload[key] for key in ("schema_version", "metadata", "items")}
        checksum = hashlib.sha256(_canonical_json(body)).hexdigest()
        if payload["payload_sha256"] != checksum:
            raise ValueError("index artifact checksum mismatch")
        metadata = _metadata_from_payload(payload["metadata"])
        expectations = (
            ("index_version", expected_index_version, metadata.index_version),
            ("corpus_version", expected_corpus_version, metadata.corpus_version),
            ("embedding_model", expected_embedding_model, metadata.embedding_model),
            ("dimension", expected_dimension, metadata.dimension),
            ("chunking_policy", expected_chunking_policy, metadata.chunking_policy),
            ("corpus_sha256", expected_corpus_sha256, metadata.corpus_sha256),
        )
        for field, expected, actual in expectations:
            if expected is not None and expected != actual:
                raise ValueError(f"index {field} mismatch: expected {expected!r}, got {actual!r}")
        raw_items = payload["items"]
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("index artifact contains no items")
        index = cls(
            index_version=metadata.index_version,
            embedding_model=metadata.embedding_model,
            metadata=metadata,
        )
        for raw_item in raw_items:
            if not isinstance(raw_item, dict) or set(raw_item) != {"chunk", "vector"}:
                raise ValueError("index item schema is invalid")
            chunk = _chunk_from_payload(raw_item["chunk"])
            raw_vector = raw_item["vector"]
            if not isinstance(raw_vector, list) or len(raw_vector) != metadata.dimension:
                raise ValueError("index vector dimension mismatch")
            vector = tuple(float(value) for value in raw_vector)
            if any(not math.isfinite(value) for value in vector):
                raise ValueError("index vector contains a non-finite value")
            index._items.append((chunk, vector))
        if len(index._items) != metadata.item_count:
            raise ValueError("index item count mismatch")
        return index


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _source_payload(source: CorpusSource) -> dict[str, object]:
    payload = asdict(source)
    if source.effective_date is not None:
        payload["effective_date"] = source.effective_date.isoformat()
    return payload


def _chunk_payload(chunk: CorpusChunk) -> dict[str, object]:
    payload = asdict(chunk)
    if chunk.effective_date is not None:
        payload["effective_date"] = chunk.effective_date.isoformat()
    return payload


def _source_from_payload(raw: object) -> CorpusSource:
    if not isinstance(raw, dict):
        raise ValueError("index source metadata is invalid")
    fields = dict(raw)
    effective = fields.get("effective_date")
    fields["effective_date"] = date.fromisoformat(effective) if effective else None
    fields["topics"] = tuple(fields.get("topics", ()))
    fields["audiences"] = tuple(fields.get("audiences", ()))
    return CorpusSource(**fields)


def _chunk_from_payload(raw: object) -> CorpusChunk:
    if not isinstance(raw, dict):
        raise ValueError("index chunk metadata is invalid")
    fields = dict(raw)
    effective = fields.get("effective_date")
    fields["effective_date"] = date.fromisoformat(effective) if effective else None
    fields["topics"] = tuple(fields.get("topics", ()))
    fields["audiences"] = tuple(fields.get("audiences", ()))
    return CorpusChunk(**fields)


def _metadata_from_payload(raw: object) -> IndexMetadata:
    if not isinstance(raw, dict):
        raise ValueError("index metadata is invalid")
    required = {
        "schema_version", "index_version", "corpus_id", "corpus_version", "chunking_policy",
        "corpus_sha256", "embedding_model", "dimension", "item_count", "sources",
    }
    if set(raw) != required or raw["schema_version"] != INDEX_SCHEMA_VERSION:
        raise ValueError("index metadata schema is invalid")
    if not isinstance(raw["dimension"], int) or raw["dimension"] < 1:
        raise ValueError("index dimension is invalid")
    if not isinstance(raw["item_count"], int) or raw["item_count"] < 1:
        raise ValueError("index item count is invalid")
    sources = raw["sources"]
    if not isinstance(sources, list):
        raise ValueError("index sources are invalid")
    return IndexMetadata(
        schema_version=raw["schema_version"],
        index_version=raw["index_version"],
        corpus_id=raw["corpus_id"],
        corpus_version=raw["corpus_version"],
        chunking_policy=raw["chunking_policy"],
        corpus_sha256=raw["corpus_sha256"],
        embedding_model=raw["embedding_model"],
        dimension=raw["dimension"],
        item_count=raw["item_count"],
        sources=tuple(_source_from_payload(item) for item in sources),
    )


def load_corpus(root: Path) -> tuple[tuple[CorpusSource, ...], tuple[CorpusChunk, ...]]:
    """Compatibility entry point backed by the strict typed ingestion owner."""
    result = ingest_corpus(root)
    if not result.valid:
        raise CorpusValidationError(CorpusPackage.validate(root))
    return result.sources, result.chunks
