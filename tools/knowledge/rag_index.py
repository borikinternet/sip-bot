#!/usr/bin/env python3
"""Validate a corpus package or build its local semantic index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import constants  # noqa: E402
from sip_bot.llm.facade import LlmFacade  # noqa: E402
from sip_bot.llm.ollama_client import OllamaHttpClient  # noqa: E402
from sip_bot.retrieval import build_and_publish_index, validate_corpus_package  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate", help="validate UTF-8 Markdown corpus package")
    validate.add_argument("--corpus", type=Path, required=True)
    validate.add_argument("--report", type=Path)
    build = subcommands.add_parser("build", help="build and atomically publish a semantic index")
    build.add_argument("--corpus", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--index-version", default=constants.RAG_INDEX_VERSION)
    build.add_argument("--embedding-model", default=constants.RAG_EMBEDDING_MODEL)
    build.add_argument("--endpoint", default=constants.LLM_HTTP_ENDPOINT)
    build.add_argument("--timeout-s", type=float, default=constants.LLM_READ_TIMEOUT_S)
    build.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        report = validate_corpus_package(args.corpus)
        rendered = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report.valid else 2
    client = OllamaHttpClient(
        endpoint=args.endpoint,
        embedding_model=args.embedding_model,
        timeout_s=args.timeout_s,
    )
    report = build_and_publish_index(
        args.corpus,
        args.output,
        LlmFacade(client),
        index_version=args.index_version,
        embedding_model=args.embedding_model,
    )
    rendered = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
