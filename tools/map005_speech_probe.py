#!/usr/bin/env python3
"""Target speech-boundary probe for the approved PCMU-derived ASR path.

The probe deliberately stops at ``FinalUserTurn``.  It does not start Ollama,
TTS, SIP, or a second model, so the result isolates Map-005-B's media-to-ASR
boundary and endpoint lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from asr_primary_probe import decode_audio  # noqa: E402
from sip_bot.media import AsrChunker, decode_pcmu_frame, encode_pcmu  # noqa: E402
from sip_bot.sip_media.models import NegotiatedMediaProfile  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    AsrHypothesis,
    EndpointingConfig,
    FinalUserTurn,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TurnDetector,
    VadProcessor,
    FasterWhisperC2Backend,
)


class _AmplitudeVad:
    """Deterministic VAD backend for isolating the real ASR boundary."""

    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        del sample_rate_hz
        samples = np.frombuffer(pcm_s16le, dtype=np.int16)
        return bool(samples.size and np.max(np.abs(samples)) > 350)


def _profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        rx_payload_type=0,
        tx_payload_type=0,
        ptime_ms=20.0,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=160,
        source="map005-b-pcmu-probe",
    )


def _hypothesis_dict(item: AsrHypothesis) -> dict[str, object]:
    return {
        "call_id": item.call_id,
        "channel_id": item.channel_id,
        "generation": item.generation,
        "revision": item.revision,
        "timestamp_ns": item.timestamp_ns,
        "text": item.text,
        "is_final": item.is_final,
        "stable_prefix": item.stable_prefix,
        "confidence": item.confidence,
        "source": item.source,
    }


def _endpoint_dict(item: object) -> dict[str, object]:
    return {
        "kind": item.kind.value,
        "call_id": item.call_id,
        "channel_id": item.channel_id,
        "generation": item.generation,
        "turn_id": item.turn_id,
        "timestamp_ns": item.timestamp_ns,
        "silence_ms": item.silence_ms,
        "reason": item.reason,
        "authoritative": item.authoritative,
    }


def _turn_dict(item: FinalUserTurn) -> dict[str, object]:
    return {
        "call_id": item.call_id,
        "channel_id": item.channel_id,
        "generation": item.generation,
        "turn_id": item.turn_id,
        "text": item.text,
        "revision": item.revision,
        "finalized_at_ns": item.finalized_at_ns,
        "boundary": item.boundary.value,
    }


def _to_pcm_8k(audio_16k: np.ndarray) -> bytes:
    target_count = max(1, round(audio_16k.size * 8000 / 16000))
    source_positions = np.arange(audio_16k.size, dtype=np.float64)
    target_positions = np.arange(target_count, dtype=np.float64) * 16000 / 8000
    pcm = np.interp(target_positions, source_positions, audio_16k)
    return (np.clip(pcm, -1.0, 1.0) * 32767.0).round().astype(np.int16).tobytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", default="ru")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    profile = _profile()
    call_id = "map005-b-pcmu-call"
    channel_id = f"{call_id}:audio"
    turn_id = f"{call_id}:turn-1"
    audio_16k = decode_audio(args.fixture)
    pcm = _to_pcm_8k(audio_16k)
    frame_bytes = profile.frame_bytes
    # Add enough actual PCM silence to exercise the authoritative 500 ms end.
    pcm += b"\x00" * round(profile.sample_rate_hz * 0.7) * 2

    backend = FasterWhisperC2Backend(
        args.model_path,
        language=args.language,
        device="cuda",
        compute_type="int8_float16",
    )
    adapter = StreamingAsrAdapter(backend)
    operation = adapter.open_operation(call_id=call_id, channel_id=channel_id, generation=1)
    ingress = SpeechIngress(
        vad=VadProcessor(_AmplitudeVad()),
        turn_detector=TurnDetector(
            EndpointingConfig(soft_endpoint_ms=300, hard_endpoint_ms=500, min_speech_ms=80)
        ),
        assembler=TranscriptAssembler(call_id, channel_id, 1, turn_id, 12),
        defer_endpoint_finalization=True,
    )
    chunker = AsrChunker(
        profile=profile,
        call_id=call_id,
        channel_id=channel_id,
        generation=1,
        chunk_ms=1000,
        flush_ms=1000,
    )
    chunker.begin_turn(turn_id)
    hypotheses: list[AsrHypothesis] = []
    endpoint_events = []
    final_turn: FinalUserTurn | None = None
    chunk_records = []
    started = time.perf_counter()
    first_model_output_at: float | None = None

    def process_chunks() -> None:
        nonlocal final_turn, first_model_output_at
        while (chunk := chunker.next_chunk()) is not None:
            chunk_records.append(chunk.as_dict())
            for hypothesis in adapter.stream(operation, (chunk,)):
                if first_model_output_at is None:
                    first_model_output_at = time.perf_counter()
                hypotheses.append(hypothesis)
                ingress_result = ingress.accept_hypothesis(hypothesis)
                if ingress_result is not None:
                    del ingress_result
                ready_turn = ingress.take_final_turn()
                if ready_turn is not None:
                    final_turn = ready_turn

    sequence = 0
    base_ns = time.monotonic_ns()
    for offset in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        sequence += 1
        timestamp_ns = base_ns + (sequence - 1) * profile.frame_time_usec * 1000
        pcm_frame = pcm[offset : offset + frame_bytes]
        # Exercise the same codec boundary as RTP: encode internal PCM to the
        # negotiated payload and decode it through the application adapter.
        pcmu_payload = encode_pcmu(pcm_frame)
        frame = decode_pcmu_frame(
            pcmu_payload,
            call_id=call_id,
            channel_id=channel_id,
            generation=1,
            sequence=sequence,
            timestamp_ns=timestamp_ns,
            profile=profile,
        )
        speech_result = ingress.process_frame(frame)
        endpoint_events.extend(speech_result.endpoint_events)
        if speech_result.final_turn is not None:
            final_turn = speech_result.final_turn
        if speech_result.vad_decision.is_speech:
            chunker.push(frame)
        process_chunks()
        if final_turn is not None:
            break

    chunker.hard_endpoint(turn_id)
    process_chunks()
    adapter.close()
    elapsed = time.perf_counter() - started
    result = {
        "status": "pass" if final_turn is not None else "fail_no_final_turn",
        "call_id": call_id,
        "fixture": str(args.fixture),
        "fixture_sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
        "model_path": args.model_path,
        "media_path": "negotiated PCMU payload -> decode_pcmu_frame -> PcmFrame",
        "profile": profile.as_dict(),
        "frames": sequence,
        "chunk_count": len(chunk_records),
        "chunks": chunk_records,
        "hypothesis_count": len(hypotheses),
        "hypotheses": [_hypothesis_dict(item) for item in hypotheses],
        "endpoint_events": [_endpoint_dict(item) for item in endpoint_events],
        "final_turn": _turn_dict(final_turn) if final_turn is not None else None,
        "elapsed_seconds": elapsed,
        "first_model_output_seconds": (
            first_model_output_at - started if first_model_output_at is not None else None
        ),
        "runtime": {
            "executable": sys.executable,
            "version": sys.version.replace("\n", " "),
            "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: None)(),
        },
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
