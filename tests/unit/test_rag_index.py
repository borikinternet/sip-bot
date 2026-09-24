from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sip_bot.retrieval import (
    DeterministicEmbeddingBackend,
    EmbeddingRequest,
    EmbeddingResponse,
    LocalKnowledgeIndex,
    KnowledgeQueryBuilder,
    build_and_publish_index,
    ingest_corpus,
)


PROJECT_ROOT = Path(__file__).parents[2]
WORKSHOP = PROJECT_ROOT / "config" / "workshops" / "rag" / "corpus"


def _build(path: Path) -> LocalKnowledgeIndex:
    ingestion = ingest_corpus(WORKSHOP)
    assert ingestion.manifest is not None
    return LocalKnowledgeIndex.build(
        ingestion.chunks,
        DeterministicEmbeddingBackend(32),
        index_version="test-index-v1",
        embedding_model="fake-v1",
        corpus_id=ingestion.manifest.corpus_id,
        corpus_version=ingestion.manifest.corpus_version,
        chunking_policy=ingestion.chunking_policy,
        corpus_sha256=ingestion.content_sha256,
        sources=ingestion.sources,
    )


def test_atomic_save_load_round_trip_and_query(tmp_path: Path) -> None:
    target = tmp_path / "index.json"
    index = _build(target)

    digest = index.save_atomic(target)
    loaded = LocalKnowledgeIndex.load(target)

    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
    assert loaded.metadata == index.metadata
    assert loaded.serialized_bytes() == index.serialized_bytes()
    context = loaded.query(
        KnowledgeQueryBuilder().build("Сколько стоит диагностический выезд?"),
        DeterministicEmbeddingBackend(32),
        top_k=3,
        threshold=0.0,
    )
    assert context.hits
    assert loaded.item_count == 12


def test_injected_pre_publish_failure_preserves_previous_bytes(tmp_path: Path) -> None:
    target = tmp_path / "index.json"
    target.write_bytes(b"previous-index")
    before = hashlib.sha256(target.read_bytes()).hexdigest()

    with pytest.raises(RuntimeError, match="injected"):
        _build(target).save_atomic(
            target,
            before_replace=lambda _temporary: (_ for _ in ()).throw(RuntimeError("injected")),
        )

    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
    assert not tuple(tmp_path.glob("*.tmp"))


def test_corrupt_payload_and_unknown_schema_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "index.json"
    _build(target).save_atomic(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["items"][0]["vector"][0] += 1
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        LocalKnowledgeIndex.load(target)

    _build(target).save_atomic(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = "future"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        LocalKnowledgeIndex.load(target)


class _BadProvider:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.calls += 1
        if self.mode == "identity":
            return EmbeddingResponse("wrong", (1.0, 2.0), request.model)
        dimension = 2 if self.calls == 1 else 3
        return EmbeddingResponse(request.request_id, tuple(float(x) for x in range(dimension)), request.model)


@pytest.mark.parametrize(("mode", "message"), (("identity", "identity"), ("dimension", "dimensions")))
def test_build_rejects_mismatched_provider_response(mode: str, message: str) -> None:
    ingestion = ingest_corpus(WORKSHOP)
    with pytest.raises(ValueError, match=message):
        LocalKnowledgeIndex.build(
            ingestion.chunks,
            _BadProvider(mode),
            index_version="test",
            embedding_model="fake",
        )


def test_build_and_publish_report_is_typed(tmp_path: Path) -> None:
    output = tmp_path / "published.json"
    report = build_and_publish_index(
        WORKSHOP,
        output,
        DeterministicEmbeddingBackend(24),
        index_version="workshop-test-v1",
        embedding_model="fake-v1",
    )

    assert report.status == "pass"
    assert report.dimension == 24
    assert report.item_count == 12
    assert report.corpus_id == "small-service-company-demo"
    assert report.artifact_sha256 == hashlib.sha256(output.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("keyword", "value", "field"),
    (
        ("expected_index_version", "wrong", "index_version"),
        ("expected_corpus_version", "wrong", "corpus_version"),
        ("expected_embedding_model", "wrong", "embedding_model"),
        ("expected_dimension", 999, "dimension"),
        ("expected_chunking_policy", "wrong", "chunking_policy"),
        ("expected_corpus_sha256", "wrong", "corpus_sha256"),
    ),
)
def test_load_rejects_each_expected_metadata_mismatch(
    tmp_path: Path, keyword: str, value: object, field: str
) -> None:
    target = tmp_path / "index.json"
    _build(target).save_atomic(target)

    with pytest.raises(ValueError, match=field):
        LocalKnowledgeIndex.load(target, **{keyword: value})
