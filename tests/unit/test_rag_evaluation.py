from __future__ import annotations

import json
from pathlib import Path

import pytest

from sip_bot.retrieval import (
    CorpusChunk,
    DeterministicEmbeddingBackend,
    KnowledgeQueryBuilder,
    LocalKnowledgeIndex,
    evaluate_suite,
    load_evaluation_suite,
)


PROJECT_ROOT = Path(__file__).parents[2]
WORKSHOP_SUITE = PROJECT_ROOT / "config" / "workshops" / "rag" / "evaluation.json"


def test_workshop_evaluation_suite_is_frozen_and_covers_required_classes() -> None:
    suite = load_evaluation_suite(WORKSHOP_SUITE)

    assert len(suite.cases) == 12
    assert {case.kind for case in suite.cases} == {
        "positive", "paraphrase", "contextual", "negative", "conflict"
    }
    assert suite.sha256 == "35f5bc63156bf99a7e1ff0fe948c4fba9b3dacba694df55a87faec6464ac3738"


def test_evaluator_reports_source_aware_result(tmp_path: Path) -> None:
    provider = DeterministicEmbeddingBackend(32)
    chunk = CorpusChunk("service-001", "service", 1, "Ремонт посудомоечной машины")
    index = LocalKnowledgeIndex.build(
        (chunk,),
        provider,
        index_version="test-index-v1",
        embedding_model="fake-v1",
        corpus_version="test-corpus-v1",
    )
    suite_path = tmp_path / "evaluation.json"
    suite_path.write_text(
        json.dumps(
            {
                "schema_version": "rag-evaluation-v1",
                "evaluation_version": "test-eval-v1",
                "corpus_version": "test-corpus-v1",
                "index_version": "test-index-v1",
                "embedding_model": "fake-v1",
                "top_k": 1,
                "threshold": 0.0,
                "cases": [
                    {
                        "case_id": "service",
                        "kind": "positive",
                        "question": "Ремонт посудомоечной машины",
                        "context": [],
                        "expected_sufficient": True,
                        "expected_any_source_ids": ["service"],
                        "expected_top_source_id": "service",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = evaluate_suite(load_evaluation_suite(suite_path), index, provider)

    assert report.status == "pass"
    assert report.cases[0].source_ids == ("service",)
    assert report.cases[0].hits[0]["score"] > 0.9
    assert report.cases[0].sufficiency_diagnostics is not None
    assert report.cases[0].sufficiency_diagnostics["configured_threshold"] == 0.0


def test_priority_breaks_semantic_near_tie_deterministically() -> None:
    provider = DeterministicEmbeddingBackend(8)
    chunks = (
        CorpusChunk("ordinary", "ordinary", 1, "одинаковый текст", priority=100),
        CorpusChunk("emergency", "emergency", 1, "одинаковый текст", priority=300),
    )
    index = LocalKnowledgeIndex.build(
        chunks,
        provider,
        index_version="priority-v1",
        embedding_model="fake-v1",
    )

    result = index.query(
        KnowledgeQueryBuilder().build("одинаковый текст"),
        provider,
        top_k=2,
        threshold=0.0,
    )

    assert [hit.source_id for hit in result.hits] == ["emergency", "ordinary"]


def test_suite_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(WORKSHOP_SUITE.read_text(encoding="utf-8"))
    payload["cases"].append(dict(payload["cases"][0]))
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        load_evaluation_suite(path)
