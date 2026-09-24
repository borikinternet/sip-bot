#!/usr/bin/env python3
"""Validate Baresip mono tracks and build the required stereo derivative."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import wave
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Track:
    path: str
    role: str
    bytes: int
    sha256: str
    channels: int
    sample_width: int
    sample_rate_hz: int
    frames: int
    duration_s: float
    recording_start_ns: int | None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


_BARESIP_RECORDING_NAME_RE = re.compile(
    r"^dump-(?P<timestamp>\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})-(?:enc|dec)\.wav$"
)


def infer_recording_start_ns(path: Path) -> int | None:
    """Infer Baresip sndfile creation time from its timestamped filename."""

    match = _BARESIP_RECORDING_NAME_RE.match(path.name)
    if match is None:
        return None
    local_time = datetime.strptime(match.group("timestamp"), "%Y-%m-%d-%H-%M-%S")
    return int(local_time.timestamp() * 1_000_000_000)


def inspect(path: Path, role: str) -> Track:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        rate = stream.getframerate()
        frames = stream.getnframes()
        if stream.getcomptype() != "NONE":
            raise ValueError(f"{role} is compressed, expected PCM WAV: {path}")
    if channels != 1 or width != 2 or rate != 8000 or frames < 1:
        raise ValueError(
            f"{role} metadata must be mono PCM16/8000Hz with data, got "
            f"channels={channels}, width={width}, rate={rate}, frames={frames}"
        )
    return Track(
        str(path), role, path.stat().st_size, sha256(path), channels, width, rate, frames,
        round(frames / rate, 6), infer_recording_start_ns(path),
    )


def build_stereo(
    enc: Path,
    dec: Path,
    output: Path,
    manifest: Path,
    *,
    expected_ptime_ms: float | None = None,
    call_window_ms: float | None = None,
    call_window_start_ns: int | None = None,
    max_trailing_padding_ms: float = 500.0,
) -> dict[str, object]:
    """Build a stereo derivative on an explicit conversation timeline.

    A live caller supplies the answered-call duration (and preferably its
    wall-clock start).  The legacy no-window mode remains strict and is only
    intended for independent fixture validation.
    """

    left = inspect(enc, "user_to_bot")
    right = inspect(dec, "bot_to_user")
    if expected_ptime_ms is not None and expected_ptime_ms <= 0:
        raise ValueError("expected_ptime_ms must be positive")
    if call_window_ms is not None and call_window_ms <= 0:
        raise ValueError("call_window_ms must be positive")
    if call_window_start_ns is not None and call_window_ms is None:
        raise ValueError("call_window_start_ns requires call_window_ms")
    if max_trailing_padding_ms < 0:
        raise ValueError("max_trailing_padding_ms must not be negative")
    max_padding_frames = math.ceil(left.sample_rate_hz * max_trailing_padding_ms / 1000.0)
    if call_window_ms is None:
        # Compatibility path for old, stand-alone recording fixtures.  Live
        # calls must pass the answered-call event window explicitly.
        target_frames = max(left.frames, right.frames)
        alignment_policy = "strict_shared_timeline_trailing_cleanup_only"
    else:
        # Baresip's sndfile enc/dec files have independent close boundaries.
        # The call lifecycle, not either WAV duration, is the authoritative
        # clock for a conversation recording.
        target_frames = max(1, round(left.sample_rate_hz * call_window_ms / 1000.0))
        alignment_policy = "answered_call_event_window"
    recording_starts = [start for start in (left.recording_start_ns, right.recording_start_ns) if start is not None]
    timeline_origin_ns = call_window_start_ns if call_window_start_ns is not None else (min(recording_starts) if recording_starts else None)
    left_offset_frames = (
        round((left.recording_start_ns - timeline_origin_ns) * left.sample_rate_hz / 1_000_000_000)
        if left.recording_start_ns is not None and timeline_origin_ns is not None
        else 0
    )
    right_offset_frames = (
        round((right.recording_start_ns - timeline_origin_ns) * right.sample_rate_hz / 1_000_000_000)
        if right.recording_start_ns is not None and timeline_origin_ns is not None
        else 0
    )

    def alignment_counts(raw_frames: int, offset_frames: int) -> tuple[int, int, int]:
        raw_end = offset_frames + raw_frames
        leading = max(0, min(target_frames, offset_frames))
        trailing = max(0, target_frames - max(0, raw_end))
        trimmed = max(0, -offset_frames) + max(0, raw_end - target_frames)
        return leading, trailing, trimmed

    left_leading_padding, left_trailing_padding, left_trimmed_frames = alignment_counts(left.frames, left_offset_frames)
    right_leading_padding, right_trailing_padding, right_trimmed_frames = alignment_counts(right.frames, right_offset_frames)
    left_padding_frames = left_leading_padding + left_trailing_padding
    right_padding_frames = right_leading_padding + right_trailing_padding
    actual_padding_frames = max(left_padding_frames, right_padding_frames)
    actual_padding_ms = actual_padding_frames * 1000.0 / left.sample_rate_hz
    if call_window_ms is None and actual_padding_frames > max_padding_frames:
        raise ValueError(
            "raw Baresip track duration gap exceeds the allowed cleanup tail: "
            f"{actual_padding_ms:.3f} ms > {max_trailing_padding_ms:.3f} ms "
            f"({left.duration_s:.6f} s vs {right.duration_s:.6f} s)"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    def read_aligned(stream: wave.Wave_read, raw_frames: int, offset_frames: int, start_frame: int, count: int) -> bytes:
        source_start = start_frame - offset_frames
        source_end = source_start + count
        payload = bytearray()
        overlap_start = max(0, source_start)
        overlap_end = min(raw_frames, source_end)
        if overlap_start > source_start:
            payload.extend(b"\x00" * ((overlap_start - source_start) * 2))
        if overlap_end > overlap_start:
            stream.setpos(overlap_start)
            payload.extend(stream.readframes(overlap_end - overlap_start))
        if source_end > overlap_end:
            payload.extend(b"\x00" * ((source_end - overlap_end) * 2))
        expected_bytes = count * 2
        if len(payload) < expected_bytes:
            payload.extend(b"\x00" * (expected_bytes - len(payload)))
        return bytes(payload[:expected_bytes])

    with wave.open(str(enc), "rb") as enc_stream, wave.open(str(dec), "rb") as dec_stream, wave.open(str(output), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(8000)
        remaining = target_frames
        while remaining:
            count = min(32768, remaining)
            start_frame = target_frames - remaining
            enc_payload = read_aligned(enc_stream, left.frames, left_offset_frames, start_frame, count)
            dec_payload = read_aligned(dec_stream, right.frames, right_offset_frames, start_frame, count)
            interleaved = bytearray(len(enc_payload) * 2)
            for index in range(0, len(enc_payload), 2):
                target = index * 2
                interleaved[target : target + 2] = enc_payload[index : index + 2]
                interleaved[target + 2 : target + 4] = dec_payload[index : index + 2]
            out.writeframes(bytes(interleaved))
            remaining -= count
    stereo = inspect_stereo(output)
    result = {
        "schema": "sip-bot.map010-b-stereo-recording.v2",
        "status": "pass",
        "mapping": {"left": "user_to_bot", "right": "bot_to_user"},
        "alignment": {
            "policy": alignment_policy,
            "target_frames": target_frames,
            "target_duration_s": round(target_frames / 8000, 6),
            "call_window_ms": None if call_window_ms is None else round(call_window_ms, 6),
            "call_window_is_authoritative": call_window_ms is not None,
            "call_window_start_ns": call_window_start_ns,
            "timeline_origin_ns": timeline_origin_ns,
            "timeline_origin_policy": (
                "answered_call_event_window_start"
                if call_window_start_ns is not None
                else "earliest_recording_start_or_zero"
            ),
            "user_to_bot_start_offset_frames": left_offset_frames,
            "bot_to_user_start_offset_frames": right_offset_frames,
            "user_to_bot_padded_frames": left_padding_frames,
            "bot_to_user_padded_frames": right_padding_frames,
            "user_to_bot_leading_padding_frames": left_leading_padding,
            "user_to_bot_trailing_padding_frames": left_trailing_padding,
            "bot_to_user_leading_padding_frames": right_leading_padding,
            "bot_to_user_trailing_padding_frames": right_trailing_padding,
            "user_to_bot_trimmed_frames": left_trimmed_frames,
            "bot_to_user_trimmed_frames": right_trimmed_frames,
            "max_trailing_padding_ms": max_trailing_padding_ms,
            "max_trailing_padding_frames": max_padding_frames,
            "max_trailing_padding_applies": call_window_ms is None,
            "padding_mode": (
                "strict_cleanup_tail_only"
                if call_window_ms is None
                else "materialize_answered_call_window"
            ),
            "actual_padding_ms": round(actual_padding_ms, 6),
            "expected_ptime_ms": None if expected_ptime_ms is None else round(expected_ptime_ms, 6),
            "padding_is_explicit_in_manifest": True,
        },
        "raw_tracks": {"enc": asdict(left), "dec": asdict(right)},
        "stereo": stereo,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def inspect_stereo(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        rate = stream.getframerate()
        frames = stream.getnframes()
        if (channels, width, rate) != (2, 2, 8000) or frames < 1:
            raise ValueError("stereo derivative metadata is invalid")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "channels": channels,
        "sample_width": width,
        "sample_rate_hz": rate,
        "frames": frames,
        "duration_s": round(frames / rate, 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enc", type=Path, required=True)
    parser.add_argument("--dec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--expected-ptime-ms", type=float, default=None)
    parser.add_argument(
        "--call-window-ms",
        type=float,
        default=None,
        help="authoritative answered-call duration from 200 OK to BYE/media_stopped",
    )
    parser.add_argument(
        "--call-window-start-ns",
        type=int,
        default=None,
        help="wall-clock timestamp of answered-call start, in epoch nanoseconds",
    )
    args = parser.parse_args()
    manifest = args.manifest or args.output.with_suffix(".json")
    try:
        result = build_stereo(
            args.enc.resolve(),
            args.dec.resolve(),
            args.output.resolve(),
            manifest.resolve(),
            expected_ptime_ms=args.expected_ptime_ms,
            call_window_ms=args.call_window_ms,
            call_window_start_ns=args.call_window_start_ns,
        )
    except Exception as exc:
        result = {"schema": "sip-bot.map010-b-stereo-recording.v2", "status": "fail", "error": f"{type(exc).__name__}: {exc}"}
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
