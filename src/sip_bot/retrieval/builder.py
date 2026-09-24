"""Offline build orchestration owned by the local Context/KB capability."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .contracts import EmbeddingProvider, IndexBuildReport
from .corpus import CorpusValidationError, ingest_corpus
from .index import LocalKnowledgeIndex


def build_and_publish_index(
    corpus_root: Path,
    output_path: Path,
    provider: EmbeddingProvider,
    *,
    index_version: str,
    embedding_model: str,
) -> IndexBuildReport:
    """Build a complete candidate and atomically publish it after self-check."""

    started_ns = time.monotonic_ns()
    ingestion = ingest_corpus(corpus_root)
    if not ingestion.valid or ingestion.manifest is None:
        from .corpus import CorpusPackage

        raise CorpusValidationError(CorpusPackage.validate(corpus_root))
    index = LocalKnowledgeIndex.build(
        ingestion.chunks,
        provider,
        index_version=index_version,
        embedding_model=embedding_model,
        corpus_id=ingestion.manifest.corpus_id,
        corpus_version=ingestion.manifest.corpus_version,
        chunking_policy=ingestion.chunking_policy,
        corpus_sha256=ingestion.content_sha256,
        sources=ingestion.sources,
    )
    artifact_sha256 = index.save_atomic(output_path)
    if hashlib.sha256(output_path.read_bytes()).hexdigest() != artifact_sha256:
        raise ValueError("published index hash does not match the candidate")
    return IndexBuildReport(
        status="pass",
        output_path=str(output_path),
        index_version=index.index_version,
        corpus_id=ingestion.manifest.corpus_id,
        corpus_version=ingestion.manifest.corpus_version,
        corpus_sha256=ingestion.content_sha256,
        chunking_policy=ingestion.chunking_policy,
        embedding_model=index.embedding_model,
        dimension=index.dimension,
        item_count=index.item_count,
        artifact_sha256=artifact_sha256,
        elapsed_ms=round((time.monotonic_ns() - started_ns) / 1_000_000, 3),
    )


__all__ = ["build_and_publish_index"]
