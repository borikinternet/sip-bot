#!/usr/bin/env python3
"""Replay the selected WebRTC VAD trace through the existing TurnDetector."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sip_bot.speech import EndpointEventKind, EndpointingConfig, TurnDetector, VadDecision  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gil_enabled() -> bool | None:
    for name in ("_is_gil_enabled", "gil_enabled"):
        probe = getattr(sys, name, None)
        if callable(probe):
            try:
                return bool(probe())
            except Exception:
                return None
    return None


def _load_trace(path: Path) -> list[dict[str, object]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    decisions = document.get("raw_decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError(f"mode trace has no raw_decisions: {path}")
    return decisions


def _manifest_intervals(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for segment in manifest["segments"]:
        segment = dict(segment)
        start_ms = float(segment["speech_started_s"]) * 1000.0
        end_ms = start_ms + float(segment["speech_duration_s"]) * 1000.0
        turn_id = str(segment["expected_turn_id"])
        current = result.get(turn_id)
        if current is None:
            result[turn_id] = {"start_ms": start_ms, "end_ms": end_ms, "segments": [segment["segment_id"]]}
        else:
            current["start_ms"] = min(float(current["start_ms"]), start_ms)
            current["end_ms"] = max(float(current["end_ms"]), end_ms)
            current["segments"].append(segment["segment_id"])
    return result


def _expected_internal_gaps(manifest: dict[str, object]) -> list[dict[str, object]]:
    segments = manifest["segments"]
    gaps: list[dict[str, object]] = []
    for previous, current in zip(segments, segments[1:], strict=False):
        if previous["expected_turn_id"] != current["expected_turn_id"]:
            continue
        previous_end = (float(previous["speech_started_s"]) + float(previous["speech_duration_s"])) * 1000.0
        current_start = float(current["speech_started_s"]) * 1000.0
        gaps.append(
            {
                "from_segment": previous["segment_id"],
                "to_segment": current["segment_id"],
                "gap_ms": round(current_start - previous_end, 3),
                "expected_no_hard_endpoint": True,
            }
        )
    return gaps


def _decision(item: dict[str, object], *, call_id: str, channel_id: str, generation: int) -> VadDecision:
    return VadDecision(
        call_id=call_id,
        channel_id=channel_id,
        generation=generation,
        sequence=int(item["sequence"]),
        timestamp_ns=int(item["start_ms"]) * 1_000_000,
        frame_duration_ms=20,
        is_speech=bool(item["is_speech"]),
        source="WebRtcVadCandidate(mode=2)/PCMU-replay",
    )


def _replay(trace: list[dict[str, object]], config: EndpointingConfig) -> list[dict[str, object]]:
    detector = TurnDetector(config)
    events: list[dict[str, object]] = []
    for item in trace:
        for event in detector.consume(_decision(item, call_id="vad-calibration-call", channel_id="speech_ingress", generation=1)):
            events.append(
                {
                    "kind": event.kind.value,
                    "turn_id": event.turn_id,
                    "timestamp_ms": event.timestamp_ns / 1_000_000,
                    "silence_ms": event.silence_ms,
                    "reason": event.reason,
                    "authoritative": event.authoritative,
                }
            )
    return events


def _split_metrics(events: list[dict[str, object]], expected_turns: dict[str, dict[str, object]]) -> dict[str, object]:
    hard = [event for event in events if event["kind"] == EndpointEventKind.HARD_ENDPOINT.value]
    soft = [event for event in events if event["kind"] == EndpointEventKind.SOFT_ENDPOINT.value]
    resumed = [event for event in events if event["kind"] == EndpointEventKind.SPEECH_RESUMED.value]
    interior_hard: list[dict[str, object]] = []
    for turn_id, interval in expected_turns.items():
        start_ms = float(interval["start_ms"])
        end_ms = float(interval["end_ms"])
        for event in hard:
            if start_ms <= float(event["timestamp_ms"]) <= end_ms:
                interior_hard.append({"expected_turn_id": turn_id, "event": event})
    expected_hard_count = len(expected_turns)
    boundary_check = len(hard) == expected_hard_count
    internal_pause_check = not interior_hard
    return {
        "event_count": len(events),
        "hard_endpoint_count": len(hard),
        "expected_hard_endpoint_count": expected_hard_count,
        "soft_endpoint_count": len(soft),
        "speech_resumed_count": len(resumed),
        "interior_hard_endpoint_count": len(interior_hard),
        "interior_hard_endpoints": interior_hard,
        "authoritative_boundaries_match": boundary_check,
        "internal_pauses_do_not_split_turn": internal_pause_check,
        "accepted": boundary_check and internal_pause_check,
    }


def run(trace_path: Path, corpus_manifest_path: Path, output_root: Path, config: EndpointingConfig | None = None) -> dict[str, object]:
    config = config or EndpointingConfig()
    trace = _load_trace(trace_path)
    manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    expected_turns = _manifest_intervals(manifest)
    internal_gaps = _expected_internal_gaps(manifest)

    # The first valid value is selected explicitly.  The 500 ms baseline is
    # retained in the evidence so a calibration change cannot hide it.
    sweep_values = tuple(dict.fromkeys((500, 520, 540, 560, config.hard_endpoint_ms)))
    sweep: list[dict[str, object]] = []
    for hard_ms in sweep_values:
        sweep_config = EndpointingConfig(
            soft_endpoint_ms=config.soft_endpoint_ms,
            hard_endpoint_ms=hard_ms,
            min_speech_ms=config.min_speech_ms,
        )
        sweep_events = _replay(trace, sweep_config)
        sweep.append(
            {
                "hard_endpoint_ms": hard_ms,
                "metrics": _split_metrics(sweep_events, expected_turns),
                "events": sweep_events,
            }
        )
    selected = next((item for item in sweep if item["metrics"]["accepted"]), None)
    if selected is None:
        selected_config = config
        events = _replay(trace, selected_config)
    else:
        selected_config = EndpointingConfig(
            soft_endpoint_ms=config.soft_endpoint_ms,
            hard_endpoint_ms=int(selected["hard_endpoint_ms"]),
            min_speech_ms=config.min_speech_ms,
        )
        events = selected["events"]
    repeat_events = _replay(trace, selected_config)
    metrics = _split_metrics(events, expected_turns)
    metrics["deterministic_replay"] = events == repeat_events
    result = {
        "evidence_id": f"E-008-B-TURN-REPLAY-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}",
        "status": "pass" if metrics["accepted"] and metrics["deterministic_replay"] else "fail",
        "plan": "008-B",
        "input": {"trace": str(trace_path), "trace_sha256": _sha256(trace_path), "corpus_manifest": str(corpus_manifest_path)},
        "runtime": {"executable": sys.executable, "version": sys.version, "implementation": platform.python_implementation(), "gil_enabled": _gil_enabled()},
        "endpoint_config": {
            "soft_endpoint_ms": selected_config.soft_endpoint_ms,
            "hard_endpoint_ms": selected_config.hard_endpoint_ms,
            "min_speech_ms": selected_config.min_speech_ms,
        },
        "expected_turns": expected_turns,
        "expected_internal_gaps": internal_gaps,
        "events": events,
        "threshold_sweep": sweep,
        "metrics": metrics,
        "checks": {
            "typed_vad_decision_replay": True,
            "turn_detector_owns_endpointing": True,
            "asr_used_for_acceptance": False,
            "new_component_added": False,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "turn-detector-replay.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.trace, args.corpus_manifest, args.output_root)
    print(json.dumps({"status": result["status"], "metrics": result["metrics"], "output_root": str(args.output_root)}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
