#!/usr/bin/env python3
"""Clean-start Map-005-D rehearsal with Baresip stereo evidence."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from map005_stereo_recording import build_stereo  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recording_peer_config(root: Path, fixture_path: Path, recording_dir: Path, j4_prepare: object) -> Path:
    peer_config = j4_prepare(root, fixture_path)
    config_path = peer_config / "config"
    config = config_path.read_text(encoding="utf-8")
    if "module            sndfile.so" not in config:
        config += "\nmodule            sndfile.so\n"
    config += f"snd_path          {recording_dir}\n"
    config_path.write_text(config, encoding="utf-8")
    return peer_config


async def run(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"rehearsal output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(PROJECT_ROOT)
    if disk.free < 20_000_000_000:
        raise RuntimeError(f"free disk guard failed: {disk.free} bytes available")
    gil_checker = getattr(sys, "_is_gil_enabled", lambda: None)
    if gil_checker() is True:
        raise RuntimeError("rehearsal requires free-threaded CPython")

    recording_dir = Path(tempfile.mkdtemp(prefix="sipbot-map005-d-", dir="/tmp"))
    import j4_full_live_gate
    import pjsua2

    j4_run = getattr(j4_full_live_gate, "_run")
    original_prepare = j4_full_live_gate._prepare_peer_config
    original_ep_config = pjsua2.EpConfig

    def configured_ep_config() -> object:
        config = original_ep_config()
        # The recording gate needs the media clock to emit explicit idle
        # PCMU frames.  This is a test-only in-memory override; production
        # application source and the closed J4 runner remain unchanged.
        config.medConfig.noVad = True
        return config

    def prepare(root: Path, fixture_path: Path) -> Path:
        return _recording_peer_config(root, fixture_path, recording_dir, original_prepare)

    j4_full_live_gate._prepare_peer_config = prepare
    pjsua2.EpConfig = configured_ep_config
    try:
        await j4_run(
            argparse.Namespace(
                output_root=output_root,
                timeout_s=args.timeout_s,
                post_report_grace_s=args.post_report_grace_s,
            )
        )
        j4_result = json.loads((output_root / "j4-full-live.json").read_text(encoding="utf-8"))
    finally:
        j4_full_live_gate._prepare_peer_config = original_prepare
        pjsua2.EpConfig = original_ep_config

    raw_root = output_root / "recordings" / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    raw_paths = sorted(recording_dir.glob("*.wav"))
    copied: list[Path] = []
    for source in raw_paths:
        target = raw_root / source.name
        shutil.copy2(source, target)
        copied.append(target)
    enc = next((path for path in copied if path.name.endswith("-enc.wav")), None)
    dec = next((path for path in copied if path.name.endswith("-dec.wav")), None)
    recording_result: dict[str, object]
    if enc is None or dec is None:
        recording_result = {
            "status": "fail",
            "error": "Baresip sndfile did not produce both *-enc.wav and *-dec.wav",
            "files": [str(path) for path in copied],
        }
    else:
        try:
            recording_result = build_stereo(
                enc,
                dec,
                output_root / "recordings" / "conversation-stereo.wav",
                output_root / "recordings" / "recording-manifest.json",
            )
        except Exception as exc:
            recording_result = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
    shutil.rmtree(recording_dir, ignore_errors=True)

    scenario_checks = dict(j4_result.get("scenario_checks", {}))
    scenario_checks["stereo_recording_present"] = recording_result.get("status") == "pass"
    result = {
        "schema": "sip-bot.map005-d-rehearsal.v1",
        "status": "pass" if j4_result.get("status") == "pass" and all(scenario_checks.values()) else "fail",
        "plan": "005-D",
        "started_at_utc": utc_now(),
        "target_runtime": {
            "executable": sys.executable,
            "python": sys.version.replace("\n", " "),
            "gil_enabled": gil_checker(),
        },
        "test_runtime_overrides": {
            "pjsua2_media_no_vad": True,
            "purpose": "emit explicit idle PCMU/RTP frames so Baresip sndfile decode recording retains the media timeline",
            "application_source_changed": False,
        },
        "upstream_j4": j4_result,
        "scenario_checks": scenario_checks,
        "recording": recording_result,
        "report": j4_result.get("report"),
        "known_limitations": [
            "Overall final-phrase-to-first-PCM latency remains above the 200–500 ms comfort target in 005-C evidence.",
            "Recording is produced by the Baresip test peer, not by application runtime.",
        ],
        "finished_at_utc": utc_now(),
    }
    (output_root / "map005-d-rehearsal.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result, 0 if result["status"] == "pass" else 1


def write_package(root: Path, result: dict[str, object]) -> None:
    checks = result.get("scenario_checks", {})
    matrix = [
        ("SIP/RTP PCMU/8000/mono", bool(result.get("upstream_j4", {}).get("sip", {}).get("pcmu_8000_mono"))),
        ("follow-up/context", bool(checks.get("follow_up_turn_present"))),
        ("barge-in", bool(checks.get("barge_in_transition_present"))),
        ("unknown-answer/offer-transfer", bool(checks.get("unknown_answer_offer_present"))),
        ("operator transfer", bool(checks.get("operator_transfer_result"))),
        ("terminal report", bool(checks.get("report_present"))),
        ("Baresip stereo recording", bool(checks.get("stereo_recording_present"))),
    ]
    (root / "requirement-matrix.md").write_text(
        "# Map-005-D requirement matrix\n\n"
        + "\n".join(f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in matrix)
        + "\n",
        encoding="utf-8",
    )
    (root / "freeze-checklist.md").write_text(
        "# Map-005-D freeze checklist\n\n"
        f"- D status: `{'complete' if result.get('status') == 'pass' else 'blocked'}`\n"
        "- Upstream A/B/C closeouts consumed: yes\n"
        "- Application source changed by D: no\n"
        "- Raw Baresip enc/dec retained: " + ("yes\n" if checks.get("stereo_recording_present") else "no\n")
        + "- Stereo mapping: left=user_to_bot, right=bot_to_user\n"
        "- Overall latency observation retained: yes\n",
        encoding="utf-8",
    )
    (root / "commands.md").write_text(
        "# 005-D commands\n\n"
        "Rehearsal uses `tools/map005_rehearsal_gate.py` under target CPython 3.14.7t; "
        "stereo validation is performed by `tools/map005_stereo_recording.py` logic.\n\n"
        f"Result: `{result.get('status')}`\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=240.0)
    parser.add_argument("--post-report-grace-s", type=float, default=5.0)
    args = parser.parse_args()
    result, exit_code = asyncio.run(run(args))
    write_package(args.output_root.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
