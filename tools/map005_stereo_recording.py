#!/usr/bin/env python3
"""Validate Baresip mono tracks and build the required stereo derivative."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import wave


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        round(frames / rate, 6),
    )


def build_stereo(enc: Path, dec: Path, output: Path, manifest: Path) -> dict[str, object]:
    left = inspect(enc, "user_to_bot")
    right = inspect(dec, "bot_to_user")
    target_frames = max(left.frames, right.frames)
    left_padding_frames = target_frames - left.frames
    right_padding_frames = target_frames - right.frames
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(enc), "rb") as enc_stream, wave.open(str(dec), "rb") as dec_stream, wave.open(str(output), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(8000)
        remaining = target_frames
        while remaining:
            count = min(32768, remaining)
            enc_payload = enc_stream.readframes(min(count, left.frames))
            dec_payload = dec_stream.readframes(min(count, right.frames))
            expected_bytes = count * 2
            if len(enc_payload) < expected_bytes:
                enc_payload += bytes(expected_bytes - len(enc_payload))
            if len(dec_payload) < expected_bytes:
                dec_payload += bytes(expected_bytes - len(dec_payload))
            interleaved = bytearray(len(enc_payload) * 2)
            for index in range(0, len(enc_payload), 2):
                target = index * 2
                interleaved[target : target + 2] = enc_payload[index : index + 2]
                interleaved[target + 2 : target + 4] = dec_payload[index : index + 2]
            out.writeframes(bytes(interleaved))
            remaining -= count
    stereo = inspect_stereo(output)
    result = {
        "schema": "sip-bot.map005-d-stereo-recording.v1",
        "status": "pass",
        "mapping": {"left": "user_to_bot", "right": "bot_to_user"},
        "alignment": {
            "policy": "pad_trailing_silence_to_longest_raw_track",
            "target_frames": target_frames,
            "target_duration_s": round(target_frames / 8000, 6),
            "user_to_bot_padded_frames": left_padding_frames,
            "bot_to_user_padded_frames": right_padding_frames,
            "padding_is_explicit_in_manifest": True,
        },
        "raw_tracks": {"enc": asdict(left), "dec": asdict(right)},
        "stereo": stereo,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(__import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    args = parser.parse_args()
    manifest = args.manifest or args.output.with_suffix(".json")
    try:
        result = build_stereo(args.enc.resolve(), args.dec.resolve(), args.output.resolve(), manifest.resolve())
    except Exception as exc:
        result = {"schema": "sip-bot.map005-d-stereo-recording.v1", "status": "fail", "error": f"{type(exc).__name__}: {exc}"}
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(__import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(__import__("json").dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(__import__("json").dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
