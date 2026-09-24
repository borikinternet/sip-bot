#!/usr/bin/env python3
"""Replay one recorded caller channel through production VAD and ASR evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import struct
import sys
import sysconfig
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
C2_SITE = "/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages"
XTTS_SITE = "/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/lib/python3.14t/site-packages"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, XTTS_SITE)
sys.path.insert(0, TARGET_SITE)
sys.path.append(C2_SITE)

from sip_bot.config import RuntimeConfig  # noqa: E402
from sip_bot.media import AsrAudioChunk, FlushReason  # noqa: E402
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    EndpointEventKind,
    EndpointingConfig,
    FasterWhisperC2Backend,
    StreamingAsrAdapter,
    TurnDetector,
    build_configured_web_rtc_vad_processor,
)


DEFAULT_MODEL = Path("/home/sipbot/.local/models/faster-whisper-large-v3-edaa852e")


def _read_channel(path: Path, channel: int) -> tuple[int, bytes, int]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("replay requires PCM S16LE WAV")
        channels = source.getnchannels()
        if not 0 <= channel < channels:
            raise ValueError("selected channel is outside the WAV")
        rate = source.getframerate()
        raw = source.readframes(source.getnframes())
    if channels == 1:
        return rate, raw, channels
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono = samples[channel::channels]
    return rate, struct.pack(f"<{len(mono)}h", *mono), channels


def replay(
    path: Path,
    *,
    channel: int,
    model_path: Path,
    probe_intervals: tuple[tuple[float, float], ...] = (),
) -> dict[str, object]:
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
        source="recorded-speech-evidence-replay",
    )
    vad = build_configured_web_rtc_vad_processor(config)
    detector = TurnDetector(
        EndpointingConfig(
            soft_endpoint_ms=config.endpoint_soft_ms,
            hard_endpoint_ms=config.endpoint_hard_ms,
            min_speech_ms=config.min_speech_ms,
        )
    )
    backend = FasterWhisperC2Backend(
        str(model_path),
        language="ru",
        device="cuda",
        compute_type="int8_float16",
        no_speech_threshold=config.asr_no_speech_threshold,
        segment_end_tolerance_ms=config.asr_segment_end_tolerance_ms,
    )
    adapter = StreamingAsrAdapter(backend)
    operation = adapter.open_operation(
        call_id="recorded-speech-evidence-replay",
        channel_id="recorded-speech-evidence-replay:media",
        generation=1,
    )
    candidate_frames: list[bytes] = []
    turn_audio: dict[str, bytearray] = {}
    turns: list[dict[str, object]] = []
    sequence = 0
    for offset in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        sequence += 1
        frame = PcmFrame(
            call_id="recorded-speech-evidence-replay",
            channel_id="recorded-speech-evidence-replay:media",
            generation=1,
            sequence=sequence,
            timestamp_ns=(sequence - 1) * frame_ms * 1_000_000,
            pcm_s16le=pcm[offset : offset + frame_bytes],
            profile=profile,
        )
        decision = vad.process(frame)
        events = detector.consume(decision)
        if decision.is_speech:
            candidate_frames.append(frame.pcm_s16le)
            active_turn_id = detector.active_turn_id
            if active_turn_id is not None:
                accumulator = turn_audio.setdefault(active_turn_id, bytearray())
                for payload in candidate_frames:
                    accumulator.extend(payload)
                candidate_frames.clear()
        elif detector.active_turn_id is None:
            candidate_frames.clear()

        for event in events:
            if event.kind is not EndpointEventKind.HARD_ENDPOINT:
                continue
            payload = bytes(turn_audio.pop(event.turn_id, b""))
            chunk = AsrAudioChunk(
                call_id=event.call_id,
                channel_id=event.channel_id,
                generation=event.generation,
                turn_id=event.turn_id,
                sequence=len(turns) + 1,
                timestamp_ns=event.timestamp_ns,
                pcm_s16le=payload,
                profile=profile,
                flush_reason=FlushReason.HARD_ENDPOINT,
                is_final=True,
            )
            hypotheses = tuple(adapter.stream(operation, (chunk,)))
            if len(hypotheses) != 1:
                raise RuntimeError("production backend must emit exactly one final hypothesis per replay turn")
            hypothesis = hypotheses[0]
            turns.append(
                {
                    "turn_id": event.turn_id,
                    "timeline_end_s": round(event.timestamp_ns / 1_000_000_000.0, 3),
                    "accepted_audio_ms": round(chunk.duration_ms, 3),
                    "text": hypothesis.normalized_text,
                    "speech_supported": hypothesis.speech_supported,
                    "evidence": None if hypothesis.evidence is None else asdict(hypothesis.evidence),
                }
            )

    analytics = vad.analytics_snapshot()
    accepted = [item for item in turns if item["speech_supported"]]
    rejected = [item for item in turns if not item["speech_supported"]]
    interval_probes: list[dict[str, object]] = []
    for index, (start_s, end_s) in enumerate(probe_intervals, start=1):
        start_byte = round(start_s * rate) * 2
        end_byte = round(end_s * rate) * 2
        payload = pcm[start_byte:end_byte]
        turn_id = f"recorded-speech-evidence-replay:probe-{index}"
        chunk = AsrAudioChunk(
            call_id="recorded-speech-evidence-replay",
            channel_id="recorded-speech-evidence-replay:media",
            generation=1,
            turn_id=turn_id,
            sequence=len(turns) + index,
            timestamp_ns=round(start_s * 1_000_000_000),
            pcm_s16le=payload,
            profile=profile,
            flush_reason=FlushReason.HARD_ENDPOINT,
            is_final=True,
        )
        hypotheses = tuple(adapter.stream(operation, (chunk,)))
        if len(hypotheses) != 1:
            raise RuntimeError("production backend must emit one interval-probe hypothesis")
        hypothesis = hypotheses[0]
        interval_probes.append(
            {
                "turn_id": turn_id,
                "start_s": start_s,
                "end_s": end_s,
                "input_duration_ms": round(chunk.duration_ms, 3),
                "text": hypothesis.normalized_text,
                "speech_supported": hypothesis.speech_supported,
                "evidence": None if hypothesis.evidence is None else asdict(hypothesis.evidence),
            }
        )
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
            "frame_count": sequence,
        },
        "configuration": {
            "vad_mode": config.vad_mode,
            "no_speech_threshold": config.asr_no_speech_threshold,
            "segment_end_tolerance_ms": config.asr_segment_end_tolerance_ms,
        },
        "vad_analytics": None if analytics is None else asdict(analytics),
        "turn_count": len(turns),
        "accepted_turn_count": len(accepted),
        "rejected_turn_count": len(rejected),
        "turns": turns,
        "interval_probes": interval_probes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--expect-accepted-turns", type=int)
    parser.add_argument(
        "--probe-interval",
        action="append",
        default=[],
        metavar="START:END",
        help="also transcribe an exact WAV interval as diagnostic speech evidence",
    )
    parser.add_argument("--expect-rejected-probes", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    intervals: list[tuple[float, float]] = []
    for value in args.probe_interval:
        start_text, separator, end_text = value.partition(":")
        if not separator:
            parser.error(f"invalid probe interval: {value!r}")
        start_s, end_s = float(start_text), float(end_text)
        if start_s < 0 or end_s <= start_s:
            parser.error(f"invalid probe interval: {value!r}")
        intervals.append((start_s, end_s))
    result = replay(
        args.wav,
        channel=args.channel,
        model_path=args.model_path,
        probe_intervals=tuple(intervals),
    )
    if (
        args.expect_accepted_turns is not None
        and result["accepted_turn_count"] != args.expect_accepted_turns
    ):
        result["status"] = "fail"
        result["expected_accepted_turns"] = args.expect_accepted_turns
    rejected_probes = sum(
        not bool(item["speech_supported"])
        for item in result["interval_probes"]
    )
    result["rejected_probe_count"] = rejected_probes
    if (
        args.expect_rejected_probes is not None
        and rejected_probes != args.expect_rejected_probes
    ):
        result["status"] = "fail"
        result["expected_rejected_probes"] = args.expect_rejected_probes
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
