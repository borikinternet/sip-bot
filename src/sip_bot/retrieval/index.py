"""Compact pure-Python local index with a typed embedding seam."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .contracts import (
    CorpusChunk,
    CorpusSource,
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResponse,
    KnowledgeContext,
    KnowledgeHit,
)
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


def _lexical_support(query: KnowledgeQuery, hits: tuple[KnowledgeHit, ...]) -> int:
    """Count query anchors represented in retrieved text.

    Embedding similarity remains the retrieval mechanism.  This small
    deterministic guard only prevents a tiny corpus from treating a generic
    high-similarity hit as sufficient evidence for an unrelated question.
    Russian inflection is handled by a short stem prefix; scientific tokens
    and numbers still require exact token equality.
    """

    terms = tuple(term.casefold() for term in query.lexical_terms if len(term) >= 4)
    if not terms:
        return 0
    hit_tokens = {
        token.casefold()
        for hit in hits
        for token in _LEXICAL_TOKEN.findall(hit.text)
    }
    matched: set[str] = set()
    for term in terms:
        if any(
            token == term
            or (
                not re.search(r"\d|[-./^+−]", term)
                and len(term) >= 5
                and token.startswith(term[:5])
            )
            for token in hit_tokens
        ):
            matched.add(term)
    return len(matched)


class LocalKnowledgeIndex:
    """In-memory query index that can be serialized as compact JSON."""

    def __init__(self, *, index_version: str, embedding_model: str) -> None:
        self.index_version = index_version
        self.embedding_model = embedding_model
        self._items: list[tuple[CorpusChunk, tuple[float, ...]]] = []

    @classmethod
    def build(
        cls,
        chunks: Iterable[CorpusChunk],
        provider: EmbeddingProvider,
        *,
        index_version: str,
        embedding_model: str,
    ) -> "LocalKnowledgeIndex":
        index = cls(index_version=index_version, embedding_model=embedding_model)
        for number, chunk in enumerate(chunks, start=1):
            response = provider.embed(EmbeddingRequest(f"index-{number}-{chunk.chunk_id}", chunk.text, embedding_model))
            index._items.append((chunk, response.vector))
        return index

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
        response = provider.embed(EmbeddingRequest(f"query-{context_id}", query.embedding_text, self.embedding_model))
        scored = sorted(
            (
                KnowledgeHit(chunk.chunk_id, chunk.source_id, chunk.text, _cosine(response.vector, vector))
                for chunk, vector in self._items
            ),
            key=lambda item: (-item.score, item.chunk_id),
        )[:top_k]
        lexical_support = _lexical_support(query, tuple(scored))
        required_lexical_support = 1 if len(query.lexical_terms) <= 5 else 2
        sufficient = bool(
            scored
            and scored[0].score >= threshold
            and lexical_support >= required_lexical_support
        )
        return KnowledgeContext(
            context_id=context_id,
            query_text=query.authoritative_text,
            hits=tuple(scored),
            sufficient=sufficient,
            threshold=threshold,
            top_k=top_k,
            index_version=self.index_version,
            embedding_model=self.embedding_model,
        )

    def save(self, path: Path) -> None:
        payload = {
            "index_version": self.index_version,
            "embedding_model": self.embedding_model,
            "items": [{"chunk": asdict(chunk), "vector": vector} for chunk, vector in self._items],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def load_corpus(root: Path) -> tuple[tuple[CorpusSource, ...], tuple[CorpusChunk, ...]]:
    """Read the checked-in manifest and deterministic chunk files."""
    manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    sources = tuple(
        CorpusSource(
            source_id=item["source_id"],
            title=item["title"],
            url=item["url"],
            license=item["license"],
            attribution=item["attribution"],
        )
        for item in manifest["sources"]
    )
    chunks: list[CorpusChunk] = []
    for item in manifest["sources"]:
        text = (Path(root) / item["file"]).read_text(encoding="utf-8")
        lines = [line.strip() for line in re.split(r"\n\s*\n", text) if line.strip()]
        for ordinal, content in enumerate(lines, start=1):
            chunks.append(CorpusChunk(f"{item['source_id']}-{ordinal:03d}", item["source_id"], ordinal, content))
    return sources, tuple(chunks)
