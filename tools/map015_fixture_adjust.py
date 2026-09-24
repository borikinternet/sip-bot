#!/usr/bin/env python3
"""Derive a Map-015 fixture set by inserting silence into an existing WAV."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave

from freeswitch_workshop.registered_full_rehearsal import _insert_silence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--after-turn", required=True)
    parser.add_argument("--insert-silence-s", type=float, required=True)
    args = parser.parse_args()
    if args.insert_silence_s <= 0:
        raise ValueError("inserted silence must be positive")

    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise RuntimeError(f"derived fixture output root already exists: {output_root}")
    shutil.copytree(source_root, output_root)
    manifest_path = source_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenario = manifest["scenarios"][args.scenario]
    segments = scenario["segments"]
    target_index = next(
        (index for index, segment in enumerate(segments) if segment["turn_id"] == args.after_turn),
        None,
    )
    if target_index is None:
        raise KeyError(f"turn {args.after_turn!r} is absent from scenario {args.scenario!r}")
    target_segment = segments[target_index]
    insertion_s = float(target_segment["speech_started_s"]) + float(target_segment["speech_duration_s"])
    source_wav = source_root / f"{args.scenario}.wav"
    target_wav = output_root / f"{args.scenario}.wav"
    _insert_silence(source_wav, target_wav, at_s=insertion_s, duration_s=args.insert_silence_s)

    target_segment["trailing_s"] = float(target_segment["trailing_s"]) + args.insert_silence_s
    for segment in segments[target_index + 1 :]:
        segment["speech_started_s"] = round(float(segment["speech_started_s"]) + args.insert_silence_s, 3)
    with wave.open(str(target_wav), "rb") as stream:
        pcm = stream.readframes(stream.getnframes())
        duration_s = stream.getnframes() / stream.getframerate()
    scenario["bytes"] = len(pcm)
    scenario["sha256"] = hashlib.sha256(pcm).hexdigest()
    scenario["duration_s"] = round(duration_s, 3)
    scenario["timing_profile"] = f"{scenario['timing_profile']}-silence-adjusted-v1"
    scenario["derived_from"] = str(source_wav)
    scenario["adjustment"] = {
        "after_turn": args.after_turn,
        "at_s": round(insertion_s, 3),
        "insert_silence_s": args.insert_silence_s,
    }
    manifest["schema"] = "sip-bot.map015-semantic-fixtures.v2"
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
