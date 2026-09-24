#!/usr/bin/env python3
"""Build the immutable, phone-conditioned VAD calibration corpus.

The source is an already accepted XTTS-generated single-voice fixture from
Map-007.  This builder does not call a model: it extracts the known speech
segments and recomposes them with explicit pauses so the VAD and endpoint
tests have a reproducible timing manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "artifacts/implementation/007-webrtc-vad/007-C/j4-full-live-20260913-r3/live-stand/input-scenario.wav"
DEFAULT_SOURCE_MANIFEST = PROJECT_ROOT / "artifacts/implementation/007-webrtc-vad/007-C/j4-full-live-20260913-r3/j4-full-live.json"

# The words deliberately cover a short acknowledgement, follow-up speech,
# scientific terms, a name and a number.  All speech bytes come from the same
# XTTS voice/source fixture.
SOURCE_TURNS = (
    "turn-1",
    "turn-2",
    "turn-3",
    "turn-4",
    "turn-5",
)

# Pause-before values exercise the endpoint policy without asking ASR to label
# the corpus: 240 ms is below soft, 620 ms exceeds hard, 480 ms is between
# soft and hard, and 700 ms exceeds hard again.
PAUSE_BEFORE_S = (0.700, 0.240, 0.620, 0.480, 0.700)
EXPECTED_TURNS = ("cal-turn-1", "cal-turn-1", "cal-turn-2", "cal-turn-2", "cal-turn-3")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_wav(path: Path) -> tuple[bytes, int, int, int]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        rate = stream.getframerate()
        frames = stream.readframes(stream.getnframes())
    if (channels, width, rate) != (1, 2, 8000):
        raise ValueError(f"source must be mono PCM16 8 kHz, got channels={channels}, width={width}, rate={rate}")
    return frames, rate, channels, width


def _load_source_segments(path: Path) -> list[dict[str, object]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    segments = document.get("fixture", {}).get("segments")
    if not isinstance(segments, list):
        raise ValueError(f"source manifest has no fixture segments: {path}")
    by_id = {str(item["turn_id"]): item for item in segments}
    missing = [turn_id for turn_id in SOURCE_TURNS if turn_id not in by_id]
    if missing:
        raise ValueError(f"source manifest misses turns: {missing}")
    return [by_id[turn_id] for turn_id in SOURCE_TURNS]


def _silence(seconds: float, rate: int) -> bytes:
    if seconds < 0:
        raise ValueError("pause must not be negative")
    samples = round(seconds * rate)
    return b"\x00\x00" * samples


def _write_wav(path: Path, pcm: bytes, rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm)


def build(source: Path, source_manifest: Path, output_root: Path) -> dict[str, object]:
    source_pcm, rate, channels, width = _read_wav(source)
    source_segments = _load_source_segments(source_manifest)
    output_root.mkdir(parents=True, exist_ok=True)
    phrase_root = output_root / "phrases"

    source_hash = _sha256(source_pcm)
    corpus = bytearray()
    segments: list[dict[str, object]] = []
    timeline_samples = 0
    for index, (source_segment, pause_before, expected_turn) in enumerate(
        zip(source_segments, PAUSE_BEFORE_S, EXPECTED_TURNS, strict=True), start=1
    ):
        start_sample = round(float(source_segment["speech_started_s"]) * rate)
        sample_count = round(float(source_segment["speech_duration_s"]) * rate)
        start_byte = start_sample * width * channels
        end_byte = start_byte + sample_count * width * channels
        speech = source_pcm[start_byte:end_byte]
        if len(speech) != sample_count * width * channels or not speech:
            raise ValueError(f"unable to extract source speech segment {source_segment['turn_id']}")
        _write_wav(phrase_root / f"phrase-{index:02d}.wav", speech, rate)

        pause = _silence(pause_before, rate)
        corpus.extend(pause)
        timeline_samples += len(pause) // (width * channels)
        speech_started_s = timeline_samples / rate
        corpus.extend(speech)
        timeline_samples += len(speech) // (width * channels)
        segments.append(
            {
                "segment_id": f"phrase-{index:02d}",
                "source_turn_id": source_segment["turn_id"],
                "text": source_segment["text"],
                "expected_turn_id": expected_turn,
                "pause_before_s": pause_before,
                "speech_started_s": round(speech_started_s, 6),
                "speech_duration_s": round(len(speech) / (rate * width * channels), 6),
                "speech_sha256": _sha256(speech),
            }
        )
    trailing_s = 0.800
    corpus.extend(_silence(trailing_s, rate))
    timeline_samples += round(trailing_s * rate)

    corpus_path = output_root / "calibration-corpus.wav"
    _write_wav(corpus_path, bytes(corpus), rate)
    manifest = {
        "corpus_id": "vad-turn-calibration-ru-xtts-single-voice-v1",
        "revision": 1,
        "status": "immutable-after-build",
        "source": {
            "fixture_path": str(source),
            "fixture_manifest_path": str(source_manifest),
            "fixture_pcm_sha256": source_hash,
            "voice": "XTTS-v2 reference voice from model samples/en_sample.wav",
            "generation": "reused accepted Map-007 J4 XTTS fixture; no model inference in builder",
        },
        "audio": {
            "path": str(corpus_path),
            "codec": "PCM S16LE",
            "sample_rate_hz": rate,
            "channels": channels,
            "sample_width_bytes": width,
            "duration_s": round(timeline_samples / rate, 6),
            "sha256": _sha256(bytes(corpus)),
        },
        "phone_conditioning": {
            "rtp_codec": "PCMU/G.711 mu-law",
            "transport_sample_rate_hz": 8000,
            "frame_duration_ms": 20,
            "frame_size_samples": 160,
            "conditioning_performed_by": "tools/vad_calibration_probe.py",
        },
        "pause_policy": {
            "soft_endpoint_ms": 300,
            "hard_endpoint_ms": 500,
            "cases": {
                "below_soft_ms": 240,
                "above_hard_ms": 620,
                "between_soft_and_hard_ms": 480,
                "above_hard_ms_second": 700,
            },
        },
        "segments": segments,
        "trailing_silence_s": trailing_s,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.source, args.source_manifest, args.output_root)
    print(json.dumps({"status": "pass", "manifest": str(args.output_root / 'manifest.json'), "corpus_sha256": manifest["audio"]["sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
