#!/usr/bin/env python3
"""Generate the deterministic multi-turn caller WAV for the RAG workshop."""

from __future__ import annotations

import argparse
import json
import sys
import sysconfig
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
XTTS_SITE = "/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/lib/python3.14t/site-packages"
for entry in (
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "src"),
    str(PROJECT_ROOT / "tools"),
    str(PROJECT_ROOT / "tools" / "knowledge"),
    XTTS_SITE,
    TARGET_SITE,
):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import j4_full_live_gate  # noqa: E402
from live_i1_gate import XTTS_MODEL, _RealXttsEngine, _profile  # noqa: E402
from rag_workshop_scenario import RAG_WORKSHOP_SCENARIO_SPECS  # noqa: E402
from sip_bot.tts import XttsV2Adapter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    j4_full_live_gate.J4_SCENARIO_SPECS = RAG_WORKSHOP_SCENARIO_SPECS
    engine = _RealXttsEngine(XTTS_MODEL, XTTS_MODEL / "samples" / "en_sample.wav")
    tts = XttsV2Adapter(engine, operation_id_factory=lambda: "rag-workshop-fixture")
    result = j4_full_live_gate._make_scenario_fixture(tts, _profile(), args.output.resolve())
    result.update(
        {
            "scenario": "rag-workshop-v1",
            "python": sys.version,
            "executable": sys.executable,
            "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
            "gil_after": getattr(sys, "_is_gil_enabled", lambda: None)(),
        }
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
