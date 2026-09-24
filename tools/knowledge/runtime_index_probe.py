#!/usr/bin/env python3
"""Load the configured RAG index and execute one real warm query."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for entry in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from config import constants  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.retrieval import (  # noqa: E402
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResponse,
    KnowledgeQueryBuilder,
    LocalKnowledgeIndex,
)


@dataclass(slots=True)
class _CountingProvider(EmbeddingProvider):
    delegate: LlmFacade
    requests: int = 0

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests += 1
        return self.delegate.embed(request)


def _gil_enabled() -> bool | None:
    check = getattr(sys, "_is_gil_enabled", None)
    return bool(check()) if check is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--query", default="Сколько стоит диагностический выезд мастера?")
    parser.add_argument("--endpoint", default=constants.LLM_HTTP_ENDPOINT)
    args = parser.parse_args()

    started = monotonic_ns()
    gil_before = _gil_enabled()
    index_path = PROJECT_ROOT / constants.KNOWLEDGE_INDEX_PATH
    index = LocalKnowledgeIndex.load(
        index_path,
        expected_index_version=constants.RAG_INDEX_VERSION,
        expected_corpus_version=constants.RAG_CORPUS_VERSION,
        expected_embedding_model=constants.RAG_EMBEDDING_MODEL,
        expected_dimension=constants.RAG_INDEX_DIMENSION,
        expected_chunking_policy=constants.RAG_CHUNKING_POLICY_VERSION,
        expected_corpus_sha256=constants.RAG_CORPUS_SHA256,
    )
    loaded = monotonic_ns()
    provider = _CountingProvider(
        LlmFacade(
            OllamaHttpClient(
                endpoint=args.endpoint,
                embedding_model=constants.RAG_EMBEDDING_MODEL,
                timeout_s=30.0,
            )
        )
    )
    query = KnowledgeQueryBuilder(
        max_context_chars=constants.QUERY_MAX_CONTEXT_CHARS,
        max_phrase_tokens=constants.QUERY_MAX_PHRASE_TOKENS,
    ).build(args.query)
    context = index.query(
        query,
        provider,
        top_k=constants.RAG_TOP_K,
        threshold=constants.RAG_RELEVANCE_THRESHOLD,
        context_id="runtime-readiness-probe",
    )
    finished = monotonic_ns()

    report = {
        "status": "pass",
        "operation": "load-prebuilt-index-and-warm-query",
        "python": sys.version,
        "executable": sys.executable,
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_before": gil_before,
        "gil_after": _gil_enabled(),
        "index_path": str(index_path.relative_to(PROJECT_ROOT)),
        "artifact_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "metadata": {
            "schema_version": index.metadata.schema_version,
            "index_version": index.metadata.index_version,
            "corpus_version": index.metadata.corpus_version,
            "chunking_policy": index.metadata.chunking_policy,
            "corpus_sha256": index.metadata.corpus_sha256,
            "embedding_model": index.metadata.embedding_model,
            "dimension": index.dimension,
            "item_count": index.item_count,
        },
        "requests": {
            "corpus_embedding": 0,
            "warm_query_embedding": provider.requests,
        },
        "query": args.query,
        "retrieval": {
            "sufficient": context.sufficient,
            "source_ids": list(context.source_ids),
            "hits": [
                {"chunk_id": hit.chunk_id, "source_id": hit.source_id, "score": hit.score}
                for hit in context.hits
            ],
        },
        "timing_ms": {
            "load": (loaded - started) / 1_000_000,
            "warm_query": (finished - loaded) / 1_000_000,
            "total": (finished - started) / 1_000_000,
        },
    }
    if provider.requests != 1:
        report["status"] = "fail"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
