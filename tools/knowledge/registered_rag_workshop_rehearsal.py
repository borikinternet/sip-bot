#!/usr/bin/env python3
"""Run and assert the registered FreeSWITCH RAG workshop scenario."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
for entry in (
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "src"),
    str(PROJECT_ROOT / "tools"),
    str(PROJECT_ROOT / "tools" / "knowledge"),
):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from rag_workshop_scenario import RAG_WORKSHOP_SCENARIO_SPECS  # noqa: E402


def _rag_stage_has_zero_corpus_embeddings(result: dict[str, object]) -> bool:
    warmup = result.get("warmup")
    if not isinstance(warmup, dict):
        return False
    stages = warmup.get("stages")
    if not isinstance(stages, list):
        return False
    for stage in stages:
        if isinstance(stage, dict) and stage.get("name") == "rag-embedding-index":
            details = stage.get("details")
            return isinstance(details, dict) and details.get("corpus_embedding_requests") == 0
    return False


def _assistant_text_for_turn(dialogue_turns: object, turn_id: str) -> str:
    """Return the answer paired with a user turn, ignoring standalone assistant turns."""
    if not isinstance(dialogue_turns, list):
        return ""
    answer_turn_id = f"{turn_id}:answer"
    for item in dialogue_turns:
        if not isinstance(item, dict):
            continue
        turn = item.get("turn")
        if (
            isinstance(turn, dict)
            and turn.get("role") == "assistant"
            and str(turn.get("turn_id", "")).endswith(answer_turn_id)
        ):
            return str(turn.get("text", ""))
    return ""


async def _run(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    import j4_full_live_gate
    from freeswitch_workshop import registered_full_rehearsal

    j4_full_live_gate.J4_SCENARIO_SPECS = RAG_WORKSHOP_SCENARIO_SPECS
    result, inner_exit = await registered_full_rehearsal._run(
        argparse.Namespace(
            output_root=args.output_root,
            timeout_s=args.timeout_s,
            post_report_grace_s=args.post_report_grace_s,
            prewarm=True,
            fixture_source=args.fixture_source,
            fixture_leading_silence_s=args.fixture_leading_silence_s,
            warmup_question="Сколько стоит диагностический выезд мастера?",
            barge_in_insert_at_s=0.0,
            barge_in_shift_s=0.0,
            continuity_tail_s=30.0,
        )
    )
    conversation = result.get("conversation")
    contexts = conversation.get("rag_contexts", []) if isinstance(conversation, dict) else []
    all_sources = [
        source
        for context in contexts
        if isinstance(context, dict)
        for source in context.get("source_ids", [])
        if isinstance(source, str)
    ]
    positive = next(
        (
            context for context in contexts
            if isinstance(context, dict) and "диагностическ" in str(context.get("query_text", "")).casefold()
        ),
        None,
    )
    follow_up = contexts[1] if len(contexts) > 1 else None
    # The fourth scripted turn is the out-of-domain science question.  Select
    # it by scenario position rather than by an ASR keyword: recognizing only
    # a fragment such as "Голубое" must still exercise the insufficient path.
    old_science = contexts[3] if len(contexts) > 3 else None
    dialogue_turns = conversation.get("context", []) if isinstance(conversation, dict) else []
    old_science_answer = _assistant_text_for_turn(dialogue_turns, "turn-4")
    normalized_unknown_answer = str(old_science_answer).casefold()
    report_path = Path(result["report"]) if result.get("report") else None
    report_text = report_path.read_text(encoding="utf-8") if report_path and report_path.exists() else ""
    checks = {
        "registered_inner_gate_passed": inner_exit == 0 and result.get("status") == "pass",
        "prebuilt_index_loaded_without_corpus_embeddings": _rag_stage_has_zero_corpus_embeddings(result),
        "workshop_positive_source_present": bool(
            isinstance(positive, dict)
            and "company-pricing-and-terms" in positive.get("source_ids", [])
            and positive.get("sufficient") is True
        ),
        "live_follow_up_uses_pricing_context": bool(
            isinstance(follow_up, dict)
            and "company-pricing-and-terms" in follow_up.get("source_ids", [])
            and follow_up.get("sufficient") is True
        ),
        "old_science_question_is_insufficient": bool(
            isinstance(old_science, dict) and old_science.get("sufficient") is False
        ),
        "unknown_answer_text_reports_limit_and_offers_operator": bool(
            ("не могу" in normalized_unknown_answer or "недостаточно" in normalized_unknown_answer)
            and "оператор" in normalized_unknown_answer
        ),
        "no_old_science_source_leakage": bool(all_sources) and not any(source.startswith("wiki-") for source in all_sources),
        "report_contains_workshop_sources": "company-pricing-and-terms" in report_text,
    }
    result["rag_workshop"] = {
        "scenario": "rag-workshop-v1",
        "checks": checks,
        "active_source_ids": sorted(set(all_sources)),
    }
    result["status"] = "pass" if all(checks.values()) else "fail"
    output = args.output_root / "rag-workshop-full-live.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result, 0 if result["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--fixture-source", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--post-report-grace-s", type=float, default=5.0)
    parser.add_argument("--fixture-leading-silence-s", type=float, default=2.0)
    args = parser.parse_args()
    result, exit_code = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
