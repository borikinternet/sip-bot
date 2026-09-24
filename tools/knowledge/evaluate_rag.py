#!/usr/bin/env python3
"""Evaluate a published RAG index against an immutable question suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import sysconfig
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for entry in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from config import constants  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.retrieval import (  # noqa: E402
    LocalKnowledgeIndex,
    evaluate_suite,
    load_evaluation_suite,
)


def _gil_enabled() -> bool | None:
    check = getattr(sys, "_is_gil_enabled", None)
    return bool(check()) if check is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        type=Path,
        default=PROJECT_ROOT / "config" / "workshops" / "rag" / "evaluation.json",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=PROJECT_ROOT / "data" / "knowledge" / "index" / "small-service-company-v1.json",
    )
    parser.add_argument("--endpoint", default=constants.LLM_HTTP_ENDPOINT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    suite = load_evaluation_suite(args.suite)
    index = LocalKnowledgeIndex.load(
        args.index,
        expected_index_version=suite.index_version,
        expected_corpus_version=suite.corpus_version,
        expected_embedding_model=suite.embedding_model,
    )
    provider = LlmFacade(
        OllamaHttpClient(
            endpoint=args.endpoint,
            embedding_model=suite.embedding_model,
            timeout_s=30.0,
        )
    )
    report = evaluate_suite(suite, index, provider)
    payload = {
        **report.to_dict(),
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
            "gil_after": _gil_enabled(),
        },
        "index_artifact": {
            "path": str(args.index),
            "sha256": hashlib.sha256(args.index.read_bytes()).hexdigest(),
            "schema_version": index.metadata.schema_version,
            "corpus_sha256": index.metadata.corpus_sha256,
            "chunking_policy": index.metadata.chunking_policy,
            "dimension": index.dimension,
            "item_count": index.item_count,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
