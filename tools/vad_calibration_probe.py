#!/usr/bin/env python3
"""Standalone PCMU-conditioned WebRTC VAD mode sweep.

This is a test-only probe.  It deliberately exercises the same application
candidate boundary with one sequential candidate instance per mode, while
keeping expected speech intervals in the corpus manifest rather than asking
ASR to provide labels.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sip_bot.media import decode_pcmu, encode_pcmu  # noqa: E402
from sip_bot.speech import WebRtcVadCandidate  # noqa: E402


RATE = 8000
FRAME_MS = 20
FRAME_SAMPLES = RATE * FRAME_MS // 1000
PCM_FRAME_BYTES = FRAME_SAMPLES * 2


@dataclass(frozen=True, slots=True)
class Frame:
    sequence: int
    start_ms: int
    end_ms: int
    pcm_s16le: bytes


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _gil_enabled() -> bool | None:
    for name in ("_is_gil_enabled", "gil_enabled"):
        probe = getattr(sys, name, None)
        if callable(probe):
            try:
                return bool(probe())
            except Exception:
                return None
    return None


def _read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as stream:
        properties = (stream.getnchannels(), stream.getsampwidth(), stream.getframerate())
        if properties != (1, 2, RATE):
            raise ValueError(f"corpus must be mono PCM16 8 kHz, got {properties}")
        return stream.readframes(stream.getnframes())


def _frames(pcm: bytes) -> list[Frame]:
    if len(pcm) % PCM_FRAME_BYTES:
        raise ValueError("corpus length is not aligned to a 20 ms frame")
    return [
        Frame(index + 1, index * FRAME_MS, (index + 1) * FRAME_MS, pcm[offset:offset + PCM_FRAME_BYTES])
        for index, offset in enumerate(range(0, len(pcm), PCM_FRAME_BYTES))
    ]


def _expected_speech(frame: Frame, segments: list[dict[str, object]]) -> bool:
    for segment in segments:
        start = float(segment["speech_started_s"]) * 1000.0
        end = start + float(segment["speech_duration_s"]) * 1000.0
        overlap = max(0.0, min(frame.end_ms, end) - max(frame.start_ms, start))
        if overlap >= FRAME_MS / 2:
            return True
    return False


def _runs(values: list[bool]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        if not value and start is not None:
            result.append((start, index))
            start = None
    if start is not None:
        result.append((start, len(values)))
    return result


def _segment_edge_metrics(values: list[bool], segments: list[dict[str, object]]) -> tuple[list[float], list[float]]:
    onsets: list[float] = []
    offsets: list[float] = []
    for segment in segments:
        start = float(segment["speech_started_s"]) * 1000.0
        end = start + float(segment["speech_duration_s"]) * 1000.0
        window = [
            index
            for index, is_speech in enumerate(values)
            if is_speech and (index + 1) * FRAME_MS >= start - 200 and index * FRAME_MS <= end + 300
        ]
        if not window:
            continue
        first = min(window) * FRAME_MS
        last = (max(window) + 1) * FRAME_MS
        onsets.append(first - start)
        offsets.append(last - end)
    return onsets, offsets


def _run_mode(mode: int, frames: list[Frame], segments: list[dict[str, object]], repeat: int) -> dict[str, object]:
    all_masks: list[list[bool]] = []
    raw_decisions: list[dict[str, object]] = []
    started = time.monotonic_ns()
    for run_number in range(1, repeat + 1):
        candidate = WebRtcVadCandidate(mode=mode)
        mask: list[bool] = []
        for frame in frames:
            pcmu = encode_pcmu(frame.pcm_s16le)
            decoded = decode_pcmu(pcmu)
            if len(decoded) != len(frame.pcm_s16le):
                raise AssertionError("PCMU round-trip changed frame size")
            is_speech = bool(candidate.is_speech(decoded, RATE))
            mask.append(is_speech)
            if run_number == 1:
                raw_decisions.append(
                    {
                        "sequence": frame.sequence,
                        "start_ms": frame.start_ms,
                        "end_ms": frame.end_ms,
                        "pcmu_sha256": _sha256(pcmu),
                        "is_speech": is_speech,
                    }
                )
        all_masks.append(mask)

    mask = all_masks[0]
    expected = [_expected_speech(frame, segments) for frame in frames]
    tp = sum(actual and wanted for actual, wanted in zip(mask, expected, strict=True))
    fp = sum(actual and not wanted for actual, wanted in zip(mask, expected, strict=True))
    fn = sum((not actual) and wanted for actual, wanted in zip(mask, expected, strict=True))
    tn = sum((not actual) and (not wanted) for actual, wanted in zip(mask, expected, strict=True))
    onsets, offsets = _segment_edge_metrics(mask, segments)
    speech_runs = _runs(mask)
    expected_runs = _runs(expected)
    total = len(mask)
    false_speech_rate = fp / max(1, fp + tn)
    missed_speech_rate = fn / max(1, fn + tp)
    mean_abs_onset = sum(abs(value) for value in onsets) / max(1, len(onsets))
    mean_abs_offset = sum(abs(value) for value in offsets) / max(1, len(offsets))
    # The formula is explicit and deliberately favors missed speech over a
    # small false-positive tail for a conversational assistant.
    score = missed_speech_rate * 5.0 + false_speech_rate + (mean_abs_onset + mean_abs_offset) / 10000.0
    return {
        "mode": mode,
        "frame_count": total,
        "speech_frame_count": sum(mask),
        "expected_speech_frame_count": sum(expected),
        "confusion": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "missed_speech_rate": round(missed_speech_rate, 8),
        "false_speech_rate": round(false_speech_rate, 8),
        "onset_delay_ms": {"values": onsets, "mean_abs": round(mean_abs_onset, 4)},
        "offset_delay_ms": {"values": offsets, "mean_abs": round(mean_abs_offset, 4)},
        "speech_run_count": len(speech_runs),
        "expected_speech_run_count": len(expected_runs),
        "fragmentation_delta": len(speech_runs) - len(expected_runs),
        "score": round(score, 8),
        "repeat_count": repeat,
        "deterministic_replay": all(mask == other for other in all_masks[1:]),
        "elapsed_ms": round((time.monotonic_ns() - started) / 1_000_000, 3),
        "raw_decisions": raw_decisions,
    }


def run(corpus_root: Path, output_root: Path, repeat: int = 2) -> dict[str, object]:
    if repeat < 2:
        raise ValueError("repeat must be at least 2 for determinism evidence")
    manifest_path = corpus_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_path = corpus_root / "calibration-corpus.wav"
    pcm = _read_pcm(corpus_path)
    if _sha256(pcm) != manifest["audio"]["sha256"]:
        raise ValueError("corpus hash does not match manifest")
    frames = _frames(pcm)
    segments = manifest["segments"]
    output_root.mkdir(parents=True, exist_ok=True)
    mode_results = [_run_mode(mode, frames, segments, repeat) for mode in range(4)]
    recommendation = min(mode_results, key=lambda result: (float(result["score"]), int(result["mode"])))
    result = {
        "evidence_id": f"E-008-A-VAD-SWEEP-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}",
        "status": "pass",
        "plan": "008-A",
        "corpus": {
            "manifest": str(manifest_path),
            "wav": str(corpus_path),
            "sha256": manifest["audio"]["sha256"],
            "duration_s": manifest["audio"]["duration_s"],
            "segment_count": len(segments),
        },
        "frame_contract": {
            "codec": "PCMU/G.711 mu-law",
            "decoded_format": "PCM S16LE",
            "sample_rate_hz": RATE,
            "frame_duration_ms": FRAME_MS,
            "frame_size_samples": FRAME_SAMPLES,
            "pcmu_roundtrip": True,
        },
        "runtime": {
            "executable": sys.executable,
            "version": sys.version,
            "implementation": platform.python_implementation(),
            "gil_enabled": _gil_enabled(),
            "webrtcvad_import": "lazy candidate import succeeded",
        },
        "score_formula": "5*missed_speech_rate + false_speech_rate + (mean_abs_onset_ms + mean_abs_offset_ms)/10000",
        "modes": mode_results,
        "recommendation": {
            "mode": recommendation["mode"],
            "score": recommendation["score"],
            "reason": "minimum explicit corpus score; all modes and all frames included",
        },
    }
    (output_root / "scorecard.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for mode_result in mode_results:
        raw = dict(mode_result)
        (output_root / f"mode-{mode_result['mode']}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raw.pop("raw_decisions", None)
    summary = dict(result)
    summary["modes"] = [{key: value for key, value in mode.items() if key != "raw_decisions"} for mode in mode_results]
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    result = run(args.corpus_root, args.output_root, args.repeat)
    print(json.dumps({"status": result["status"], "recommendation": result["recommendation"], "output_root": str(args.output_root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
