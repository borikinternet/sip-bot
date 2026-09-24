#!/usr/bin/env python3
"""Replay a mono/stereo telephone WAV through the configured live VAD policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import sysconfig
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sip_bot.config import RuntimeConfig  # noqa: E402
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    EndpointEventKind,
    EndpointingConfig,
    TurnDetector,
    build_configured_web_rtc_vad_processor,
)


def _read_channel(path: Path, channel: int) -> tuple[int, bytes, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError("replay requires PCM S16LE WAV")
        channels = wav.getnchannels()
        if not 0 <= channel < channels:
            raise ValueError(f"channel {channel} is outside WAV channel count {channels}")
        rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    if channels == 1:
        return rate, raw, channels
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono = samples[channel::channels]
    return rate, struct.pack(f"<{len(mono)}h", *mono), channels


def _ranges(flags: list[bool], frame_ms: int) -> list[dict[str, float | int]]:
    ranges: list[dict[str, float | int]] = []
    start: int | None = None
    for index, value in enumerate((*flags, False)):
        if value and start is None:
            start = index
        elif not value and start is not None:
            ranges.append(
                {
                    "start_s": round(start * frame_ms / 1000.0, 3),
                    "end_s": round(index * frame_ms / 1000.0, 3),
                    "duration_ms": (index - start) * frame_ms,
                }
            )
            start = None
    return ranges


def replay(path: Path, *, channel: int) -> dict[str, object]:
    config = RuntimeConfig.from_constants()
    rate, pcm, source_channels = _read_channel(path, channel)
    frame_ms = 20
    frame_samples = rate * frame_ms // 1000
    frame_bytes = frame_samples * 2
    profile = NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        ptime_ms=float(frame_ms),
        sample_rate_hz=rate,
        channels=1,
        frame_size_samples=frame_samples,
        source="recorded-call-replay",
    )
    processor = build_configured_web_rtc_vad_processor(config)
    detector = TurnDetector(
        EndpointingConfig(
            soft_endpoint_ms=config.endpoint_soft_ms,
            hard_endpoint_ms=config.endpoint_hard_ms,
            min_speech_ms=config.min_speech_ms,
        )
    )
    raw_flags: list[bool] = []
    accepted_flags: list[bool] = []
    endpoint_events: list[dict[str, object]] = []
    sequence = 0
    for offset in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        sequence += 1
        frame = PcmFrame(
            call_id="recorded-call-replay",
            channel_id="recorded-call-replay:media",
            generation=1,
            sequence=sequence,
            timestamp_ns=(sequence - 1) * frame_ms * 1_000_000,
            pcm_s16le=pcm[offset : offset + frame_bytes],
            profile=profile,
        )
        decision = processor.process(frame)
        raw_flags.append(bool(decision.raw_is_speech))
        accepted_flags.append(decision.is_speech)
        for event in detector.consume(decision):
            endpoint_events.append(
                {
                    "kind": event.kind.value,
                    "turn_id": event.turn_id,
                    "timestamp_s": round(event.timestamp_ns / 1_000_000_000.0, 3),
                    "silence_ms": event.silence_ms,
                    "authoritative": event.authoritative,
                }
            )
    analytics = processor.analytics_snapshot()
    assert analytics is not None
    hard_endpoints = [
        event for event in endpoint_events if event["kind"] == EndpointEventKind.HARD_ENDPOINT.value
    ]
    hard_endpoint_silence_ms = [int(event["silence_ms"]) for event in hard_endpoints]
    return {
        "status": "pass",
        "runtime": {
            "executable": sys.executable,
            "version": sys.version,
            "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
            "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: None)(),
        },
        "input": {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "sample_rate_hz": rate,
            "source_channels": source_channels,
            "selected_channel": channel,
            "frame_ms": frame_ms,
            "frame_count": sequence,
        },
        "configuration": {
            "vad_mode": config.vad_mode,
            "energy_gate_enabled": config.vad_energy_gate_enabled,
            "minimum_dbfs": config.vad_energy_min_dbfs,
            "noise_margin_db": config.vad_energy_noise_margin_db,
            "near_end_bootstrap_dbfs": config.vad_energy_near_end_bootstrap_dbfs,
            "near_end_confirmation_ms": config.vad_energy_near_end_confirmation_ms,
            "near_end_percentile": config.vad_energy_near_end_percentile,
            "near_end_margin_db": config.vad_energy_near_end_margin_db,
            "barge_in_margin_db": config.vad_energy_barge_in_margin_db,
            "barge_in_minimum_dbfs": config.vad_energy_barge_in_minimum_dbfs,
            "hard_endpoint_ms": config.endpoint_hard_ms,
            "min_speech_ms": config.min_speech_ms,
        },
        "analytics": {
            "total_frames": analytics.total_frames,
            "raw_speech_frames": analytics.raw_speech_frames,
            "accepted_speech_frames": analytics.accepted_speech_frames,
            "rejected_low_energy_frames": analytics.rejected_low_energy_frames,
            "noise_floor_dbfs": round(analytics.noise_floor_dbfs, 3),
            "speech_threshold_dbfs": round(analytics.speech_threshold_dbfs, 3),
            "speech_level_dbfs": (
                None
                if analytics.speech_level_dbfs is None
                else round(analytics.speech_level_dbfs, 3)
            ),
            "barge_in_threshold_dbfs": round(analytics.barge_in_threshold_dbfs, 3),
            "barge_in_qualified_frames": analytics.barge_in_qualified_frames,
        },
        "raw_speech_ranges": _ranges(raw_flags, frame_ms),
        "accepted_speech_ranges": _ranges(accepted_flags, frame_ms),
        "endpoint_events": endpoint_events,
        "authoritative_turn_count": len(hard_endpoints),
        "endpoint_timing": {
            "hard_endpoint_silence_ms": hard_endpoint_silence_ms,
            "maximum_hard_endpoint_silence_ms": (
                max(hard_endpoint_silence_ms) if hard_endpoint_silence_ms else None
            ),
        },
    }


def apply_expectations(
    result: dict[str, object],
    *,
    expected_turn_count: int | None,
    maximum_hard_endpoint_ms: int | None,
) -> dict[str, object]:
    """Apply CLI acceptance without requiring the native VAD in unit tests."""

    if expected_turn_count is not None and result["authoritative_turn_count"] != expected_turn_count:
        result["status"] = "fail"
        result["expected_turn_count"] = expected_turn_count
    if maximum_hard_endpoint_ms is not None:
        timing = result["endpoint_timing"]
        assert isinstance(timing, dict)
        maximum = timing["maximum_hard_endpoint_silence_ms"]
        result["maximum_allowed_hard_endpoint_ms"] = maximum_hard_endpoint_ms
        if maximum is None or int(maximum) > maximum_hard_endpoint_ms:
            result["status"] = "fail"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--expect-turns", type=int)
    parser.add_argument("--max-hard-endpoint-ms", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(args.wav, channel=args.channel)
    apply_expectations(
        result,
        expected_turn_count=args.expect_turns,
        maximum_hard_endpoint_ms=args.max_hard_endpoint_ms,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
