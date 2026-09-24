from __future__ import annotations

import asyncio
from pathlib import Path

from sip_bot.retrieval import (
    DeterministicEmbeddingBackend,
    EmbeddingRequest,
    EmbeddingResponse,
    KnowledgeQueryBuilder,
    LocalKnowledgeIndex,
    ingest_corpus,
)
from sip_bot.runtime_readiness import RuntimeReadinessCoordinator


PROJECT_ROOT = Path(__file__).parents[2]
WORKSHOP = PROJECT_ROOT / "config" / "workshops" / "rag" / "corpus"


class _CountingProvider:
    def __init__(self, dimension: int) -> None:
        self.backend = DeterministicEmbeddingBackend(dimension)
        self.requests: list[EmbeddingRequest] = []

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests.append(request)
        return self.backend.embed(request)


def test_readiness_loads_prebuilt_index_and_only_embeds_warm_query(tmp_path: Path) -> None:
    ingestion = ingest_corpus(WORKSHOP)
    assert ingestion.manifest is not None
    build_provider = _CountingProvider(32)
    built = LocalKnowledgeIndex.build(
        ingestion.chunks,
        build_provider,
        index_version="runtime-test-v1",
        embedding_model="fake-v1",
        corpus_id=ingestion.manifest.corpus_id,
        corpus_version=ingestion.manifest.corpus_version,
        chunking_policy=ingestion.chunking_policy,
        corpus_sha256=ingestion.content_sha256,
        sources=ingestion.sources,
    )
    path = tmp_path / "index.json"
    built.save_atomic(path)
    assert len(build_provider.requests) == 12

    query_provider = _CountingProvider(32)

    def warmup() -> dict[str, object]:
        loaded = LocalKnowledgeIndex.load(
            path,
            expected_index_version="runtime-test-v1",
            expected_corpus_version="small-service-company-demo-v1",
            expected_embedding_model="fake-v1",
            expected_dimension=32,
            expected_chunking_policy=ingestion.chunking_policy,
            expected_corpus_sha256=ingestion.content_sha256,
        )
        context = loaded.query(
            KnowledgeQueryBuilder().build("Сколько стоит диагностический выезд?"),
            query_provider,
            top_k=3,
            threshold=0.0,
            context_id="readiness-warm-query",
        )
        return {"items": loaded.item_count, "sources": context.source_ids}

    async def run() -> None:
        coordinator = RuntimeReadinessCoordinator(warmup, runtime_id="rag-test")
        result = await coordinator.ensure_ready()
        assert result["items"] == 12
        assert coordinator.ready is True

    asyncio.run(run())

    assert len(query_provider.requests) == 1
    assert query_provider.requests[0].request_id == "query-readiness-warm-query"
