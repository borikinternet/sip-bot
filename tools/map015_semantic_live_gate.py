#!/usr/bin/env python3
"""Run and reconcile the registered semantic-turn acceptance scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCENARIO_IDS = (
    "compound-negative-and-explicit-transfer",
    "compound-positive-barge-and-confirm",
    "compound-positive-unknown-single-offer",
)


def _turns(result: dict[str, Any], role: str) -> list[dict[str, Any]]:
    context = result.get("conversation", {}).get("context", [])
    return [item["turn"] for item in context if item.get("turn", {}).get("role") == role]


def _acts(result: dict[str, Any], turn_id: str) -> list[str]:
    traces = result.get("conversation", {}).get("semantic_acts", [])
    return [item["kind"] for item in traces if item.get("turn_id") == turn_id]


def _base_checks(result: dict[str, Any]) -> dict[str, bool]:
    semantic = result.get("conversation", {}).get("semantic_acts", [])
    diagnostics = [
        item.get("sufficiency_diagnostics")
        for item in result.get("conversation", {}).get("rag_contexts", [])
    ]
    report_path = result.get("report")
    report = Path(report_path) if isinstance(report_path, str) else None
    return {
        "registered_runner_pass": result.get("status") == "pass",
        "semantic_trace_present": bool(semantic),
        "all_semantic_acts_applied": bool(semantic) and all(item.get("outcome") == "applied" for item in semantic),
        "rag_diagnostics_present": bool(diagnostics) and all(item is not None for item in diagnostics),
        "report_contains_semantic_section": bool(
            report and report.is_file() and "## Семантические действия" in report.read_text(encoding="utf-8")
        ),
        "free_threaded_runtime": result.get("runtime", {}).get("gil_enabled") is False,
        "no_runtime_errors": not result.get("errors"),
    }


def _scenario_checks(scenario_id: str, result: dict[str, Any]) -> dict[str, bool]:
    users = _turns(result, "user")
    assistants = _turns(result, "assistant")
    checks = _base_checks(result)
    accepted = result.get("operator", {}).get("transfer_result", {}).get("accepted", [])
    transfer_reason = accepted[-1].get("reason") if accepted else None

    if scenario_id == "compound-negative-and-explicit-transfer":
        checks.update(
            {
                "six_raw_turns": len(users) == 6,
                "compound_negative_split": len(users) >= 3
                and _acts(result, users[2]["turn_id"]) == ["reject_pending", "knowledge_request"],
                "pure_no_rejects_without_inference": len(users) >= 5
                and _acts(result, users[4]["turn_id"]) == ["reject_pending"],
                "explicit_transfer_act": len(users) >= 6
                and _acts(result, users[5]["turn_id"]) == ["transfer_request"],
                "explicit_transfer_executed": transfer_reason == "explicit_user_request",
                "compound_raw_text_persisted_once": len(users) >= 3
                and sum(item["turn_id"] == users[2]["turn_id"] for item in users) == 1,
                "residual_question_retrieved": any(
                    context.get("query_text", "").lower().startswith("почему небо")
                    for context in result.get("conversation", {}).get("rag_contexts", [])
                ),
            }
        )
    elif scenario_id == "compound-positive-barge-and-confirm":
        checks.update(
            {
                "four_raw_turns": len(users) == 4,
                "compound_positive_split": len(users) >= 2
                and _acts(result, users[1]["turn_id"]) == ["confirm_pending", "knowledge_request"],
                "barge_in_observed": result.get("fsm", {}).get("barge_in_observed") is True,
                "pending_survives_to_new_confirmation": len(users) >= 4
                and _acts(result, users[3]["turn_id"]) == ["confirm_pending"],
                "static_reconfirmation_played": any(
                    ":transfer-confirmation:" in item.get("turn_id", "") for item in assistants
                ),
                "transfer_only_after_new_confirmation": transfer_reason == "user_confirmed",
            }
        )
    elif scenario_id == "compound-positive-unknown-single-offer":
        compound_turn_id = users[1]["turn_id"] if len(users) >= 2 else ""
        compound_answers = [
            item for item in assistants if item.get("turn_id") == f"{compound_turn_id}:answer"
        ]
        checks.update(
            {
                "five_raw_turns": len(users) == 5,
                "compound_positive_unknown_split": len(users) >= 2
                and _acts(result, compound_turn_id) == ["confirm_pending", "knowledge_request"],
                "compound_unknown_offer_once": len(compound_answers) == 1
                and compound_answers[0].get("text", "").count("Подключить оператора?") == 1,
                "no_duplicate_static_offer_for_compound_unknown": not any(
                    ":transfer-confirmation:" in item.get("turn_id", "") for item in assistants
                ),
                "subsequent_reject_is_typed": len(users) >= 3
                and _acts(result, users[2]["turn_id"]) == ["reject_pending"],
                "final_explicit_transfer": transfer_reason == "explicit_user_request",
            }
        )
    else:
        raise ValueError(f"unsupported scenario: {scenario_id}")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--registrar-address", default="127.0.0.1:5060")
    parser.add_argument("--peer-user", default="peer")
    parser.add_argument("--peer-password", default="PUBLIC-DEMO-SIP-PASSWORD")
    parser.add_argument("--target-extension", default="7000")
    parser.add_argument("--external-pbx", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=360.0)
    parser.add_argument(
        "--reuse-result",
        action="append",
        default=[],
        metavar="SCENARIO=RESULT_JSON",
        help="reuse a previously green registered result for the same immutable fixture",
    )
    args = parser.parse_args()

    fixture_root = args.fixture_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"semantic gate output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    reused: dict[str, Path] = {}
    for item in args.reuse_result:
        scenario_id, separator, result_value = item.partition("=")
        if not separator or scenario_id not in SCENARIO_IDS or not result_value:
            raise ValueError(f"invalid --reuse-result value: {item!r}")
        reused[scenario_id] = Path(result_value).resolve()

    for scenario_id in SCENARIO_IDS:
        scenario_root = output_root / scenario_id
        fixture = fixture_root / f"{scenario_id}.wav"
        if not fixture.is_file():
            raise FileNotFoundError(f"missing Map-015 fixture: {fixture}")
        reused_result = reused.get(scenario_id)
        if reused_result is not None:
            if not reused_result.is_file():
                raise FileNotFoundError(f"reused result is absent: {reused_result}")
            result = json.loads(reused_result.read_text(encoding="utf-8"))
            checks = _scenario_checks(scenario_id, result)
            results[scenario_id] = {
                "command": None,
                "exit_code": 0 if result.get("status") == "pass" else 1,
                "result": str(reused_result),
                "log": None,
                "reused": True,
                "fixture": str(fixture),
                "checks": checks,
                "status": "pass" if result.get("status") == "pass" and all(checks.values()) else "fail",
            }
            if results[scenario_id]["status"] != "pass":
                break
            continue
        command = [
            sys.executable,
            "tools/freeswitch_workshop/registered_full_rehearsal.py",
            "--output-root",
            str(scenario_root),
            "--fixture-source",
            str(fixture),
            "--timeout-s",
            str(args.timeout_s),
            "--post-report-grace-s",
            "5",
            "--fixture-leading-silence-s",
            "8",
            "--continuity-tail-s",
            "20",
            "--barge-in-shift-s",
            "0",
            "--prewarm",
            "--registrar-address",
            args.registrar_address,
            "--peer-user",
            args.peer_user,
            "--peer-password",
            args.peer_password,
            "--target-extension",
            args.target_extension,
        ]
        if args.external_pbx:
            command.append("--external-pbx")
        if scenario_id != "compound-positive-barge-and-confirm":
            command.append("--skip-barge-in-check")
        log_path = output_root / f"{scenario_id}.log"
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=args.timeout_s + 120,
                check=False,
            )
        result_path = scenario_root / "registered-j4-full-live.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
        checks = _scenario_checks(scenario_id, result) if result else {"result_present": False}
        redacted_command = list(command)
        password_index = redacted_command.index("--peer-password") + 1
        redacted_command[password_index] = "<REDACTED>"
        results[scenario_id] = {
            "command": redacted_command,
            "exit_code": completed.returncode,
            "result": str(result_path),
            "log": str(log_path),
            "reused": False,
            "fixture": str(fixture),
            "checks": checks,
            "status": "pass" if completed.returncode == 0 and all(checks.values()) else "fail",
        }
        if results[scenario_id]["status"] != "pass":
            break

    aggregate = {
        "schema": "sip-bot.map015-semantic-live-gate.v1",
        "status": (
            "pass"
            if len(results) == len(SCENARIO_IDS)
            and all(item["status"] == "pass" for item in results.values())
            else "fail"
        ),
        "scenarios": results,
    }
    (output_root / "map015-semantic-live-gate.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0 if aggregate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
