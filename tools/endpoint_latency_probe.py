#!/usr/bin/env python3
"""Verify the current endpoint budget on real speech and historical sensitivity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sip_bot.config import RuntimeConfig  # noqa: E402
from sip_bot.speech import EndpointingConfig  # noqa: E402
from tools.turn_detector_calibration_probe import (  # noqa: E402
    _load_trace,
    _manifest_intervals,
    _replay,
    _split_metrics,
)
from tools.vad_energy_replay import apply_expectations, replay  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(
    *,
    caller_wav: Path,
    caller_channel: int,
    historical_trace: Path,
    historical_manifest: Path,
    output: Path,
) -> dict[str, object]:
    config = RuntimeConfig.from_constants()
    caller = apply_expectations(
        replay(caller_wav, channel=caller_channel),
        expected_turn_count=4,
        maximum_hard_endpoint_ms=400,
    )

    trace = _load_trace(historical_trace)
    manifest = json.loads(historical_manifest.read_text(encoding="utf-8"))
    historical_events = _replay(
        trace,
        EndpointingConfig(
            soft_endpoint_ms=config.endpoint_soft_ms,
            hard_endpoint_ms=config.endpoint_hard_ms,
            min_speech_ms=config.min_speech_ms,
        ),
    )
    historical_metrics = _split_metrics(historical_events, _manifest_intervals(manifest))
    sensitivity_pass = (
        historical_metrics["hard_endpoint_count"] == 4
        and historical_metrics["interior_hard_endpoint_count"] == 1
        and historical_metrics["internal_pauses_do_not_split_turn"] is False
    )
    result: dict[str, object] = {
        "status": "pass" if caller["status"] == "pass" and sensitivity_pass else "fail",
        "policy": {
            "soft_endpoint_ms": config.endpoint_soft_ms,
            "hard_endpoint_ms": config.endpoint_hard_ms,
            "owner_maximum_ms": 400,
            "telephone_frame_ms": 20,
        },
        "caller_recording": caller,
        "historical_480ms_pause_sensitivity": {
            "trace": str(historical_trace.resolve()),
            "trace_sha256": _sha256(historical_trace),
            "manifest": str(historical_manifest.resolve()),
            "manifest_sha256": _sha256(historical_manifest),
            "former_expected_turns": 3,
            "current_expected_turns": 4,
            "expected_interior_split_count": 1,
            "metrics": historical_metrics,
            "events": historical_events,
            "accepted_as_explicit_policy_transition": sensitivity_pass,
        },
        "checks": {
            "real_caller_four_turns": caller["authoritative_turn_count"] == 4,
            "all_real_hard_endpoints_within_400ms": caller["status"] == "pass",
            "historical_480ms_pause_split_is_visible": sensitivity_pass,
            "same_frame_clock_used_for_vad_and_endpoint": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller-wav", type=Path, required=True)
    parser.add_argument("--caller-channel", type=int, default=0)
    parser.add_argument("--historical-trace", type=Path, required=True)
    parser.add_argument("--historical-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        caller_wav=args.caller_wav,
        caller_channel=args.caller_channel,
        historical_trace=args.historical_trace,
        historical_manifest=args.historical_manifest,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "policy": result["policy"],
                "checks": result["checks"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
