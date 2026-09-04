"""Map-005-B deterministic speech/audio resilience matrix."""

from __future__ import annotations

import pytest

from sip_bot.media import AsrChunker, FlushReason, PcmFanOut
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.speech import (
    AsrHypothesis,
    EndpointEvent,
    EndpointEventKind,
    EndpointingConfig,
    SpeechIngress,
    TranscriptAssembler,
    TranscriptUpdateKind,
    TurnDetector,
    VadProcessor,
    WebRtcVadCandidate,
)


def _profile(ptime_ms: float = 30.0) -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        rx_payload_type=0,
        tx_payload_type=0,
        ptime_ms=ptime_ms,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=int(8000 * ptime_ms / 1000),
        source="map005-b-negotiated",
    )


def _frame(sequence: int, *, generation: int = 1, ptime_ms: float = 30.0, value: int = 1) -> PcmFrame:
    profile = _profile(ptime_ms)
    return PcmFrame(
        call_id="call-map005-b",
        channel_id="call-map005-b:audio",
        generation=generation,
        sequence=sequence,
        timestamp_ns=(sequence - 1) * int(ptime_ms * 1_000_000),
        pcm_s16le=(value.to_bytes(2, "little", signed=True) * profile.frame_size_samples),
        profile=profile,
    )


class _ByteVad:
    def is_speech(self, pcm_s16le: bytes, _sample_rate_hz: int) -> bool:
        return pcm_s16le[:2] == b"\x01\x00"


def _vad() -> VadProcessor:
    return VadProcessor(WebRtcVadCandidate(backend=_ByteVad()))


def _hard_boundary() -> EndpointEvent:
    return EndpointEvent(
        kind=EndpointEventKind.HARD_ENDPOINT,
        call_id="call-map005-b",
        channel_id="call-map005-b:audio",
        generation=1,
        turn_id="call-map005-b:turn-1",
        timestamp_ns=500_000_000,
        silence_ms=500,
        reason="hard_silence_threshold_reached",
        authoritative=True,
    )


def test_fanout_drops_only_slow_consumer_and_keeps_other_consumer_live() -> None:
    fanout = PcmFanOut(capacity_frames=1, generation=1)
    vad = fanout.subscribe("vad")
    asr = fanout.subscribe("asr")

    assert fanout.publish(_frame(1)).delivered_to == ("vad", "asr")
    assert vad.get_nowait() is not None
    result = fanout.publish(_frame(2))

    assert result.accepted is True
    assert result.overflowed == ("asr",)
    assert result.delivered_to == ("vad",)
    assert vad.get_nowait() is not None
    assert asr.get_nowait() is not None
    assert fanout.stats.dropped_overflow == 1


def test_chunker_uses_negotiated_30ms_frames_and_timer_flush() -> None:
    profile = _profile(30.0)
    chunker = AsrChunker(
        profile=profile,
        call_id="call-map005-b",
        channel_id="call-map005-b:audio",
        generation=1,
        chunk_ms=900,
        flush_ms=1000,
    )

    for sequence in range(1, 31):
        assert chunker.push(_frame(sequence, ptime_ms=30.0)) in (0, 1)
    chunk = chunker.next_chunk()
    assert chunk is not None
    assert chunk.flush_reason is FlushReason.TARGET
    assert chunk.duration_ms == 900.0
    assert chunk.profile.ptime_ms == 30.0

    assert chunker.push(_frame(31, ptime_ms=30.0, value=2)) == 0
    assert chunker.on_timer(31 * 30_000_000 + 1_000_000_000) == 1
    tail = chunker.next_chunk()
    assert tail is not None
    assert tail.flush_reason is FlushReason.TIMER
    assert tail.duration_ms == 30.0


def test_chunker_hard_endpoint_has_one_authoritative_final_marker_and_drops_stale_generation() -> None:
    chunker = AsrChunker(
        profile=_profile(),
        call_id="call-map005-b",
        channel_id="call-map005-b:audio",
        generation=1,
    )
    chunker.push(_frame(1))
    assert chunker.hard_endpoint() == 1
    final_chunk = chunker.next_chunk()
    assert final_chunk is not None
    assert final_chunk.is_final is True
    assert final_chunk.flush_reason is FlushReason.HARD_ENDPOINT
    assert chunker.push(_frame(2, generation=2)) == 0
    assert chunker.stats.dropped_stale == 1


def test_endpointing_uses_300ms_soft_and_500ms_authoritative_hard_boundary() -> None:
    detector = TurnDetector(EndpointingConfig(soft_endpoint_ms=300, hard_endpoint_ms=500, min_speech_ms=60))
    events = []
    sequence = 0
    for timestamp_ms in (0, 30, 60):
        sequence += 1
        events.extend(detector.consume(_vad().process(_frame(sequence, ptime_ms=30.0, value=1))))
    for timestamp_ms in range(90, 600, 30):
        sequence += 1
        silence = _frame(sequence, ptime_ms=30.0, value=0)
        silence = PcmFrame(
            call_id=silence.call_id,
            channel_id=silence.channel_id,
            generation=silence.generation,
            sequence=silence.sequence,
            timestamp_ns=timestamp_ms * 1_000_000,
            pcm_s16le=silence.pcm_s16le,
            profile=silence.profile,
        )
        events.extend(detector.consume(_vad().process(silence)))

    assert [event.kind for event in events] == [
        EndpointEventKind.SPEECH_STARTED,
        EndpointEventKind.PAUSE_CANDIDATE,
        EndpointEventKind.SOFT_ENDPOINT,
        EndpointEventKind.HARD_ENDPOINT,
    ]
    assert next(event for event in events if event.kind is EndpointEventKind.SOFT_ENDPOINT).silence_ms == 300
    hard = next(event for event in events if event.kind is EndpointEventKind.HARD_ENDPOINT)
    assert hard.silence_ms == 510
    assert hard.authoritative is True


def test_resumed_speech_cancels_speculative_endpoint_and_partial_revisions_are_replacements() -> None:
    detector = TurnDetector(EndpointingConfig(soft_endpoint_ms=90, hard_endpoint_ms=500, min_speech_ms=60))
    events = []
    for sequence, value in enumerate((1, 1, 1, 0, 0, 0, 1), start=1):
        events.extend(detector.consume(_vad().process(_frame(sequence, value=value))))

    assert EndpointEventKind.SOFT_ENDPOINT in [event.kind for event in events]
    assert EndpointEventKind.SPEECH_RESUMED in [event.kind for event in events]
    assert EndpointEventKind.HARD_ENDPOINT not in [event.kind for event in events]

    assembler = TranscriptAssembler("call-map005-b", "call-map005-b:audio", 1, "call-map005-b:turn-1", 8)
    first = assembler.accept(AsrHypothesis("call-map005-b", "call-map005-b:audio", 1, 1, 1, "почему небо"))
    second = assembler.accept(
        AsrHypothesis(
            "call-map005-b",
            "call-map005-b:audio",
            1,
            2,
            2,
            "почему небо днем голубое",
            stable_prefix="почему небо",
        )
    )
    stale = assembler.accept(AsrHypothesis("call-map005-b", "call-map005-b:audio", 1, 1, 3, "старый текст"))

    assert first is not None and first.kind is TranscriptUpdateKind.PARTIAL
    assert second is not None and second.text == "почему небо днем голубое"
    assert second.stable_prefix == "почему небо"
    assert second.unstable_suffix == " днем голубое"
    assert stale is None


def test_speech_ingress_emits_exactly_one_final_user_turn_after_hard_endpoint() -> None:
    detector = TurnDetector(EndpointingConfig(soft_endpoint_ms=90, hard_endpoint_ms=180, min_speech_ms=60))
    assembler = TranscriptAssembler("call-map005-b", "call-map005-b:audio", 1, "call-map005-b:turn-1", 0)
    ingress = SpeechIngress(vad=_vad(), turn_detector=detector, assembler=assembler)
    for sequence in range(1, 4):
        ingress.process_frame(_frame(sequence, value=1))
    ingress.accept_hypothesis(
        AsrHypothesis("call-map005-b", "call-map005-b:audio", 1, 1, 100_000_000, "вопрос о небе")
    )

    final_results = []
    for sequence in range(4, 11):
        result = ingress.process_frame(_frame(sequence, value=0))
        if result.final_turn is not None:
            final_results.append(result.final_turn)

    assert len(final_results) == 1
    assert final_results[0].text == "вопрос о небе"
    assert final_results[0].boundary is EndpointEventKind.HARD_ENDPOINT
