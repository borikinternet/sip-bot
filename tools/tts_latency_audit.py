#!/usr/bin/env python3
"""Audit post-LLM TTS latency in a registered full-live result."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


_STAGES = (
    "llm_final_result",
    "tts_command_accepted",
    "tts_worker_started",
    "tts_adapter_started",
    "tts_engine_first_chunk",
    "tts_pcm_first_chunk",
    "playback_first_frame",
)


def _milliseconds(later_ns: int, earlier_ns: int) -> float:
    return round((later_ns - earlier_ns) / 1_000_000, 3)


def audit(document: dict[str, object], *, baseline_median_ms: float) -> dict[str, object]:
    events = document.get("tts_latency_events")
    runtime = document.get("runtime")
    wiring = document.get("wiring")
    tts_output = document.get("tts_output")
    rtp = document.get("rtp_continuity")
    if not isinstance(events, list):
        return {"status": "fail", "error": "registered result lacks tts_latency_events"}
    if not all(isinstance(section, dict) for section in (runtime, wiring, tts_output, rtp)):
        return {"status": "fail", "error": "registered result lacks runtime/output sections"}

    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            continue
        key = (
            str(event.get("call_id", "")),
            str(event.get("channel_id", "")),
            int(event.get("generation", 0)),
        )
        grouped[key].append(event)

    traces: list[dict[str, object]] = []
    incomplete: list[dict[str, object]] = []
    for (call_id, channel_id, generation), group in grouped.items():
        by_stage = {str(event.get("stage")): event for event in group}
        if "llm_final_result" not in by_stage:
            continue
        missing = [stage for stage in _STAGES if stage not in by_stage]
        if missing:
            incomplete.append(
                {
                    "call_id": call_id,
                    "channel_id": channel_id,
                    "generation": generation,
                    "missing_stages": missing,
                }
            )
            continue
        timestamps = [int(by_stage[stage]["timestamp_ns"]) for stage in _STAGES]
        traces.append(
            {
                "call_id": call_id,
                "turn_id": str(by_stage["llm_final_result"].get("turn_id", "")),
                "channel_id": channel_id,
                "generation": generation,
                "ordered": timestamps == sorted(timestamps),
                "stage_ms": {
                    "llm_final_to_command": _milliseconds(timestamps[1], timestamps[0]),
                    "command_to_worker": _milliseconds(timestamps[2], timestamps[1]),
                    "worker_to_adapter": _milliseconds(timestamps[3], timestamps[2]),
                    "adapter_to_engine_first_chunk": _milliseconds(timestamps[4], timestamps[3]),
                    "engine_to_pcm_first_chunk": _milliseconds(timestamps[5], timestamps[4]),
                    "pcm_to_playback_first_frame": _milliseconds(timestamps[6], timestamps[5]),
                    "llm_final_to_playback_first_frame": _milliseconds(timestamps[6], timestamps[0]),
                },
            }
        )

    totals = [
        float(trace["stage_ms"]["llm_final_to_playback_first_frame"])  # type: ignore[index]
        for trace in traces
    ]
    checks = {
        "registered_runner_pass": document.get("status") == "pass",
        "free_threaded_runtime": runtime.get("gil_enabled") is False,  # type: ignore[union-attr]
        "complete_answer_traces": bool(traces) and not incomplete,
        "timestamps_ordered": bool(traces) and all(bool(trace["ordered"]) for trace in traces),
        "improves_over_chunk_20_baseline": bool(totals) and max(totals) < baseline_median_ms,
        "no_runtime_errors": wiring.get("errors") == 0 and document.get("errors") == [],  # type: ignore[union-attr]
        "no_output_overflow": tts_output.get("dropped_overflow_bytes") == 0,  # type: ignore[union-attr]
        "no_egress_underruns": bool(rtp.get("checks", {}).get("egress_underruns_zero")),  # type: ignore[union-attr]
    }
    return {
        "schema": "sip-bot.tts-latency-live-audit.v1",
        "status": "pass" if all(checks.values()) else "fail",
        "baseline_chunk_20_median_ms": baseline_median_ms,
        "trace_count": len(traces),
        "minimum_llm_final_to_playback_ms": min(totals) if totals else None,
        "maximum_llm_final_to_playback_ms": max(totals) if totals else None,
        "traces": traces,
        "incomplete_traces": incomplete,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-median-ms", type=float, required=True)
    args = parser.parse_args()
    result = audit(
        json.loads(args.input.read_text(encoding="utf-8")),
        baseline_median_ms=args.baseline_median_ms,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
