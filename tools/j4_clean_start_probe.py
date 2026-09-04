#!/usr/bin/env python3
"""Main-only clean-start evidence runner for the Map-002 J4 gate."""

from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_PYTHON = "/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t"
C4_PYTHON = "/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python"
C2_LIBS = "/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs"


def _run(name: str, command: list[str], output_root: Path, *, env: dict[str, str] | None = None) -> dict[str, object]:
    started = time.monotonic()
    completed: subprocess.CompletedProcess[str] | None = None
    error: str | None = None
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=360,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        error = f"TimeoutExpired: {exc}"
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = 124
    else:
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
    (output_root / f"{name}.stdout.log").write_text(stdout, encoding="utf-8")
    (output_root / f"{name}.stderr.log").write_text(stderr, encoding="utf-8")
    return {
        "name": name,
        "command": " ".join(command),
        "cwd": str(PROJECT_ROOT),
        "exit_code": exit_code,
        "elapsed_s": round(time.monotonic() - started, 3),
        "stdout": str(output_root / f"{name}.stdout.log"),
        "stderr": str(output_root / f"{name}.stderr.log"),
        "error": error,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: j4_clean_start_probe.py OUTPUT_ROOT")
    output_root = Path(sys.argv[1]).resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"clean-start output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    target_env = os.environ.copy()
    target_env.pop("PYTHONPATH", None)
    target_env["PYTHONNOUSERSITE"] = "1"
    c4_env = target_env.copy()
    c4_env["LD_LIBRARY_PATH"] = C2_LIBS + (":" + c4_env["LD_LIBRARY_PATH"] if c4_env.get("LD_LIBRARY_PATH") else "")

    runs = [
        _run(
            "target-full-regression",
            [TARGET_PYTHON, "-I", "-m", "pytest", "tests/unit", "tests/contract", "tests/integration", "-q"],
            output_root,
            env=target_env,
        ),
        _run(
            "real-answer-composition",
            [
                C4_PYTHON,
                "-I",
                "tools/real_composition_probe.py",
                "--output-root",
                str(output_root / "real-answer"),
            ],
            output_root,
            env=target_env,
        ),
        _run(
            "real-media-transfer-composition",
            [
                C4_PYTHON,
                "-I",
                "tools/real_media_composition_probe.py",
                "--output-root",
                str(output_root / "real-media-transfer"),
            ],
            output_root,
            env=c4_env,
        ),
    ]
    answer = output_root / "real-answer" / "real-composition.json"
    media = output_root / "real-media-transfer" / "real-media-composition.json"
    parsed: dict[str, object] = {}
    for name, path in (("answer", answer), ("media_transfer", media)):
        if path.exists():
            parsed[name] = json.loads(path.read_text(encoding="utf-8"))
    evidence_date = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y%m%d")
    result = {
        "evidence_id": f"E-002-J4-CLEAN-START-{evidence_date}",
        "plan": "002-J",
        "stage": "J4",
        "status": "pass" if all(item["exit_code"] == 0 for item in runs) else "fail",
        "acceptance": "base_component_and_composition_lanes_pass; full_scenario_matrix_pending",
        "runs": runs,
        "compositions": parsed,
        "audio_recording": False,
        "external_pbx": False,
        "live_sip_ai": {
            "status": "base_path_proven_separately",
            "reason": "The base live SIP/RTP -> ASR/LLM/TTS -> SIP path is proven by 002-I.1 live-gate-20260903-r4; this runner keeps component/composition lanes separate and does not close the remaining full scenario matrix",
            "blocker": "B-002-J-004",
        },
        "notes": [
            "Each real composition is a clean one-call run with a fresh output root.",
            "The target regression supplies deterministic answer/follow-up/barge-in/unknown-transfer/report coverage and live SIP/RTP checks.",
            "Generated WAV files are TTS output artifacts for inspection, not conversation recordings.",
            "The runner proves component/composition lanes; 002-I.1 separately proves the base live SIP-driven path; the full scenario matrix remains open.",
        ],
    }
    (output_root / "j4-evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
