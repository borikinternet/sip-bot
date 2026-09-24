#!/usr/bin/env python3
"""Audit endpoint timing in a registered full-live result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def audit(document: dict[str, object], *, maximum_ms: int = 400) -> dict[str, object]:
    speech = document.get("speech")
    runtime = document.get("runtime")
    wiring = document.get("wiring")
    if not isinstance(speech, dict) or not isinstance(runtime, dict) or not isinstance(wiring, dict):
        return {"status": "fail", "error": "registered result lacks speech/runtime/wiring sections"}
    events = speech.get("endpoint_events")
    if not isinstance(events, list):
        return {"status": "fail", "error": "registered result lacks endpoint_events"}
    hard = [event for event in events if isinstance(event, dict) and event.get("kind") == "hard_endpoint"]
    silences = [int(event["silence_ms"]) for event in hard]
    checks = {
        "registered_runner_pass": document.get("status") == "pass",
        "free_threaded_runtime": runtime.get("gil_enabled") is False,
        "four_hard_endpoints": len(hard) == 4,
        "all_hard_endpoints_within_limit": bool(silences) and max(silences) <= maximum_ms,
        "four_final_turns": wiring.get("final_turns") == 4,
        "no_runtime_errors": wiring.get("errors") == 0 and document.get("errors") == [],
    }
    return {
        "schema": "sip-bot.endpoint-live-audit.v1",
        "status": "pass" if all(checks.values()) else "fail",
        "maximum_allowed_ms": maximum_ms,
        "observed_silence_ms": silences,
        "maximum_observed_ms": max(silences) if silences else None,
        "hard_endpoints": hard,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-ms", type=int, default=400)
    args = parser.parse_args()
    result = audit(json.loads(args.input.read_text(encoding="utf-8")), maximum_ms=args.maximum_ms)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
