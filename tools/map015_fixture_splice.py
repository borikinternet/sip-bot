#!/usr/bin/env python3
"""Replace one speech segment with a verified segment from another fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave


def _segment(manifest: dict, scenario_id: str, turn_id: str) -> dict:
    return next(
        item
        for item in manifest["scenarios"][scenario_id]["segments"]
        if item["turn_id"] == turn_id
    )


def _read_wave(path: Path) -> tuple[wave._wave_params, bytes]:
    with wave.open(str(path), "rb") as stream:
        return stream.getparams(), stream.readframes(stream.getnframes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--target-scenario", required=True)
    parser.add_argument("--target-turn", required=True)
    parser.add_argument("--donor-scenario", required=True)
    parser.add_argument("--donor-turn", required=True)
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise RuntimeError(f"spliced fixture output root already exists: {output_root}")
    shutil.copytree(source_root, output_root)
    manifest = json.loads((source_root / "manifest.json").read_text(encoding="utf-8"))
    target = _segment(manifest, args.target_scenario, args.target_turn)
    donor = _segment(manifest, args.donor_scenario, args.donor_turn)
    target_path = source_root / f"{args.target_scenario}.wav"
    donor_path = source_root / f"{args.donor_scenario}.wav"
    target_params, target_pcm = _read_wave(target_path)
    donor_params, donor_pcm = _read_wave(donor_path)
    if (
        target_params.nchannels,
        target_params.sampwidth,
        target_params.framerate,
    ) != (
        donor_params.nchannels,
        donor_params.sampwidth,
        donor_params.framerate,
    ):
        raise ValueError("target and donor WAV profiles differ")
    frame_width = target_params.nchannels * target_params.sampwidth
    rate = target_params.framerate
    target_start = round(float(target["speech_started_s"]) * rate) * frame_width
    target_end = target_start + round(float(target["speech_duration_s"]) * rate) * frame_width
    donor_start = round(float(donor["speech_started_s"]) * rate) * frame_width
    donor_end = donor_start + round(float(donor["speech_duration_s"]) * rate) * frame_width
    donor_speech = donor_pcm[donor_start:donor_end]
    updated_pcm = target_pcm[:target_start] + donor_speech + target_pcm[target_end:]

    output_wav = output_root / f"{args.target_scenario}.wav"
    with wave.open(str(output_wav), "wb") as stream:
        stream.setparams(target_params)
        stream.writeframes(updated_pcm)
    duration_delta_s = len(donor_speech) / (rate * frame_width) - float(target["speech_duration_s"])
    target["text"] = donor["text"]
    target["speech_duration_s"] = round(len(donor_speech) / (rate * frame_width), 3)
    target_segments = manifest["scenarios"][args.target_scenario]["segments"]
    target_index = target_segments.index(target)
    for segment in target_segments[target_index + 1 :]:
        segment["speech_started_s"] = round(float(segment["speech_started_s"]) + duration_delta_s, 3)
    scenario = manifest["scenarios"][args.target_scenario]
    scenario["bytes"] = len(updated_pcm)
    scenario["sha256"] = hashlib.sha256(updated_pcm).hexdigest()
    scenario["duration_s"] = round(len(updated_pcm) / (rate * frame_width), 3)
    scenario["timing_profile"] = f"{scenario['timing_profile']}-spliced-v1"
    scenario["splice"] = {
        "target_turn": args.target_turn,
        "donor_scenario": args.donor_scenario,
        "donor_turn": args.donor_turn,
        "donor_pcm_sha256": hashlib.sha256(donor_speech).hexdigest(),
    }
    manifest["schema"] = "sip-bot.map015-semantic-fixtures.v3"
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
