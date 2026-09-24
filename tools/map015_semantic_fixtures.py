#!/usr/bin/env python3
"""Generate the fixed Russian caller fixtures for Map-015 live acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import j4_full_live_gate
from sip_bot.tts import XttsV2Adapter


SCENARIOS: dict[str, tuple[tuple[str, str, float, float], ...]] = {
    "compound-negative-and-explicit-transfer": (
        ("known-wrapper", "Скажите, пожалуйста, почему небо днём голубое?", 2.0, 12.0),
        ("unknown-offer", "Каков точный состав атмосферы на экзопланете Кеплер семьсот восемьдесят шесть?", 0.0, 9.0),
        ("compound-negative", "Нет, не надо. Почему небо днём голубое?", 0.0, 12.0),
        ("unknown-before-pure-no", "Как оформить отпуск на Марсе?", 0.0, 8.0),
        ("pure-no", "Нет, спасибо, не надо.", 0.0, 5.0),
        ("explicit-transfer", "Переведите меня на оператора.", 0.0, 6.0),
    ),
    "compound-positive-barge-and-confirm": (
        ("unknown-offer", "Каков точный состав атмосферы на экзопланете Кеплер семьсот восемьдесят шесть?", 2.0, 9.0),
        ("compound-positive", "Да, соедините, но сначала ответьте, почему небо голубое?", 0.0, 3.0),
        ("barge-content", "Стоп, а почему на закате небо красное?", 0.0, 22.0),
        ("pure-confirm", "Да.", 0.0, 6.0),
    ),
    "compound-positive-unknown-single-offer": (
        ("unknown-offer", "Как оформить отпуск на Марсе?", 2.0, 8.0),
        ("compound-positive-unknown", "Да, но сначала ответьте, каков точный состав атмосферы на экзопланете Кеплер семьсот восемьдесят шесть?", 0.0, 10.0),
        ("pure-no", "Нет, спасибо, не надо.", 0.0, 5.0),
        ("unknown-again", "Как оформить отпуск на Венере?", 0.0, 8.0),
        ("explicit-transfer", "Переведите меня на оператора.", 0.0, 6.0),
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise RuntimeError(f"fixture output root must be new or empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    profile = j4_full_live_gate._profile()
    engine = j4_full_live_gate._RealXttsEngine(
        j4_full_live_gate.XTTS_MODEL,
        j4_full_live_gate.XTTS_MODEL / "samples" / "en_sample.wav",
    )
    tts = XttsV2Adapter(engine, operation_id_factory=lambda: "map015-fixture")
    rendered: dict[str, object] = {}
    for scenario_id, specs in SCENARIOS.items():
        rendered[scenario_id] = j4_full_live_gate._make_scenario_fixture(
            tts,
            profile,
            root / f"{scenario_id}.wav",
            specs=specs,
            timing_profile=f"map015-{scenario_id}-v1",
        )
    manifest = {
        "schema": "sip-bot.map015-semantic-fixtures.v1",
        "profile": profile.as_dict(),
        "scenarios": rendered,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
